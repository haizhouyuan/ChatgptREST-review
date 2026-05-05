"""Runtime state management for Paperclip Skill Agent.

SQLite-backed storage for:
- Quota tracking (budgets, reservations, usage)
- Health monitoring (probe results, circuit breaker state)
- Runtime events (call logs, fallback traces)
- Resource locks (concurrency control)

Replaces the JSON file-backed QuotaLedger for production use.

Usage:
    from runtime_allocator.runtime_state import RuntimeStateStore
    store = RuntimeStateStore()
    store.reserve("claudekimi", request_id="abc", task_class="finbot_trade_proposal")
    store.commit("abc", tokens_actual=1500)
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


_DEFAULT_DB_PATH = Path(os.path.expanduser("~/.paperclip/runtime_state.sqlite"))


class RuntimeStateStore:
    """SQLite-backed runtime state: quota, health, events, locks."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS runtime_budgets (
                provider_id TEXT PRIMARY KEY,
                quota_mode TEXT NOT NULL DEFAULT 'opaque_plan',
                soft_rpd INTEGER DEFAULT 1000,
                hard_rpd INTEGER DEFAULT 1000,
                soft_rpm INTEGER DEFAULT 60,
                hard_rpm INTEGER DEFAULT 60,
                soft_tpd INTEGER,
                hard_tpd INTEGER,
                max_concurrency INTEGER DEFAULT 1,
                cooldown_seconds INTEGER DEFAULT 300,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS runtime_reservations (
                reservation_id TEXT PRIMARY KEY,
                provider_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                attempt_id TEXT,
                task_class TEXT NOT NULL,
                estimated_input_tokens INTEGER DEFAULT 0,
                estimated_output_tokens INTEGER DEFAULT 0,
                actual_input_tokens INTEGER,
                actual_output_tokens INTEGER,
                reserved_units INTEGER DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'reserved'
                    CHECK (status IN ('reserved', 'committed', 'refunded', 'expired')),
                created_at TEXT NOT NULL,
                expires_at TEXT,
                committed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS runtime_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reservation_id TEXT,
                provider_id TEXT,
                task_class TEXT,
                status TEXT,
                error_class TEXT,
                error_code TEXT,
                latency_ms INTEGER,
                tokens_in_est INTEGER,
                tokens_out_est INTEGER,
                tokens_actual INTEGER,
                fallback_from TEXT,
                fallback_to TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runtime_health (
                provider_id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'unknown',
                last_probe_at TEXT,
                last_success_at TEXT,
                last_failure_at TEXT,
                consecutive_failures INTEGER DEFAULT 0,
                circuit_open_until TEXT,
                p50_latency_ms INTEGER,
                p95_latency_ms INTEGER,
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS resource_locks (
                resource_id TEXT PRIMARY KEY,
                owner_request_id TEXT,
                owner_agent_id TEXT,
                lock_type TEXT,
                acquired_at TEXT NOT NULL,
                expires_at TEXT,
                heartbeat_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_reservations_provider
                ON runtime_reservations(provider_id, status);
            CREATE INDEX IF NOT EXISTS idx_reservations_request
                ON runtime_reservations(request_id);
            CREATE INDEX IF NOT EXISTS idx_reservations_provider_created
                ON runtime_reservations(provider_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_events_provider
                ON runtime_events(provider_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_locks_expires
                ON resource_locks(expires_at);
        """)
        # Backfill columns for older DBs (best-effort; ignore if already exists)
        for stmt in (
            "ALTER TABLE runtime_reservations ADD COLUMN attempt_id TEXT",
            "ALTER TABLE runtime_reservations ADD COLUMN actual_input_tokens INTEGER",
            "ALTER TABLE runtime_reservations ADD COLUMN actual_output_tokens INTEGER",
        ):
            try:
                self._conn.execute(stmt)
            except sqlite3.OperationalError:
                pass
        self._conn.commit()

    def close(self):
        self._conn.close()

    # ── Quota: budgets ────────────────────────────────────────────────────

    def init_budget(self, provider_id: str, **kwargs):
        """Initialize or update budget for a provider."""
        now = datetime.now().isoformat()
        defaults = {
            "quota_mode": "opaque_plan",
            "soft_rpd": 1000, "hard_rpd": 1000,
            "soft_rpm": 60, "hard_rpm": 60,
            "max_concurrency": 1, "cooldown_seconds": 300,
        }
        defaults.update(kwargs)
        defaults["updated_at"] = now
        cols = ", ".join(defaults.keys())
        placeholders = ", ".join(["?"] * len(defaults))
        updates = ", ".join(f"{k}=excluded.{k}" for k in defaults if k != "provider_id")
        self._conn.execute(
            f"INSERT INTO runtime_budgets (provider_id, {cols}) VALUES (?, {placeholders}) "
            f"ON CONFLICT(provider_id) DO UPDATE SET {updates}",
            [provider_id] + list(defaults.values()),
        )
        self._conn.commit()

    def get_budget(self, provider_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM runtime_budgets WHERE provider_id=?", (provider_id,)
        ).fetchone()
        return dict(row) if row else None

    # ── Quota: reservations ───────────────────────────────────────────────

    def reserve(
        self,
        provider_id: str,
        request_id: str,
        task_class: str,
        attempt_id: Optional[str] = None,
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
        ttl_seconds: int = 300,
    ) -> str:
        """Reserve a request unit. Returns reservation_id.

        Each attempt within a single request should pass a distinct attempt_id
        so reservations don't conflict.
        """
        reservation_id = str(uuid.uuid4())[:12]
        now = datetime.now()
        expires = now + timedelta(seconds=ttl_seconds)
        self._conn.execute(
            """INSERT INTO runtime_reservations
               (reservation_id, provider_id, request_id, attempt_id, task_class,
                estimated_input_tokens, estimated_output_tokens,
                status, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'reserved', ?, ?)""",
            (reservation_id, provider_id, request_id, attempt_id, task_class,
             estimated_input_tokens, estimated_output_tokens,
             now.isoformat(), expires.isoformat()),
        )
        self._conn.commit()
        return reservation_id

    def commit(
        self,
        reservation_id: str,
        actual_input_tokens: int = 0,
        actual_output_tokens: int = 0,
    ):
        """Mark reservation as committed (successful use).

        Stores actual_input_tokens/actual_output_tokens separately from
        reserved_units. reserved_units stays at 1 (per-call counter).
        """
        now = datetime.now().isoformat()
        self._conn.execute(
            """UPDATE runtime_reservations
               SET status='committed', committed_at=?,
                   actual_input_tokens=?, actual_output_tokens=?
               WHERE reservation_id=?""",
            (now, actual_input_tokens, actual_output_tokens, reservation_id),
        )
        self._conn.commit()

    def refund(self, reservation_id: str, reason: str = ""):
        """Mark reservation as refunded (failed, quota returned)."""
        self._conn.execute(
            "UPDATE runtime_reservations SET status='refunded' WHERE reservation_id=?",
            (reservation_id,),
        )
        self._conn.commit()

    def count_today(self, provider_id: str, status: str = "committed") -> int:
        """Count reservations today for a provider with a specific status."""
        today = datetime.now().strftime("%Y-%m-%d")
        row = self._conn.execute(
            """SELECT COUNT(*) FROM runtime_reservations
               WHERE provider_id=? AND status=? AND created_at LIKE ?""",
            (provider_id, status, f"{today}%"),
        ).fetchone()
        return row[0] if row else 0

    def count_today_units(self, provider_id: str) -> int:
        """Count units consumed today (reserved + committed) for budget gating.

        Excludes refunded/expired so 401/429 failures don't count against quota.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        row = self._conn.execute(
            """SELECT COUNT(*) FROM runtime_reservations
               WHERE provider_id=? AND status IN ('reserved', 'committed')
                 AND created_at LIKE ?""",
            (provider_id, f"{today}%"),
        ).fetchone()
        return row[0] if row else 0

    def can_reserve(self, provider_id: str) -> bool:
        """Check if provider can accept new requests (budget + health)."""
        # Check health first
        if not self.is_usable(provider_id):
            return False

        budget = self.get_budget(provider_id)
        if not budget:
            return True  # No budget configured, allow

        # Use reserved+committed for hard budget enforcement
        used_rpd = self.count_today_units(provider_id)
        if used_rpd >= budget.get("hard_rpd", 1000):
            return False

        return True

    # ── Health: probes and circuit breaker ─────────────────────────────────

    def update_health(
        self,
        provider_id: str,
        status: str,
        latency_ms: Optional[int] = None,
        error: Optional[str] = None,
        circuit_open_seconds: int = 0,
    ):
        """Update health status after a probe or call."""
        now = datetime.now().isoformat()
        existing = self.get_health(provider_id)

        consecutive = 0
        if existing:
            if status in ("healthy",):
                consecutive = 0
            elif existing.get("status") == status:
                consecutive = existing.get("consecutive_failures", 0) + 1
            else:
                consecutive = 1

        circuit_until = None
        if circuit_open_seconds > 0:
            circuit_until = (datetime.now() + timedelta(seconds=circuit_open_seconds)).isoformat()

        self._conn.execute(
            """INSERT INTO runtime_health
               (provider_id, status, last_probe_at, last_success_at, last_failure_at,
                consecutive_failures, circuit_open_until, p50_latency_ms, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(provider_id) DO UPDATE SET
                 status=excluded.status,
                 last_probe_at=excluded.last_probe_at,
                 last_success_at=COALESCE(excluded.last_success_at, runtime_health.last_success_at),
                 last_failure_at=COALESCE(excluded.last_failure_at, runtime_health.last_failure_at),
                 consecutive_failures=excluded.consecutive_failures,
                 circuit_open_until=excluded.circuit_open_until,
                 p50_latency_ms=COALESCE(excluded.p50_latency_ms, runtime_health.p50_latency_ms),
                 note=excluded.note""",
            (
                provider_id, status, now,
                now if status == "healthy" else None,
                now if status not in ("healthy",) else None,
                consecutive, circuit_until,
                latency_ms, error,
            ),
        )
        self._conn.commit()

    def get_health(self, provider_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM runtime_health WHERE provider_id=?", (provider_id,)
        ).fetchone()
        return dict(row) if row else None

    def is_usable(self, provider_id: str) -> bool:
        """Check if provider is usable (not in circuit breaker, not down)."""
        health = self.get_health(provider_id)
        if not health:
            return True  # No health data, assume usable

        status = health.get("status", "unknown")
        if status in ("healthy", "unknown", "degraded"):
            return True
        if status == "down":
            return False

        # Circuit breaker check
        if status == "circuit_open":
            until = health.get("circuit_open_until")
            if until:
                try:
                    if datetime.fromisoformat(until) > datetime.now():
                        return False
                    # Circuit expired, allow retry
                    self.update_health(provider_id, "degraded")
                    return True
                except Exception:
                    return False
            return False

        if status == "quota_exhausted":
            # Check if cooldown expired (use budget cooldown_seconds)
            budget = self.get_budget(provider_id)
            cooldown = budget.get("cooldown_seconds", 300) if budget else 300
            last_fail = health.get("last_failure_at")
            if last_fail:
                try:
                    fail_time = datetime.fromisoformat(last_fail)
                    if datetime.now() - fail_time < timedelta(seconds=cooldown):
                        return False
                    # Cooldown expired
                    self.update_health(provider_id, "degraded")
                    return True
                except Exception:
                    return False
            return False

        return True

    # ── Events: call logging ──────────────────────────────────────────────

    def log_event(
        self,
        provider_id: str,
        task_class: str,
        status: str,
        reservation_id: Optional[str] = None,
        error_class: Optional[str] = None,
        error_code: Optional[str] = None,
        latency_ms: Optional[int] = None,
        tokens_in_est: Optional[int] = None,
        tokens_out_est: Optional[int] = None,
        tokens_actual: Optional[int] = None,
        fallback_from: Optional[str] = None,
        fallback_to: Optional[str] = None,
    ):
        """Log a runtime event (call, failure, fallback)."""
        self._conn.execute(
            """INSERT INTO runtime_events
               (reservation_id, provider_id, task_class, status,
                error_class, error_code, latency_ms,
                tokens_in_est, tokens_out_est, tokens_actual,
                fallback_from, fallback_to, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (reservation_id, provider_id, task_class, status,
             error_class, error_code, latency_ms,
             tokens_in_est, tokens_out_est, tokens_actual,
             fallback_from, fallback_to, datetime.now().isoformat()),
        )
        self._conn.commit()

    def get_events(
        self,
        provider_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get recent events, optionally filtered by provider."""
        if provider_id:
            rows = self._conn.execute(
                "SELECT * FROM runtime_events WHERE provider_id=? ORDER BY id DESC LIMIT ?",
                (provider_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM runtime_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Resource locks ────────────────────────────────────────────────────

    def acquire_lock(
        self,
        resource_id: str,
        owner_request_id: str,
        owner_agent_id: str = "",
        lock_type: str = "exclusive",
        ttl_seconds: int = 600,
    ) -> bool:
        """Try to acquire a resource lock. Returns True if acquired.

        Uses atomic INSERT ... ON CONFLICT with rowcount check for correctness.
        """
        now = datetime.now()
        expires = now + timedelta(seconds=ttl_seconds)

        try:
            self._conn.execute("BEGIN IMMEDIATE")

            # Atomic insert: succeeds only if no lock or lock expired
            self._conn.execute(
                """INSERT INTO resource_locks
                   (resource_id, owner_request_id, owner_agent_id, lock_type,
                    acquired_at, expires_at, heartbeat_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(resource_id) DO UPDATE SET
                     owner_request_id=excluded.owner_request_id,
                     owner_agent_id=excluded.owner_agent_id,
                     lock_type=excluded.lock_type,
                     acquired_at=excluded.acquired_at,
                     expires_at=excluded.expires_at,
                     heartbeat_at=excluded.heartbeat_at
                   WHERE resource_locks.expires_at < ?""",
                (resource_id, owner_request_id, owner_agent_id, lock_type,
                 now.isoformat(), expires.isoformat(), now.isoformat(),
                 now.isoformat()),
            )
            acquired = self._conn.execute("SELECT changes()").fetchone()[0] > 0
            self._conn.commit()
            return acquired
        except Exception:
            self._conn.execute("ROLLBACK")
            return False

    def release_lock(self, resource_id: str, owner_request_id: str):
        """Release a lock if owned by this request."""
        self._conn.execute(
            """DELETE FROM resource_locks
               WHERE resource_id=? AND owner_request_id=?""",
            (resource_id, owner_request_id),
        )
        self._conn.commit()

    def is_locked(self, resource_id: str) -> bool:
        """Check if a resource is currently locked."""
        row = self._conn.execute(
            "SELECT expires_at FROM resource_locks WHERE resource_id=?",
            (resource_id,),
        ).fetchone()
        if not row:
            return False
        try:
            return datetime.fromisoformat(row["expires_at"]) > datetime.now()
        except Exception:
            return False

    # ── Migration from JSON ledger ────────────────────────────────────────

    def migrate_from_json(self, json_path: Optional[Path] = None):
        """Migrate data from old JSON quota ledger."""
        if json_path is None:
            json_path = Path(os.path.expanduser("~/.paperclip/runtime_quota_ledger.json"))
        if not json_path.exists():
            return

        try:
            data = json.loads(json_path.read_text())
        except Exception:
            return

        for date_key, providers in data.items():
            if not isinstance(providers, dict):
                continue
            for provider_id, usage in providers.items():
                if provider_id == "_cooldowns":
                    continue
                if not isinstance(usage, dict):
                    continue
                # Log as historical events
                rpd = usage.get("rpd", 0)
                for _ in range(min(rpd, 100)):  # Cap to avoid huge migrations
                    self.log_event(
                        provider_id=provider_id,
                        task_class="migrated",
                        status="committed",
                    )

    # ── Summary ───────────────────────────────────────────────────────────

    def summary(self) -> dict:
        """Get a summary of all runtime state."""
        budgets = self._conn.execute("SELECT * FROM runtime_budgets").fetchall()
        health = self._conn.execute("SELECT * FROM runtime_health").fetchall()
        locks = self._conn.execute("SELECT * FROM resource_locks").fetchall()
        today = datetime.now().strftime("%Y-%m-%d")
        events_today = self._conn.execute(
            "SELECT COUNT(*) FROM runtime_events WHERE created_at LIKE ?",
            (f"{today}%",),
        ).fetchone()[0]

        return {
            "budgets": [dict(b) for b in budgets],
            "health": [dict(h) for h in health],
            "locks": [dict(l) for l in locks],
            "events_today": events_today,
        }


# ── Singleton ────────────────────────────────────────────────────────────

_store: Optional[RuntimeStateStore] = None


def get_store(db_path: Optional[Path] = None) -> RuntimeStateStore:
    """Get or create the singleton RuntimeStateStore."""
    global _store
    if _store is None:
        _store = RuntimeStateStore(db_path)
    return _store
