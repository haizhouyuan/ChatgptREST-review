from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover
    fcntl = None


SCHEMA_VERSION = 11

_init_lock = threading.Lock()
_initialized_paths: set[str] = set()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _now() -> float:
    return time.time()


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
              k TEXT PRIMARY KEY,
              v TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS idempotency (
              idempotency_key TEXT PRIMARY KEY,
              request_hash TEXT NOT NULL,
              job_id TEXT NOT NULL,
              created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
              job_id TEXT PRIMARY KEY,
              kind TEXT NOT NULL,
              input_json TEXT NOT NULL,
              params_json TEXT NOT NULL,
              client_json TEXT,
              phase TEXT NOT NULL DEFAULT 'send',
              status TEXT NOT NULL,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              not_before REAL NOT NULL DEFAULT 0,
              attempts INTEGER NOT NULL DEFAULT 0,
              max_attempts INTEGER NOT NULL DEFAULT 3,
              lease_owner TEXT,
              lease_expires_at REAL,
              lease_token TEXT,
              cancel_requested_at REAL,
              parent_job_id TEXT,
              conversation_url TEXT,
              conversation_id TEXT,
              conversation_export_format TEXT,
              conversation_export_path TEXT,
              conversation_export_sha256 TEXT,
              conversation_export_chars INTEGER,
              answer_format TEXT,
              answer_path TEXT,
              answer_sha256 TEXT,
              answer_chars INTEGER,
              last_error_type TEXT,
              last_error TEXT
            )
            """
        )
        cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        migrations: list[tuple[str, str]] = [
            ("lease_token", "lease_token TEXT"),
            ("conversation_export_format", "conversation_export_format TEXT"),
            ("conversation_export_path", "conversation_export_path TEXT"),
            ("conversation_export_sha256", "conversation_export_sha256 TEXT"),
            ("conversation_export_chars", "conversation_export_chars INTEGER"),
            ("phase", "phase TEXT NOT NULL DEFAULT 'send'"),
            ("client_json", "client_json TEXT"),
            ("conversation_id", "conversation_id TEXT"),
        ]
        for name, ddl in migrations:
            if name not in cols:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {ddl}")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_ready
            ON jobs(status, not_before)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              job_id TEXT NOT NULL,
              ts REAL NOT NULL,
              type TEXT NOT NULL,
              payload_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_job_events_job_id
            ON job_events(job_id, id)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rate_limits (
              k TEXT PRIMARY KEY,
              last_ts REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_counters (
              k TEXT NOT NULL,
              window_start INTEGER NOT NULL,
              count INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY (k, window_start)
            )
            """
        )

        # Incident management (maint_daemon / repair loops).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
              incident_id TEXT PRIMARY KEY,
              fingerprint_hash TEXT NOT NULL,
              signature TEXT NOT NULL,
              category TEXT,
              severity TEXT NOT NULL DEFAULT 'P2',
              status TEXT NOT NULL DEFAULT 'open',
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              last_seen_at REAL NOT NULL,
              count INTEGER NOT NULL DEFAULT 0,
              job_ids_json TEXT,
              evidence_dir TEXT,
              repair_job_id TEXT,
              codex_input_hash TEXT,
              codex_last_run_ts REAL,
              codex_run_count INTEGER NOT NULL DEFAULT 0,
              codex_last_ok INTEGER,
              codex_last_error TEXT,
              codex_autofix_last_ts REAL,
              codex_autofix_run_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_incidents_fingerprint_status
            ON incidents(fingerprint_hash, status, updated_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_incidents_updated_at
            ON incidents(updated_at)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS remediation_actions (
              action_id TEXT PRIMARY KEY,
              incident_id TEXT NOT NULL,
              action_type TEXT NOT NULL,
              status TEXT NOT NULL,
              risk_level TEXT NOT NULL DEFAULT 'low',
              created_at REAL NOT NULL,
              started_at REAL,
              completed_at REAL,
              result_json TEXT,
              error_type TEXT,
              error TEXT,
              FOREIGN KEY(incident_id) REFERENCES incidents(incident_id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_remediation_actions_incident
            ON remediation_actions(incident_id, created_at)
            """
        )

        # Client issue ledger (cross-project issue tracking for ChatgptREST clients).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS client_issues (
              issue_id TEXT PRIMARY KEY,
              fingerprint_hash TEXT NOT NULL,
              fingerprint_text TEXT NOT NULL,
              project TEXT NOT NULL,
              title TEXT NOT NULL,
              kind TEXT,
              severity TEXT NOT NULL DEFAULT 'P2',
              status TEXT NOT NULL DEFAULT 'open',
              source TEXT,
              symptom TEXT,
              raw_error TEXT,
              tags_json TEXT,
              metadata_json TEXT,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              first_seen_at REAL NOT NULL,
              last_seen_at REAL NOT NULL,
              closed_at REAL,
              count INTEGER NOT NULL DEFAULT 1,
              latest_job_id TEXT,
              latest_conversation_url TEXT,
              latest_artifacts_path TEXT
            )
            """
        )
        issue_cols = {row[1] for row in conn.execute("PRAGMA table_info(client_issues)").fetchall()}
        issue_migrations: list[tuple[str, str]] = [
            ("fingerprint_text", "fingerprint_text TEXT"),
            ("project", "project TEXT"),
            ("title", "title TEXT"),
            ("kind", "kind TEXT"),
            ("severity", "severity TEXT NOT NULL DEFAULT 'P2'"),
            ("status", "status TEXT NOT NULL DEFAULT 'open'"),
            ("source", "source TEXT"),
            ("symptom", "symptom TEXT"),
            ("raw_error", "raw_error TEXT"),
            ("tags_json", "tags_json TEXT"),
            ("metadata_json", "metadata_json TEXT"),
            ("created_at", "created_at REAL"),
            ("updated_at", "updated_at REAL"),
            ("first_seen_at", "first_seen_at REAL"),
            ("last_seen_at", "last_seen_at REAL"),
            ("closed_at", "closed_at REAL"),
            ("count", "count INTEGER NOT NULL DEFAULT 1"),
            ("latest_job_id", "latest_job_id TEXT"),
            ("latest_conversation_url", "latest_conversation_url TEXT"),
            ("latest_artifacts_path", "latest_artifacts_path TEXT"),
        ]
        for name, ddl in issue_migrations:
            if name not in issue_cols:
                conn.execute(f"ALTER TABLE client_issues ADD COLUMN {ddl}")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_client_issues_fingerprint_status_updated
            ON client_issues(fingerprint_hash, status, updated_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_client_issues_project_updated
            ON client_issues(project, updated_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_client_issues_updated
            ON client_issues(updated_at, issue_id)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS client_issue_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              issue_id TEXT NOT NULL,
              ts REAL NOT NULL,
              type TEXT NOT NULL,
              payload_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_client_issue_events_issue_id
            ON client_issue_events(issue_id, id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_client_issue_events_ts
            ON client_issue_events(ts)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS client_issue_verifications (
              verification_id TEXT PRIMARY KEY,
              issue_id TEXT NOT NULL,
              ts REAL NOT NULL,
              verification_type TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'passed',
              verifier TEXT,
              note TEXT,
              job_id TEXT,
              conversation_url TEXT,
              artifacts_path TEXT,
              metadata_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_client_issue_verifications_issue_ts
            ON client_issue_verifications(issue_id, ts DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_client_issue_verifications_job
            ON client_issue_verifications(job_id)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS client_issue_usage_evidence (
              usage_id TEXT PRIMARY KEY,
              issue_id TEXT NOT NULL,
              ts REAL NOT NULL,
              job_id TEXT NOT NULL,
              client_name TEXT,
              kind TEXT,
              status TEXT NOT NULL DEFAULT 'completed',
              answer_chars INTEGER,
              metadata_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_client_issue_usage_unique
            ON client_issue_usage_evidence(issue_id, job_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_client_issue_usage_issue_ts
            ON client_issue_usage_evidence(issue_id, ts DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_client_issue_usage_job
            ON client_issue_usage_evidence(job_id)
            """
        )

        # Advisor orchestrate state store (run/step/lease/event).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS advisor_runs (
              run_id TEXT PRIMARY KEY,
              request_id TEXT,
              mode TEXT NOT NULL DEFAULT 'balanced',
              status TEXT NOT NULL,
              route TEXT,
              raw_question TEXT,
              normalized_question TEXT,
              context_json TEXT NOT NULL DEFAULT '{}',
              quality_threshold INTEGER,
              crosscheck INTEGER NOT NULL DEFAULT 0,
              max_retries INTEGER NOT NULL DEFAULT 0,
              orchestrate_job_id TEXT,
              final_job_id TEXT,
              degraded INTEGER NOT NULL DEFAULT 0,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              ended_at REAL,
              error_type TEXT,
              error TEXT
            )
            """
        )
        run_cols = {row[1] for row in conn.execute("PRAGMA table_info(advisor_runs)").fetchall()}
        run_migrations: list[tuple[str, str]] = [
            ("request_id", "request_id TEXT"),
            ("mode", "mode TEXT NOT NULL DEFAULT 'balanced'"),
            ("status", "status TEXT"),
            ("route", "route TEXT"),
            ("raw_question", "raw_question TEXT"),
            ("normalized_question", "normalized_question TEXT"),
            ("context_json", "context_json TEXT NOT NULL DEFAULT '{}'"),
            ("quality_threshold", "quality_threshold INTEGER"),
            ("crosscheck", "crosscheck INTEGER NOT NULL DEFAULT 0"),
            ("max_retries", "max_retries INTEGER NOT NULL DEFAULT 0"),
            ("orchestrate_job_id", "orchestrate_job_id TEXT"),
            ("final_job_id", "final_job_id TEXT"),
            ("degraded", "degraded INTEGER NOT NULL DEFAULT 0"),
            ("created_at", "created_at REAL"),
            ("updated_at", "updated_at REAL"),
            ("ended_at", "ended_at REAL"),
            ("error_type", "error_type TEXT"),
            ("error", "error TEXT"),
        ]
        for name, ddl in run_migrations:
            if name not in run_cols:
                conn.execute(f"ALTER TABLE advisor_runs ADD COLUMN {ddl}")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_advisor_runs_updated
            ON advisor_runs(updated_at, run_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_advisor_runs_status_updated
            ON advisor_runs(status, updated_at)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS advisor_steps (
              run_id TEXT NOT NULL,
              step_id TEXT NOT NULL,
              step_type TEXT NOT NULL,
              status TEXT NOT NULL,
              attempt INTEGER NOT NULL DEFAULT 0,
              job_id TEXT,
              lease_id TEXT,
              lease_expires_at REAL,
              input_json TEXT,
              output_json TEXT,
              evidence_path TEXT,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              PRIMARY KEY (run_id, step_id)
            )
            """
        )
        step_cols = {row[1] for row in conn.execute("PRAGMA table_info(advisor_steps)").fetchall()}
        step_migrations: list[tuple[str, str]] = [
            ("step_type", "step_type TEXT"),
            ("status", "status TEXT"),
            ("attempt", "attempt INTEGER NOT NULL DEFAULT 0"),
            ("job_id", "job_id TEXT"),
            ("lease_id", "lease_id TEXT"),
            ("lease_expires_at", "lease_expires_at REAL"),
            ("input_json", "input_json TEXT"),
            ("output_json", "output_json TEXT"),
            ("evidence_path", "evidence_path TEXT"),
            ("created_at", "created_at REAL"),
            ("updated_at", "updated_at REAL"),
        ]
        for name, ddl in step_migrations:
            if name not in step_cols:
                conn.execute(f"ALTER TABLE advisor_steps ADD COLUMN {ddl}")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_advisor_steps_run_updated
            ON advisor_steps(run_id, updated_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_advisor_steps_job
            ON advisor_steps(job_id)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS advisor_leases (
              lease_id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL,
              step_id TEXT NOT NULL,
              owner TEXT,
              token TEXT,
              status TEXT NOT NULL,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              expires_at REAL,
              heartbeat_at REAL
            )
            """
        )
        lease_cols = {row[1] for row in conn.execute("PRAGMA table_info(advisor_leases)").fetchall()}
        lease_migrations: list[tuple[str, str]] = [
            ("run_id", "run_id TEXT"),
            ("step_id", "step_id TEXT"),
            ("owner", "owner TEXT"),
            ("token", "token TEXT"),
            ("status", "status TEXT"),
            ("created_at", "created_at REAL"),
            ("updated_at", "updated_at REAL"),
            ("expires_at", "expires_at REAL"),
            ("heartbeat_at", "heartbeat_at REAL"),
        ]
        for name, ddl in lease_migrations:
            if name not in lease_cols:
                conn.execute(f"ALTER TABLE advisor_leases ADD COLUMN {ddl}")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_advisor_leases_run_step
            ON advisor_leases(run_id, step_id, updated_at)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS advisor_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id TEXT NOT NULL,
              step_id TEXT,
              ts REAL NOT NULL,
              type TEXT NOT NULL,
              payload_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_advisor_events_run_id
            ON advisor_events(run_id, id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_advisor_events_ts
            ON advisor_events(ts)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_outcomes (
              outcome_id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL UNIQUE,
              trace_id TEXT NOT NULL DEFAULT '',
              job_id TEXT NOT NULL DEFAULT '',
              task_ref TEXT NOT NULL DEFAULT '',
              logical_task_id TEXT NOT NULL DEFAULT '',
              identity_confidence TEXT NOT NULL DEFAULT '',
              route TEXT NOT NULL DEFAULT '',
              provider TEXT NOT NULL DEFAULT '',
              channel TEXT NOT NULL DEFAULT '',
              session_id TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT '',
              degraded INTEGER NOT NULL DEFAULT 0,
              fallback_chain_json TEXT NOT NULL DEFAULT '[]',
              retrieval_refs_json TEXT NOT NULL DEFAULT '[]',
              artifacts_json TEXT NOT NULL DEFAULT '[]',
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            )
            """
        )
        outcome_cols = {row[1] for row in conn.execute("PRAGMA table_info(execution_outcomes)").fetchall()}
        outcome_migrations: list[tuple[str, str]] = [
            ("trace_id", "trace_id TEXT NOT NULL DEFAULT ''"),
            ("job_id", "job_id TEXT NOT NULL DEFAULT ''"),
            ("task_ref", "task_ref TEXT NOT NULL DEFAULT ''"),
            ("logical_task_id", "logical_task_id TEXT NOT NULL DEFAULT ''"),
            ("identity_confidence", "identity_confidence TEXT NOT NULL DEFAULT ''"),
            ("route", "route TEXT NOT NULL DEFAULT ''"),
            ("provider", "provider TEXT NOT NULL DEFAULT ''"),
            ("channel", "channel TEXT NOT NULL DEFAULT ''"),
            ("session_id", "session_id TEXT NOT NULL DEFAULT ''"),
            ("status", "status TEXT NOT NULL DEFAULT ''"),
            ("degraded", "degraded INTEGER NOT NULL DEFAULT 0"),
            ("fallback_chain_json", "fallback_chain_json TEXT NOT NULL DEFAULT '[]'"),
            ("retrieval_refs_json", "retrieval_refs_json TEXT NOT NULL DEFAULT '[]'"),
            ("artifacts_json", "artifacts_json TEXT NOT NULL DEFAULT '[]'"),
            ("metadata_json", "metadata_json TEXT NOT NULL DEFAULT '{}'"),
            ("created_at", "created_at REAL"),
            ("updated_at", "updated_at REAL"),
        ]
        for name, ddl in outcome_migrations:
            if name not in outcome_cols:
                conn.execute(f"ALTER TABLE execution_outcomes ADD COLUMN {ddl}")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_execution_outcomes_status_updated
            ON execution_outcomes(status, updated_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_execution_outcomes_task_ref
            ON execution_outcomes(task_ref, updated_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_execution_outcomes_logical_task
            ON execution_outcomes(logical_task_id, updated_at)
            """
        )

        # Unified controller ledger: durable run/work/checkpoint/artifact state
        # for OpenMind/OpenClaw hot paths. This extends advisor_runs without
        # changing the existing advisor executor contracts.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS controller_runs (
              run_id TEXT PRIMARY KEY,
              trace_id TEXT,
              request_id TEXT,
              execution_mode TEXT NOT NULL DEFAULT 'sync',
              controller_status TEXT NOT NULL DEFAULT 'NEW',
              objective_text TEXT,
              objective_kind TEXT,
              success_criteria_json TEXT NOT NULL DEFAULT '[]',
              constraints_json TEXT NOT NULL DEFAULT '[]',
              delivery_target_json TEXT NOT NULL DEFAULT '{}',
              current_work_id TEXT,
              blocked_reason TEXT,
              wake_after REAL,
              plan_version INTEGER NOT NULL DEFAULT 1,
              route TEXT,
              provider TEXT,
              preset TEXT,
              session_id TEXT,
              account_id TEXT,
              thread_id TEXT,
              agent_id TEXT,
              role_id TEXT,
              user_id TEXT,
              intent_hint TEXT,
              question TEXT,
              normalized_question TEXT,
              request_json TEXT NOT NULL DEFAULT '{}',
              plan_json TEXT NOT NULL DEFAULT '{}',
              delivery_json TEXT NOT NULL DEFAULT '{}',
              next_action_json TEXT NOT NULL DEFAULT '{}',
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              ended_at REAL
            )
            """
        )
        controller_run_cols = {row[1] for row in conn.execute("PRAGMA table_info(controller_runs)").fetchall()}
        controller_run_migrations: list[tuple[str, str]] = [
            ("trace_id", "trace_id TEXT"),
            ("request_id", "request_id TEXT"),
            ("execution_mode", "execution_mode TEXT NOT NULL DEFAULT 'sync'"),
            ("controller_status", "controller_status TEXT NOT NULL DEFAULT 'NEW'"),
            ("objective_text", "objective_text TEXT"),
            ("objective_kind", "objective_kind TEXT"),
            ("success_criteria_json", "success_criteria_json TEXT NOT NULL DEFAULT '[]'"),
            ("constraints_json", "constraints_json TEXT NOT NULL DEFAULT '[]'"),
            ("delivery_target_json", "delivery_target_json TEXT NOT NULL DEFAULT '{}'"),
            ("current_work_id", "current_work_id TEXT"),
            ("blocked_reason", "blocked_reason TEXT"),
            ("wake_after", "wake_after REAL"),
            ("plan_version", "plan_version INTEGER NOT NULL DEFAULT 1"),
            ("route", "route TEXT"),
            ("provider", "provider TEXT"),
            ("preset", "preset TEXT"),
            ("session_id", "session_id TEXT"),
            ("account_id", "account_id TEXT"),
            ("thread_id", "thread_id TEXT"),
            ("agent_id", "agent_id TEXT"),
            ("role_id", "role_id TEXT"),
            ("user_id", "user_id TEXT"),
            ("intent_hint", "intent_hint TEXT"),
            ("question", "question TEXT"),
            ("normalized_question", "normalized_question TEXT"),
            ("request_json", "request_json TEXT NOT NULL DEFAULT '{}'"),
            ("plan_json", "plan_json TEXT NOT NULL DEFAULT '{}'"),
            ("delivery_json", "delivery_json TEXT NOT NULL DEFAULT '{}'"),
            ("next_action_json", "next_action_json TEXT NOT NULL DEFAULT '{}'"),
            ("created_at", "created_at REAL"),
            ("updated_at", "updated_at REAL"),
            ("ended_at", "ended_at REAL"),
        ]
        for name, ddl in controller_run_migrations:
            if name not in controller_run_cols:
                conn.execute(f"ALTER TABLE controller_runs ADD COLUMN {ddl}")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_controller_runs_trace
            ON controller_runs(trace_id, updated_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_controller_runs_request
            ON controller_runs(request_id, updated_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_controller_runs_status_updated
            ON controller_runs(controller_status, updated_at)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS controller_work_items (
              run_id TEXT NOT NULL,
              work_id TEXT NOT NULL,
              title TEXT NOT NULL,
              kind TEXT NOT NULL,
              status TEXT NOT NULL,
              owner TEXT,
              lane TEXT,
              priority TEXT,
              job_id TEXT,
              depends_on_json TEXT NOT NULL DEFAULT '[]',
              input_json TEXT NOT NULL DEFAULT '{}',
              output_json TEXT NOT NULL DEFAULT '{}',
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              PRIMARY KEY (run_id, work_id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_controller_work_items_status
            ON controller_work_items(run_id, status, updated_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_controller_work_items_job
            ON controller_work_items(job_id)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS controller_checkpoints (
              run_id TEXT NOT NULL,
              checkpoint_id TEXT NOT NULL,
              title TEXT NOT NULL,
              status TEXT NOT NULL,
              blocking INTEGER NOT NULL DEFAULT 0,
              details_json TEXT NOT NULL DEFAULT '{}',
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              PRIMARY KEY (run_id, checkpoint_id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_controller_checkpoints_status
            ON controller_checkpoints(run_id, status, updated_at)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS controller_artifacts (
              run_id TEXT NOT NULL,
              artifact_id TEXT NOT NULL,
              work_id TEXT,
              kind TEXT NOT NULL,
              title TEXT NOT NULL,
              path TEXT,
              uri TEXT,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at REAL NOT NULL,
              PRIMARY KEY (run_id, artifact_id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_controller_artifacts_work
            ON controller_artifacts(run_id, work_id, created_at)
            """
        )

        conn.execute("INSERT OR IGNORE INTO meta(k, v) VALUES (?, ?)", ("schema_version", str(SCHEMA_VERSION)))
        conn.execute("UPDATE meta SET v = ? WHERE k = ?", (str(SCHEMA_VERSION), "schema_version"))
        conn.commit()
    finally:
        conn.close()


def ensure_db_initialized(db_path: Path) -> None:
    key = str(db_path)
    with _init_lock:
        if key in _initialized_paths:
            return

        # Cross-process init lock: multiple chatgptrest processes may start at once (api/worker/mcp).
        # Concurrent PRAGMA/migrations can trigger "database is locked" storms even with busy_timeout.
        lock_path = Path(str(db_path) + ".init.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd: int | None = None
        try:
            if fcntl is not None:
                fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
                fcntl.flock(fd, fcntl.LOCK_EX)
            init_db(db_path)
            _initialized_paths.add(key)
        finally:
            if fd is not None:
                try:
                    if fcntl is not None:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                except Exception:
                    pass
                try:
                    os.close(fd)
                except Exception:
                    pass


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    ensure_db_initialized(db_path)
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    try:
        conn.row_factory = sqlite3.Row
        # journal_mode=WAL is persisted per database file; init_db() sets it once.
        conn.execute("PRAGMA busy_timeout=30000")
        yield conn
    finally:
        conn.close()


def insert_event(conn: sqlite3.Connection, *, job_id: str, type: str, payload: Any | None = None) -> None:
    conn.execute(
        "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
        (job_id, _now(), type, (_json_dumps(payload) if payload is not None else None)),
    )


def meta_get(conn: sqlite3.Connection, *, key: str) -> str | None:
    row = conn.execute("SELECT v FROM meta WHERE k = ?", (str(key),)).fetchone()
    if row is None:
        return None
    try:
        return str(row["v"])
    except Exception:
        return None


def meta_set(conn: sqlite3.Connection, *, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO meta(k, v) VALUES (?, ?)", (str(key), str(value)))
