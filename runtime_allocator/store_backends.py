"""Pluggable storage backends for RuntimeStateStore.

SQLite is the default (zero dependency). PostgreSQL can be swapped in
for high-concurrency deployments by installing psycopg2 and passing
a connection URI.

Usage:
    from runtime_allocator.store_backends import SQLiteBackend
    backend = SQLiteBackend("/path/to/db.sqlite")
"""

from __future__ import annotations

import os
import sqlite3
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


_DEFAULT_SQLITE_PATH = Path(os.path.expanduser("~/.paperclip/runtime_state.sqlite"))


class StateStoreBackend(ABC):
    """Abstract interface for runtime state storage."""

    @abstractmethod
    def init_schema(self):
        """Create tables and indexes if they don't exist."""
        ...

    @abstractmethod
    def execute(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a query and return results as dicts."""
        ...

    @abstractmethod
    def execute_write(self, sql: str, params: tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE and return rowcount."""
        ...

    @abstractmethod
    def fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Execute and return a single row or None."""
        ...


class SQLiteBackend(StateStoreBackend):
    """SQLite-backed state storage (default, zero external deps)."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else _DEFAULT_SQLITE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def init_schema(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runtime_budgets (
                    provider_id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL DEFAULT '',
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
                    company_id TEXT NOT NULL DEFAULT '',
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
                    company_id TEXT NOT NULL DEFAULT '',
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
                    company_id TEXT NOT NULL DEFAULT '',
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
                    company_id TEXT NOT NULL DEFAULT '',
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
            backfill_stmts = [
                "ALTER TABLE runtime_budgets ADD COLUMN company_id TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE runtime_reservations ADD COLUMN attempt_id TEXT",
                "ALTER TABLE runtime_reservations ADD COLUMN actual_input_tokens INTEGER",
                "ALTER TABLE runtime_reservations ADD COLUMN actual_output_tokens INTEGER",
                "ALTER TABLE runtime_reservations ADD COLUMN company_id TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE runtime_events ADD COLUMN company_id TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE runtime_health ADD COLUMN company_id TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE resource_locks ADD COLUMN company_id TEXT NOT NULL DEFAULT ''",
            ]
            for stmt in backfill_stmts:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass
            conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def execute_write(self, sql: str, params: tuple = ()) -> int:
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(sql, params)
                conn.commit()
                return cur.rowcount

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None


class PostgreSQLBackend(StateStoreBackend):
    """PostgreSQL-backed state storage for high-concurrency deployments.

    Requires: pip install psycopg2-binary

    Usage:
        backend = PostgreSQLBackend("postgresql://user:pass@host/db")
    """

    def __init__(self, connection_uri: str):
        self.connection_uri = connection_uri
        try:
            import psycopg2
            self._psycopg2 = psycopg2
        except ImportError as exc:
            raise ImportError(
                "PostgreSQLBackend requires psycopg2. Install it: pip install psycopg2-binary"
            ) from exc
        self.init_schema()

    def _connect(self):
        conn = self._psycopg2.connect(self.connection_uri)
        # Dict cursor for row-like access
        from psycopg2.extras import RealDictCursor
        return conn, conn.cursor(cursor_factory=RealDictCursor)

    def init_schema(self):
        conn, cur = self._connect()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS runtime_budgets (
                    provider_id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL DEFAULT '',
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
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS runtime_reservations (
                    reservation_id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL DEFAULT '',
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
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS runtime_events (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT NOT NULL DEFAULT '',
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
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS runtime_health (
                    provider_id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'unknown',
                    last_probe_at TEXT,
                    last_success_at TEXT,
                    last_failure_at TEXT,
                    consecutive_failures INTEGER DEFAULT 0,
                    circuit_open_until TEXT,
                    p50_latency_ms INTEGER,
                    p95_latency_ms INTEGER,
                    note TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS resource_locks (
                    resource_id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL DEFAULT '',
                    owner_request_id TEXT,
                    owner_agent_id TEXT,
                    lock_type TEXT,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT,
                    heartbeat_at TEXT
                )
            """)
            # Indexes
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS idx_reservations_provider ON runtime_reservations(provider_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_reservations_request ON runtime_reservations(request_id)",
                "CREATE INDEX IF NOT EXISTS idx_reservations_provider_created ON runtime_reservations(provider_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_events_provider ON runtime_events(provider_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_locks_expires ON resource_locks(expires_at)",
            ):
                cur.execute(idx_sql)
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> list[dict]:
        conn, cur = self._connect()
        try:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            cur.close()
            conn.close()

    def execute_write(self, sql: str, params: tuple = ()) -> int:
        conn, cur = self._connect()
        try:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount
        finally:
            cur.close()
            conn.close()

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        conn, cur = self._connect()
        try:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            cur.close()
            conn.close()
