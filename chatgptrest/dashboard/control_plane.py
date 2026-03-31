from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from chatgptrest.core.config import AppConfig
from chatgptrest.core.db import connect as connect_jobdb
from chatgptrest.core.openmind_paths import (
    REPO_ROOT,
    resolve_evomap_knowledge_read_db_path,
    resolve_openmind_event_bus_db_path,
    resolve_openmind_kb_search_db_path,
)
from chatgptrest.evomap.paths import resolve_evomap_db_path, resolve_kb_registry_db_path


DEFAULT_CONTROLLER_LANE_DB_PATH = REPO_ROOT / "state" / "controller_lanes.sqlite3"
DEFAULT_DASHBOARD_DB_PATH = REPO_ROOT / "state" / "dashboard_control_plane.sqlite3"
DEFAULT_OPENMIND_MEMORY_DB = Path("~/.openmind/memory.db").expanduser()
SCHEMA_VERSION = 1

_MATERIALIZE_LOCK = threading.Lock()

_DDL = """
CREATE TABLE IF NOT EXISTS meta (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS identity_map (
  identity_key TEXT PRIMARY KEY,
  root_run_id TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  source_system TEXT NOT NULL,
  task_id TEXT,
  task_ref TEXT,
  trace_id TEXT,
  run_id TEXT,
  job_id TEXT,
  lane_id TEXT,
  team_run_id TEXT,
  role_name TEXT,
  checkpoint_id TEXT,
  issue_id TEXT,
  incident_id TEXT,
  ingress_channel TEXT,
  session_id TEXT,
  thread_id TEXT,
  tenant_id TEXT,
  team_id TEXT,
  user_id TEXT,
  updated_at REAL NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_identity_map_root ON identity_map(root_run_id, entity_type, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_identity_map_trace ON identity_map(trace_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_identity_map_task ON identity_map(task_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS canonical_events (
  event_key TEXT PRIMARY KEY,
  root_run_id TEXT NOT NULL,
  source_system TEXT NOT NULL,
  layer TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  status TEXT,
  severity TEXT,
  ts REAL NOT NULL,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_canonical_events_root_ts ON canonical_events(root_run_id, ts DESC);

CREATE TABLE IF NOT EXISTS run_index (
  root_run_id TEXT PRIMARY KEY,
  root_entity_type TEXT NOT NULL,
  task_id TEXT,
  task_ref TEXT,
  title TEXT,
  ingress_channel TEXT,
  session_id TEXT,
  thread_id TEXT,
  tenant_id TEXT,
  team_id TEXT,
  user_id TEXT,
  trace_id TEXT,
  run_id TEXT,
  job_id TEXT,
  job_kind TEXT,
  job_phase TEXT,
  job_status TEXT,
  lane_id TEXT,
  lane_status TEXT,
  team_run_id TEXT,
  role_name TEXT,
  checkpoint_id TEXT,
  issue_id TEXT,
  incident_id TEXT,
  current_layer TEXT NOT NULL,
  current_status TEXT NOT NULL,
  current_owner TEXT NOT NULL DEFAULT '',
  problem_class TEXT NOT NULL,
  health_tone TEXT NOT NULL,
  upstream_json TEXT NOT NULL DEFAULT '[]',
  downstream_json TEXT NOT NULL DEFAULT '[]',
  entity_counts_json TEXT NOT NULL DEFAULT '{}',
  summary_json TEXT NOT NULL DEFAULT '{}',
  created_at REAL NOT NULL DEFAULT 0,
  last_progress_at REAL NOT NULL DEFAULT 0,
  updated_at REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_run_index_status ON run_index(current_status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_run_index_problem ON run_index(problem_class, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_run_index_ingress ON run_index(ingress_channel, updated_at DESC);

CREATE TABLE IF NOT EXISTS run_timeline (
  root_run_id TEXT NOT NULL,
  event_rank INTEGER NOT NULL,
  ts REAL NOT NULL,
  layer TEXT NOT NULL,
  source_system TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  status TEXT,
  severity TEXT,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (root_run_id, event_rank)
);
CREATE INDEX IF NOT EXISTS idx_run_timeline_root_ts ON run_timeline(root_run_id, ts DESC);

CREATE TABLE IF NOT EXISTS component_health (
  component_key TEXT PRIMARY KEY,
  plane TEXT NOT NULL,
  label TEXT NOT NULL,
  status TEXT NOT NULL,
  severity TEXT NOT NULL,
  ok INTEGER,
  guard_family TEXT,
  attention_reason TEXT,
  blast_radius TEXT,
  signal_ts REAL NOT NULL DEFAULT 0,
  summary TEXT NOT NULL DEFAULT '',
  details_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_component_health_plane ON component_health(plane, severity, signal_ts DESC);

CREATE TABLE IF NOT EXISTS incident_index (
  incident_key TEXT PRIMARY KEY,
  incident_type TEXT NOT NULL,
  incident_id TEXT NOT NULL,
  root_run_id TEXT,
  job_id TEXT,
  issue_id TEXT,
  project TEXT,
  category TEXT,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  blast_radius TEXT NOT NULL DEFAULT 'local',
  guard_source TEXT,
  updated_at REAL NOT NULL DEFAULT 0,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_incident_index_status ON incident_index(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_incident_index_root ON incident_index(root_run_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS cognitive_snapshot (
  snapshot_key TEXT PRIMARY KEY,
  scope TEXT NOT NULL,
  root_run_id TEXT,
  kind TEXT NOT NULL,
  ts REAL NOT NULL,
  summary_json TEXT NOT NULL DEFAULT '{}',
  details_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_cognitive_snapshot_scope ON cognitive_snapshot(scope, ts DESC);
"""


def _safe_json_loads(raw: Any, *, default: Any) -> Any:
    if raw is None:
        return default
    try:
        return json.loads(str(raw))
    except Exception:
        return default


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _as_text(raw: Any) -> str:
    return str(raw or "").strip()


def _as_float(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)
    except Exception:
        return float(default)


def _as_int(raw: Any, default: int = 0) -> int:
    try:
        return int(raw)
    except Exception:
        return int(default)


def _truncate(raw: Any, limit: int = 180) -> str:
    text = _as_text(raw)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _connect_sqlite(path: str | Path | None) -> sqlite3.Connection | None:
    if not path:
        return None
    resolved = Path(path).expanduser()
    if not resolved.exists():
        return None
    conn = sqlite3.connect(str(resolved), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


@contextmanager
def _open_sqlite(path: str | Path | None) -> Any:
    conn = _connect_sqlite(path)
    try:
        yield conn
    finally:
        if conn is not None:
            conn.close()


def _table_exists(conn: sqlite3.Connection | None, table_name: str) -> bool:
    if conn is None:
        return False
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (str(table_name),),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection | None, table_name: str) -> set[str]:
    if conn is None or not _table_exists(conn, table_name):
        return set()
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _sql_in_clause(values: list[str]) -> tuple[str, list[str]]:
    placeholders = ",".join(["?"] * len(values))
    return placeholders, [str(value) for value in values]


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _pick_latest(rows: list[dict[str, Any]], *, status_fields: tuple[str, ...] = (), preferred: set[str] | None = None) -> dict[str, Any] | None:
    if not rows:
        return None
    preferred = preferred or set()

    def _sort_key(row: dict[str, Any]) -> tuple[int, float]:
        matched = 1 if any(_as_text(row.get(field)).lower() in preferred for field in status_fields) else 0
        stamp = max(
            _as_float(row.get("updated_at")),
            _as_float(row.get("last_seen_at")),
            _as_float(row.get("heartbeat_at")),
            _as_float(row.get("created_at")),
            _as_float(row.get("started_at")),
        )
        return (matched, stamp)

    return max(rows, key=_sort_key)


def _tone_for_status(status: str, *, severe: bool = False) -> str:
    value = _as_text(status).lower()
    if value in {"completed", "closed", "resolved", "ok", "idle", "healthy"}:
        return "success"
    if value in {"running", "working", "in_progress", "queued", "pending"}:
        return "accent"
    if value in {"blocked", "error", "failed", "critical"}:
        return "danger"
    if value in {"warning", "open", "needs_followup", "cooldown", "stale", "degraded"} or severe:
        return "warning"
    return "neutral"


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}
        self.rank: dict[str, int] = {}

    def add(self, key: str) -> None:
        if key not in self.parent:
            self.parent[key] = key
            self.rank[key] = 0

    def find(self, key: str) -> str:
        parent = self.parent.get(key)
        if parent is None:
            self.add(key)
            return key
        if parent != key:
            self.parent[key] = self.find(parent)
        return self.parent[key]

    def union(self, left: str, right: str) -> None:
        if not left or not right:
            return
        self.add(left)
        self.add(right)
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return
        rank_left = self.rank.get(root_left, 0)
        rank_right = self.rank.get(root_right, 0)
        if rank_left < rank_right:
            root_left, root_right = root_right, root_left
            rank_left, rank_right = rank_right, rank_left
        self.parent[root_right] = root_left
        if rank_left == rank_right:
            self.rank[root_left] = rank_left + 1

    def groups(self) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for key in list(self.parent):
            root = self.find(key)
            grouped.setdefault(root, []).append(key)
        return grouped


@dataclass(frozen=True)
class DashboardControlPlaneConfig:
    job_db_path: Path
    artifacts_dir: Path
    read_db_path: Path
    controller_lane_db_path: Path
    openmind_kb_search_db_path: Path
    openmind_kb_registry_db_path: Path
    openmind_memory_db_path: Path
    openmind_events_db_path: Path
    evomap_knowledge_db_path: Path | None
    evomap_signals_db_path: Path
    refresh_interval_seconds: int
    bootstrap_on_read: bool

    @classmethod
    def from_app_config(cls, cfg: AppConfig) -> "DashboardControlPlaneConfig":
        read_db_path = Path(
            os.environ.get("CHATGPTREST_DASHBOARD_DB_PATH", str(DEFAULT_DASHBOARD_DB_PATH))
        ).expanduser()
        refresh_interval = max(
            5,
            _as_int(os.environ.get("CHATGPTREST_DASHBOARD_REFRESH_INTERVAL_SECONDS"), 15),
        )
        bootstrap_on_read = _as_text(
            os.environ.get("CHATGPTREST_DASHBOARD_BOOTSTRAP_ON_READ", "1")
        ).lower() not in {"0", "false", "no", "off"}
        evomap_knowledge = resolve_evomap_knowledge_read_db_path(repo_root=REPO_ROOT)
        return cls(
            job_db_path=Path(cfg.db_path).expanduser(),
            artifacts_dir=Path(cfg.artifacts_dir).expanduser(),
            read_db_path=read_db_path,
            controller_lane_db_path=Path(
                os.environ.get("CHATGPTREST_CONTROLLER_LANE_DB_PATH", str(DEFAULT_CONTROLLER_LANE_DB_PATH))
            ).expanduser(),
            openmind_kb_search_db_path=Path(resolve_openmind_kb_search_db_path()).expanduser(),
            openmind_kb_registry_db_path=Path(resolve_kb_registry_db_path()).expanduser(),
            openmind_memory_db_path=Path(
                os.environ.get("OPENMIND_MEMORY_DB", str(DEFAULT_OPENMIND_MEMORY_DB))
            ).expanduser(),
            openmind_events_db_path=Path(resolve_openmind_event_bus_db_path()).expanduser(),
            evomap_knowledge_db_path=Path(evomap_knowledge).expanduser() if evomap_knowledge else None,
            evomap_signals_db_path=Path(resolve_evomap_db_path()).expanduser(),
            refresh_interval_seconds=refresh_interval,
            bootstrap_on_read=bootstrap_on_read,
        )


class DashboardControlPlane:
    def __init__(self, config: DashboardControlPlaneConfig) -> None:
        self.config = config
        self._refresh_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._init_read_db()

    def _init_read_db(self) -> None:
        self.config.read_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.config.read_db_path), timeout=30.0)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.executescript(_DDL)
            conn.execute("INSERT OR REPLACE INTO meta(k, v) VALUES (?, ?)", ("schema_version", str(SCHEMA_VERSION)))
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def connect_read_db(self) -> Any:
        self._init_read_db()
        conn = sqlite3.connect(str(self.config.read_db_path), timeout=30.0)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=30000")
            yield conn
        finally:
            conn.close()

    def get_meta(self) -> dict[str, str]:
        with self.connect_read_db() as conn:
            return {
                str(row["k"]): str(row["v"])
                for row in conn.execute("SELECT k, v FROM meta").fetchall()
            }

    def last_refreshed_at(self) -> float:
        meta = self.get_meta()
        return _as_float(meta.get("refreshed_at"))

    def needs_refresh(self, *, now: float | None = None) -> bool:
        current = float(now if now is not None else time.time())
        refreshed_at = self.last_refreshed_at()
        if refreshed_at <= 0:
            return True
        return (current - refreshed_at) >= float(self.config.refresh_interval_seconds)

    def maybe_bootstrap(self) -> None:
        if not self.config.bootstrap_on_read:
            return
        with self.connect_read_db() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM run_index").fetchone()
            count = _as_int(row["count"] if row else 0)
        if count <= 0:
            self.refresh(force=True)
            return
        if self.needs_refresh():
            # Requests should never pay the full cross-system materialization cost once
            # a usable read model exists. When stale, refresh in the background instead.
            self.start_background_refresh()

    def start_background_refresh(self) -> None:
        if self._refresh_thread is not None and self._refresh_thread.is_alive():
            return

        def _loop() -> None:
            while not self._stop_event.is_set():
                try:
                    self.refresh(force=False)
                except Exception:
                    pass
                self._stop_event.wait(self.config.refresh_interval_seconds)

        self._stop_event.clear()
        self._refresh_thread = threading.Thread(
            target=_loop,
            name="dashboard-control-plane-refresh",
            daemon=True,
        )
        self._refresh_thread.start()

    def stop_background_refresh(self) -> None:
        self._stop_event.set()
        if self._refresh_thread is not None:
            self._refresh_thread.join(timeout=2.0)
        self._refresh_thread = None

    def refresh(self, *, force: bool = False) -> dict[str, Any]:
        now = time.time()
        if not force and not self.needs_refresh(now=now):
            return {"ok": True, "refreshed": False, "refreshed_at": self.last_refreshed_at()}
        with _MATERIALIZE_LOCK:
            now = time.time()
            if not force and not self.needs_refresh(now=now):
                return {"ok": True, "refreshed": False, "refreshed_at": self.last_refreshed_at()}
            source = self._load_sources()
            payload = self._build_materialized_payload(source=source, now=now)
            self._write_payload(payload=payload, now=now, source_summary=source["source_summary"])
            return {
                "ok": True,
                "refreshed": True,
                "refreshed_at": now,
                "source_summary": source["source_summary"],
                "root_count": len(payload["run_index"]),
            }

    def _write_payload(
        self,
        *,
        payload: dict[str, list[dict[str, Any]]],
        now: float,
        source_summary: dict[str, Any],
    ) -> None:
        with self.connect_read_db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for table_name in (
                "identity_map",
                "canonical_events",
                "run_index",
                "run_timeline",
                "component_health",
                "incident_index",
                "cognitive_snapshot",
            ):
                conn.execute(f"DELETE FROM {table_name}")

            conn.executemany(
                """
                INSERT INTO identity_map (
                  identity_key, root_run_id, entity_type, entity_id, source_system,
                  task_id, task_ref, trace_id, run_id, job_id, lane_id, team_run_id,
                  role_name, checkpoint_id, issue_id, incident_id, ingress_channel,
                  session_id, thread_id, tenant_id, team_id, user_id, updated_at,
                  metadata_json
                ) VALUES (
                  :identity_key, :root_run_id, :entity_type, :entity_id, :source_system,
                  :task_id, :task_ref, :trace_id, :run_id, :job_id, :lane_id, :team_run_id,
                  :role_name, :checkpoint_id, :issue_id, :incident_id, :ingress_channel,
                  :session_id, :thread_id, :tenant_id, :team_id, :user_id, :updated_at,
                  :metadata_json
                )
                """,
                payload["identity_map"],
            )
            conn.executemany(
                """
                INSERT INTO canonical_events (
                  event_key, root_run_id, source_system, layer, entity_type, entity_id,
                  event_type, status, severity, ts, summary, payload_json
                ) VALUES (
                  :event_key, :root_run_id, :source_system, :layer, :entity_type, :entity_id,
                  :event_type, :status, :severity, :ts, :summary, :payload_json
                )
                """,
                payload["canonical_events"],
            )
            conn.executemany(
                """
                INSERT INTO run_index (
                  root_run_id, root_entity_type, task_id, task_ref, title, ingress_channel,
                  session_id, thread_id, tenant_id, team_id, user_id, trace_id, run_id,
                  job_id, job_kind, job_phase, job_status, lane_id, lane_status, team_run_id,
                  role_name, checkpoint_id, issue_id, incident_id, current_layer, current_status,
                  current_owner, problem_class, health_tone, upstream_json, downstream_json,
                  entity_counts_json, summary_json, created_at, last_progress_at, updated_at
                ) VALUES (
                  :root_run_id, :root_entity_type, :task_id, :task_ref, :title, :ingress_channel,
                  :session_id, :thread_id, :tenant_id, :team_id, :user_id, :trace_id, :run_id,
                  :job_id, :job_kind, :job_phase, :job_status, :lane_id, :lane_status, :team_run_id,
                  :role_name, :checkpoint_id, :issue_id, :incident_id, :current_layer, :current_status,
                  :current_owner, :problem_class, :health_tone, :upstream_json, :downstream_json,
                  :entity_counts_json, :summary_json, :created_at, :last_progress_at, :updated_at
                )
                """,
                payload["run_index"],
            )
            conn.executemany(
                """
                INSERT INTO run_timeline (
                  root_run_id, event_rank, ts, layer, source_system, entity_type, entity_id,
                  event_type, status, severity, summary, payload_json
                ) VALUES (
                  :root_run_id, :event_rank, :ts, :layer, :source_system, :entity_type, :entity_id,
                  :event_type, :status, :severity, :summary, :payload_json
                )
                """,
                payload["run_timeline"],
            )
            conn.executemany(
                """
                INSERT INTO component_health (
                  component_key, plane, label, status, severity, ok, guard_family,
                  attention_reason, blast_radius, signal_ts, summary, details_json
                ) VALUES (
                  :component_key, :plane, :label, :status, :severity, :ok, :guard_family,
                  :attention_reason, :blast_radius, :signal_ts, :summary, :details_json
                )
                """,
                payload["component_health"],
            )
            conn.executemany(
                """
                INSERT INTO incident_index (
                  incident_key, incident_type, incident_id, root_run_id, job_id, issue_id,
                  project, category, severity, status, title, summary, blast_radius,
                  guard_source, updated_at, metadata_json
                ) VALUES (
                  :incident_key, :incident_type, :incident_id, :root_run_id, :job_id, :issue_id,
                  :project, :category, :severity, :status, :title, :summary, :blast_radius,
                  :guard_source, :updated_at, :metadata_json
                )
                """,
                payload["incident_index"],
            )
            conn.executemany(
                """
                INSERT INTO cognitive_snapshot (
                  snapshot_key, scope, root_run_id, kind, ts, summary_json, details_json
                ) VALUES (
                  :snapshot_key, :scope, :root_run_id, :kind, :ts, :summary_json, :details_json
                )
                """,
                payload["cognitive_snapshot"],
            )
            conn.execute("INSERT OR REPLACE INTO meta(k, v) VALUES (?, ?)", ("schema_version", str(SCHEMA_VERSION)))
            conn.execute("INSERT OR REPLACE INTO meta(k, v) VALUES (?, ?)", ("refreshed_at", str(now)))
            conn.execute("INSERT OR REPLACE INTO meta(k, v) VALUES (?, ?)", ("refresh_status", "ok"))
            conn.execute("INSERT OR REPLACE INTO meta(k, v) VALUES (?, ?)", ("source_summary_json", _json_dumps(source_summary)))
            conn.execute("INSERT OR REPLACE INTO meta(k, v) VALUES (?, ?)", ("root_count", str(len(payload["run_index"]))))
            conn.commit()

    def _load_sources(self) -> dict[str, Any]:
        source_summary: dict[str, Any] = {}
        tasks: list[dict[str, Any]] = []
        task_links: list[dict[str, Any]] = []
        task_messages: list[dict[str, Any]] = []
        jobs: list[dict[str, Any]] = []
        job_events: list[dict[str, Any]] = []
        advisor_runs: list[dict[str, Any]] = []
        advisor_steps: list[dict[str, Any]] = []
        advisor_events: list[dict[str, Any]] = []
        client_issues: list[dict[str, Any]] = []
        client_issue_events: list[dict[str, Any]] = []
        incidents: list[dict[str, Any]] = []

        with connect_jobdb(self.config.job_db_path) as conn:
            if _table_exists(conn, "tasks"):
                tasks = _rows_to_dicts(conn.execute("SELECT * FROM tasks").fetchall())
            if _table_exists(conn, "task_links"):
                task_links = _rows_to_dicts(conn.execute("SELECT * FROM task_links").fetchall())
            if _table_exists(conn, "task_messages"):
                task_messages = _rows_to_dicts(conn.execute("SELECT * FROM task_messages").fetchall())
            if _table_exists(conn, "jobs"):
                jobs = _rows_to_dicts(conn.execute("SELECT * FROM jobs").fetchall())
            if _table_exists(conn, "advisor_runs"):
                advisor_runs = _rows_to_dicts(conn.execute("SELECT * FROM advisor_runs").fetchall())
            if _table_exists(conn, "advisor_steps"):
                advisor_steps = _rows_to_dicts(conn.execute("SELECT * FROM advisor_steps").fetchall())
            if _table_exists(conn, "client_issues"):
                client_issues = _rows_to_dicts(conn.execute("SELECT * FROM client_issues").fetchall())
            if _table_exists(conn, "client_issue_events"):
                client_issue_events = _rows_to_dicts(
                    conn.execute(
                        "SELECT * FROM client_issue_events ORDER BY ts DESC LIMIT 1000"
                    ).fetchall()
                )
            if _table_exists(conn, "incidents"):
                incidents = _rows_to_dicts(conn.execute("SELECT * FROM incidents").fetchall())

            relevant_job_ids = self._relevant_job_ids(
                jobs=jobs,
                task_links=task_links,
                advisor_runs=advisor_runs,
                advisor_steps=advisor_steps,
                client_issues=client_issues,
                incidents=incidents,
            )
            relevant_run_ids = {
                _as_text(row.get("run_id"))
                for row in advisor_runs
                if _as_text(row.get("run_id"))
            }
            if relevant_job_ids and _table_exists(conn, "job_events"):
                job_events = self._load_recent_events(
                    conn=conn,
                    table_name="job_events",
                    entity_column="job_id",
                    entities=sorted(relevant_job_ids),
                    order_column="ts",
                    per_entity_limit=25,
                )
            if relevant_run_ids and _table_exists(conn, "advisor_events"):
                advisor_events = self._load_recent_events(
                    conn=conn,
                    table_name="advisor_events",
                    entity_column="run_id",
                    entities=sorted(relevant_run_ids),
                    order_column="ts",
                    per_entity_limit=25,
                )

        lanes: list[dict[str, Any]] = []
        lane_events: list[dict[str, Any]] = []
        with _open_sqlite(self.config.controller_lane_db_path) as lane_conn:
            if _table_exists(lane_conn, "lanes"):
                lanes = _rows_to_dicts(lane_conn.execute("SELECT * FROM lanes").fetchall())
            if _table_exists(lane_conn, "lane_events"):
                lane_events = _rows_to_dicts(lane_conn.execute("SELECT * FROM lane_events").fetchall())

        team_runs: list[dict[str, Any]] = []
        team_role_runs: list[dict[str, Any]] = []
        team_checkpoints: list[dict[str, Any]] = []
        with _open_sqlite(self.config.evomap_signals_db_path) as team_conn:
            if _table_exists(team_conn, "team_runs"):
                team_runs = _rows_to_dicts(team_conn.execute("SELECT * FROM team_runs").fetchall())
            if _table_exists(team_conn, "team_role_runs"):
                team_role_runs = _rows_to_dicts(team_conn.execute("SELECT * FROM team_role_runs").fetchall())
            if _table_exists(team_conn, "team_checkpoints"):
                team_checkpoints = _rows_to_dicts(team_conn.execute("SELECT * FROM team_checkpoints").fetchall())

        openmind = self._openmind_summary()
        runtime_reports = self._runtime_reports()

        source_summary.update(
            {
                "tasks": len(tasks),
                "task_links": len(task_links),
                "task_messages": len(task_messages),
                "jobs": len(jobs),
                "job_events": len(job_events),
                "advisor_runs": len(advisor_runs),
                "advisor_steps": len(advisor_steps),
                "advisor_events": len(advisor_events),
                "client_issues": len(client_issues),
                "client_issue_events": len(client_issue_events),
                "incidents": len(incidents),
                "lanes": len(lanes),
                "lane_events": len(lane_events),
                "team_runs": len(team_runs),
                "team_role_runs": len(team_role_runs),
                "team_checkpoints": len(team_checkpoints),
                "openmind": openmind,
            }
        )

        return {
            "source_summary": source_summary,
            "tasks": tasks,
            "task_links": task_links,
            "task_messages": task_messages,
            "jobs": jobs,
            "job_events": job_events,
            "advisor_runs": advisor_runs,
            "advisor_steps": advisor_steps,
            "advisor_events": advisor_events,
            "client_issues": client_issues,
            "client_issue_events": client_issue_events,
            "incidents": incidents,
            "lanes": lanes,
            "lane_events": lane_events,
            "team_runs": team_runs,
            "team_role_runs": team_role_runs,
            "team_checkpoints": team_checkpoints,
            "openmind": openmind,
            "runtime_reports": runtime_reports,
        }

    def _load_recent_events(
        self,
        *,
        conn: sqlite3.Connection,
        table_name: str,
        entity_column: str,
        entities: list[str],
        order_column: str,
        per_entity_limit: int,
    ) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        counters: dict[str, int] = {}
        chunk_size = 200
        for offset in range(0, len(entities), chunk_size):
            chunk = entities[offset : offset + chunk_size]
            if not chunk:
                continue
            placeholders, params = _sql_in_clause(chunk)
            query = (
                f"SELECT * FROM {table_name} "
                f"WHERE {entity_column} IN ({placeholders}) "
                f"ORDER BY {order_column} DESC"
            )
            for row in conn.execute(query, params).fetchall():
                item = dict(row)
                entity_id = _as_text(item.get(entity_column))
                seen = counters.get(entity_id, 0)
                if seen >= per_entity_limit:
                    continue
                counters[entity_id] = seen + 1
                collected.append(item)
        return collected

    def _relevant_job_ids(
        self,
        *,
        jobs: list[dict[str, Any]],
        task_links: list[dict[str, Any]],
        advisor_runs: list[dict[str, Any]],
        advisor_steps: list[dict[str, Any]],
        client_issues: list[dict[str, Any]],
        incidents: list[dict[str, Any]],
    ) -> set[str]:
        relevant: set[str] = set()
        for row in jobs:
            status = _as_text(row.get("status")).lower()
            updated_at = _as_float(row.get("updated_at"))
            if status not in {"completed", "canceled"}:
                relevant.add(_as_text(row.get("job_id")))
            elif updated_at >= (time.time() - 86400):
                relevant.add(_as_text(row.get("job_id")))
        recent_jobs = sorted(jobs, key=lambda row: _as_float(row.get("updated_at")), reverse=True)[:200]
        for row in recent_jobs:
            relevant.add(_as_text(row.get("job_id")))
        for row in task_links:
            relevant.add(_as_text(row.get("job_id")))
        for row in advisor_runs:
            relevant.add(_as_text(row.get("final_job_id")))
            relevant.add(_as_text(row.get("orchestrate_job_id")))
        for row in advisor_steps:
            relevant.add(_as_text(row.get("job_id")))
        for row in client_issues:
            relevant.add(_as_text(row.get("latest_job_id")))
        for row in incidents:
            for job_id in _safe_json_loads(row.get("job_ids_json"), default=[]):
                relevant.add(_as_text(job_id))
        return {job_id for job_id in relevant if job_id}

    def _openmind_summary(self) -> dict[str, Any]:
        summary = {
            "kb_search_docs": 0,
            "kb_registry_artifacts": 0,
            "memory_records": 0,
            "event_rows": 0,
            "signal_rows": 0,
            "knowledge_entities": 0,
            "knowledge_edges": 0,
            "knowledge_atoms": 0,
        }
        with _open_sqlite(self.config.openmind_kb_search_db_path) as conn:
            if _table_exists(conn, "kb_fts"):
                row = conn.execute("SELECT COUNT(*) AS count FROM kb_fts").fetchone()
                summary["kb_search_docs"] = _as_int(row["count"] if row else 0)
        with _open_sqlite(self.config.openmind_kb_registry_db_path) as conn:
            if _table_exists(conn, "artifacts"):
                row = conn.execute("SELECT COUNT(*) AS count FROM artifacts").fetchone()
                summary["kb_registry_artifacts"] = _as_int(row["count"] if row else 0)
        with _open_sqlite(self.config.openmind_memory_db_path) as conn:
            if _table_exists(conn, "memory_records"):
                row = conn.execute("SELECT COUNT(*) AS count FROM memory_records").fetchone()
                summary["memory_records"] = _as_int(row["count"] if row else 0)
        with _open_sqlite(self.config.openmind_events_db_path) as conn:
            if _table_exists(conn, "trace_events"):
                row = conn.execute("SELECT COUNT(*) AS count FROM trace_events").fetchone()
                summary["event_rows"] = _as_int(row["count"] if row else 0)
        with _open_sqlite(self.config.evomap_signals_db_path) as conn:
            if _table_exists(conn, "signals"):
                row = conn.execute("SELECT COUNT(*) AS count FROM signals").fetchone()
                summary["signal_rows"] = _as_int(row["count"] if row else 0)
        with _open_sqlite(self.config.evomap_knowledge_db_path) as conn:
            if _table_exists(conn, "entities"):
                row = conn.execute("SELECT COUNT(*) AS count FROM entities").fetchone()
                summary["knowledge_entities"] = _as_int(row["count"] if row else 0)
            if _table_exists(conn, "edges"):
                row = conn.execute("SELECT COUNT(*) AS count FROM edges").fetchone()
                summary["knowledge_edges"] = _as_int(row["count"] if row else 0)
            if _table_exists(conn, "atoms"):
                row = conn.execute("SELECT COUNT(*) AS count FROM atoms").fetchone()
                summary["knowledge_atoms"] = _as_int(row["count"] if row else 0)
        return summary

    def _runtime_reports(self) -> dict[str, Any]:
        artifacts_dir = self.config.artifacts_dir
        guardian = _read_json_file(artifacts_dir / "monitor" / "openclaw_guardian" / "latest_report.json") or {}
        orch = _read_json_file(artifacts_dir / "monitor" / "openclaw_orch" / "latest_report.json") or {}
        ui_canary = _read_json_file(artifacts_dir / "monitor" / "ui_canary" / "latest.json") or {}
        viewer = self._viewer_health()
        runtime_guard = _read_json_file(artifacts_dir / "monitor" / "openclaw_runtime_guard" / "latest.json") or {}
        return {
            "guardian": guardian,
            "orch": orch,
            "ui_canary": ui_canary,
            "viewer": viewer,
            "runtime_guard": runtime_guard,
        }

    def _viewer_health(self) -> dict[str, Any]:
        run_dir = REPO_ROOT / ".run" / "viewer"
        chrome_pid_file = run_dir / "chrome.pid"
        x11vnc_pid_file = run_dir / "x11vnc.pid"
        websockify_pid_file = run_dir / "websockify.pid"
        viewer_vnc_port = _as_int(os.environ.get("VIEWER_VNC_PORT"), 5902)
        viewer_novnc_port = _as_int(os.environ.get("VIEWER_NOVNC_PORT"), 6082)
        novnc_host = _as_text(os.environ.get("VIEWER_NOVNC_BIND_HOST") or "127.0.0.1") or "127.0.0.1"

        def _pid_alive(pid_file: Path) -> bool:
            try:
                raw = pid_file.read_text(encoding="utf-8", errors="replace").strip()
                pid = int(raw)
                if pid <= 1:
                    return False
                os.kill(pid, 0)
                return True
            except Exception:
                return False

        def _port_open(host: str, port: int) -> bool:
            import socket

            try:
                with socket.create_connection((host, int(port)), timeout=1.5):
                    return True
            except Exception:
                return False

        chrome_running = _pid_alive(chrome_pid_file)
        x11vnc_running = _pid_alive(x11vnc_pid_file)
        websockify_running = _pid_alive(websockify_pid_file)
        vnc_listening = _port_open("127.0.0.1", viewer_vnc_port)
        novnc_listening = _port_open("127.0.0.1", viewer_novnc_port)
        ok = bool(chrome_running and x11vnc_running and websockify_running and vnc_listening and novnc_listening)
        return {
            "ok": ok,
            "chrome_running": chrome_running,
            "x11vnc_running": x11vnc_running,
            "websockify_running": websockify_running,
            "vnc_listening": vnc_listening,
            "novnc_listening": novnc_listening,
            "novnc_host": novnc_host,
            "checked_at": time.time(),
        }

    def _build_materialized_payload(self, *, source: dict[str, Any], now: float) -> dict[str, list[dict[str, Any]]]:
        tasks = source["tasks"]
        task_links = source["task_links"]
        task_messages = source["task_messages"]
        jobs = source["jobs"]
        job_events = source["job_events"]
        advisor_runs = source["advisor_runs"]
        advisor_steps = source["advisor_steps"]
        advisor_events = source["advisor_events"]
        client_issues = source["client_issues"]
        client_issue_events = source["client_issue_events"]
        incidents = source["incidents"]
        lanes = source["lanes"]
        lane_events = source["lane_events"]
        team_runs = source["team_runs"]
        team_role_runs = source["team_role_runs"]
        team_checkpoints = source["team_checkpoints"]

        task_by_id = { _as_text(row.get("task_id")): row for row in tasks if _as_text(row.get("task_id")) }
        task_by_ref = { _as_text(row.get("task_ref")): row for row in tasks if _as_text(row.get("task_ref")) }
        run_by_id = { _as_text(row.get("run_id")): row for row in advisor_runs if _as_text(row.get("run_id")) }
        job_by_id = { _as_text(row.get("job_id")): row for row in jobs if _as_text(row.get("job_id")) }
        issue_by_id = { _as_text(row.get("issue_id")): row for row in client_issues if _as_text(row.get("issue_id")) }
        lane_by_id = { _as_text(row.get("lane_id")): row for row in lanes if _as_text(row.get("lane_id")) }
        team_run_by_id = { _as_text(row.get("team_run_id")): row for row in team_runs if _as_text(row.get("team_run_id")) }
        incident_by_id = { _as_text(row.get("incident_id")): row for row in incidents if _as_text(row.get("incident_id")) }

        uf = _UnionFind()

        def _join_many(entity_keys: list[str]) -> None:
            filtered = [key for key in entity_keys if key]
            if len(filtered) < 2:
                for key in filtered:
                    uf.add(key)
                return
            first = filtered[0]
            for key in filtered:
                uf.union(first, key)

        for row in tasks:
            task_id = _as_text(row.get("task_id"))
            if not task_id:
                continue
            task_key = f"task:{task_id}"
            _join_many(
                [
                    task_key,
                    f"run:{_as_text(row.get('current_run_id'))}" if _as_text(row.get("current_run_id")) else "",
                    f"issue:{_as_text(row.get('latest_issue_id'))}" if _as_text(row.get("latest_issue_id")) else "",
                    (
                        f"session:{_as_text(row.get('source_channel'))}:{_as_text(row.get('source_session_id'))}"
                        if _as_text(row.get("source_session_id"))
                        else ""
                    ),
                ]
            )

        for row in task_links:
            _join_many(
                [
                    f"task:{_as_text(row.get('task_id'))}" if _as_text(row.get("task_id")) else "",
                    f"run:{_as_text(row.get('run_id'))}" if _as_text(row.get("run_id")) else "",
                    f"job:{_as_text(row.get('job_id'))}" if _as_text(row.get("job_id")) else "",
                    f"issue:{_as_text(row.get('issue_id'))}" if _as_text(row.get("issue_id")) else "",
                    f"lane:{_as_text(row.get('lane_id'))}" if _as_text(row.get("lane_id")) else "",
                    f"trace:{_as_text(row.get('trace_id'))}" if _as_text(row.get("trace_id")) else "",
                ]
            )

        for row in advisor_runs:
            run_id = _as_text(row.get("run_id"))
            task_id = _as_text(row.get("task_id"))
            task_ref = _as_text(row.get("task_ref"))
            _join_many(
                [
                    f"run:{run_id}" if run_id else "",
                    f"task:{task_id}" if task_id else (
                        f"task:{_as_text(task_by_ref[task_ref].get('task_id'))}"
                        if task_ref and task_ref in task_by_ref
                        else ""
                    ),
                    f"job:{_as_text(row.get('final_job_id'))}" if _as_text(row.get("final_job_id")) else "",
                    f"job:{_as_text(row.get('orchestrate_job_id'))}" if _as_text(row.get("orchestrate_job_id")) else "",
                ]
            )

        for row in advisor_steps:
            _join_many(
                [
                    f"run:{_as_text(row.get('run_id'))}" if _as_text(row.get("run_id")) else "",
                    f"job:{_as_text(row.get('job_id'))}" if _as_text(row.get("job_id")) else "",
                ]
            )

        for row in jobs:
            job_id = _as_text(row.get("job_id"))
            client = _safe_json_loads(row.get("client_json"), default={})
            input_obj = _safe_json_loads(row.get("input_json"), default={})
            params_obj = _safe_json_loads(row.get("params_json"), default={})
            trace_id = _as_text(client.get("trace_id") or input_obj.get("trace_id") or params_obj.get("trace_id"))
            session_id = _as_text(client.get("session_id") or input_obj.get("session_id"))
            thread_id = _as_text(client.get("thread_id") or input_obj.get("thread_id"))
            task_id = _as_text(input_obj.get("task_id"))
            run_id = _as_text(input_obj.get("run_id") or params_obj.get("run_id"))
            team_run_id = _as_text(input_obj.get("team_run_id") or params_obj.get("team_run_id"))
            _join_many(
                [
                    f"job:{job_id}" if job_id else "",
                    f"job:{_as_text(row.get('parent_job_id'))}" if _as_text(row.get("parent_job_id")) else "",
                    f"trace:{trace_id}" if trace_id else "",
                    f"session:{session_id}" if session_id else "",
                    f"thread:{thread_id}" if thread_id else "",
                    f"task:{task_id}" if task_id else "",
                    f"run:{run_id}" if run_id else "",
                    f"teamrun:{team_run_id}" if team_run_id else "",
                ]
            )

        issue_columns = {key for row in client_issues for key in row.keys()}
        for row in client_issues:
            task_id = _as_text(row.get("task_id")) if "task_id" in issue_columns else ""
            task_ref = _as_text(row.get("task_ref")) if "task_ref" in issue_columns else ""
            run_id = _as_text(row.get("run_id")) if "run_id" in issue_columns else ""
            _join_many(
                [
                    f"issue:{_as_text(row.get('issue_id'))}" if _as_text(row.get("issue_id")) else "",
                    f"job:{_as_text(row.get('latest_job_id'))}" if _as_text(row.get("latest_job_id")) else "",
                    f"task:{task_id}" if task_id else (
                        f"task:{_as_text(task_by_ref[task_ref].get('task_id'))}"
                        if task_ref and task_ref in task_by_ref
                        else ""
                    ),
                    f"run:{run_id}" if run_id else "",
                ]
            )

        for row in incidents:
            keys = [f"incident:{_as_text(row.get('incident_id'))}" if _as_text(row.get("incident_id")) else ""]
            for job_id in _safe_json_loads(row.get("job_ids_json"), default=[]):
                if _as_text(job_id):
                    keys.append(f"job:{_as_text(job_id)}")
            _join_many(keys)

        for row in lanes:
            keys = [
                f"lane:{_as_text(row.get('lane_id'))}" if _as_text(row.get("lane_id")) else "",
                f"session:{_as_text(row.get('session_key'))}" if _as_text(row.get("session_key")) else "",
            ]
            _join_many(keys)

        for row in lane_events:
            payload = _safe_json_loads(row.get("payload_json"), default={})
            keys = [
                f"lane:{_as_text(row.get('lane_id'))}" if _as_text(row.get("lane_id")) else "",
                f"task:{_as_text(payload.get('task_id'))}" if _as_text(payload.get("task_id")) else "",
                f"run:{_as_text(payload.get('run_id'))}" if _as_text(payload.get("run_id")) else "",
                f"job:{_as_text(payload.get('job_id'))}" if _as_text(payload.get("job_id")) else "",
                f"trace:{_as_text(payload.get('trace_id'))}" if _as_text(payload.get("trace_id")) else "",
                f"teamrun:{_as_text(payload.get('team_run_id'))}" if _as_text(payload.get("team_run_id")) else "",
            ]
            _join_many(keys)

        for row in team_runs:
            _join_many(
                [
                    f"teamrun:{_as_text(row.get('team_run_id'))}" if _as_text(row.get("team_run_id")) else "",
                    f"trace:{_as_text(row.get('trace_id'))}" if _as_text(row.get("trace_id")) else "",
                ]
            )

        for row in team_role_runs:
            team_run_id = _as_text(row.get("team_run_id"))
            role_name = _as_text(row.get("role_name"))
            _join_many(
                [
                    f"teamrun:{team_run_id}" if team_run_id else "",
                    f"role:{team_run_id}:{role_name}" if team_run_id and role_name else "",
                ]
            )

        for row in team_checkpoints:
            team_run_id = _as_text(row.get("team_run_id"))
            checkpoint_id = _as_text(row.get("checkpoint_id"))
            _join_many(
                [
                    f"teamrun:{team_run_id}" if team_run_id else "",
                    f"checkpoint:{checkpoint_id}" if checkpoint_id else "",
                ]
            )

        groups = uf.groups()
        entity_root_map: dict[str, str] = {}
        component_members: dict[str, list[str]] = {}
        for group_keys in groups.values():
            root_key = self._choose_root_key(
                entity_keys=group_keys,
                task_by_id=task_by_id,
                run_by_id=run_by_id,
                job_by_id=job_by_id,
                issue_by_id=issue_by_id,
                lane_by_id=lane_by_id,
                team_run_by_id=team_run_by_id,
                incident_by_id=incident_by_id,
            )
            component_members[root_key] = sorted(group_keys)
            for key in group_keys:
                entity_root_map[key] = root_key

        by_root: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for root_key in component_members:
            by_root[root_key] = {
                "tasks": [],
                "task_links": [],
                "task_messages": [],
                "runs": [],
                "steps": [],
                "jobs": [],
                "job_events": [],
                "advisor_events": [],
                "issues": [],
                "issue_events": [],
                "incidents": [],
                "lanes": [],
                "lane_events": [],
                "team_runs": [],
                "team_role_runs": [],
                "team_checkpoints": [],
                "members": component_members[root_key],
            }

        def _append_by_entity(entity_key: str, bucket: str, row: dict[str, Any]) -> None:
            root_key = entity_root_map.get(entity_key)
            if not root_key:
                return
            by_root[root_key][bucket].append(row)

        for row in tasks:
            task_id = _as_text(row.get("task_id"))
            if task_id:
                _append_by_entity(f"task:{task_id}", "tasks", row)
        for row in task_links:
            task_id = _as_text(row.get("task_id"))
            if task_id:
                _append_by_entity(f"task:{task_id}", "task_links", row)
        for row in task_messages:
            task_id = _as_text(row.get("task_id"))
            if task_id:
                _append_by_entity(f"task:{task_id}", "task_messages", row)
        for row in advisor_runs:
            run_id = _as_text(row.get("run_id"))
            if run_id:
                _append_by_entity(f"run:{run_id}", "runs", row)
        for row in advisor_steps:
            run_id = _as_text(row.get("run_id"))
            if run_id:
                _append_by_entity(f"run:{run_id}", "steps", row)
        for row in jobs:
            job_id = _as_text(row.get("job_id"))
            if job_id:
                _append_by_entity(f"job:{job_id}", "jobs", row)
        for row in job_events:
            job_id = _as_text(row.get("job_id"))
            if job_id:
                _append_by_entity(f"job:{job_id}", "job_events", row)
        for row in advisor_events:
            run_id = _as_text(row.get("run_id"))
            if run_id:
                _append_by_entity(f"run:{run_id}", "advisor_events", row)
        for row in client_issues:
            issue_id = _as_text(row.get("issue_id"))
            if issue_id:
                _append_by_entity(f"issue:{issue_id}", "issues", row)
        for row in client_issue_events:
            issue_id = _as_text(row.get("issue_id"))
            if issue_id:
                _append_by_entity(f"issue:{issue_id}", "issue_events", row)
        for row in incidents:
            incident_id = _as_text(row.get("incident_id"))
            if incident_id:
                _append_by_entity(f"incident:{incident_id}", "incidents", row)
        for row in lanes:
            lane_id = _as_text(row.get("lane_id"))
            if lane_id:
                _append_by_entity(f"lane:{lane_id}", "lanes", row)
        for row in lane_events:
            lane_id = _as_text(row.get("lane_id"))
            if lane_id:
                _append_by_entity(f"lane:{lane_id}", "lane_events", row)
        for row in team_runs:
            team_run_id = _as_text(row.get("team_run_id"))
            if team_run_id:
                _append_by_entity(f"teamrun:{team_run_id}", "team_runs", row)
        for row in team_role_runs:
            team_run_id = _as_text(row.get("team_run_id"))
            if team_run_id:
                _append_by_entity(f"teamrun:{team_run_id}", "team_role_runs", row)
        for row in team_checkpoints:
            team_run_id = _as_text(row.get("team_run_id"))
            if team_run_id:
                _append_by_entity(f"teamrun:{team_run_id}", "team_checkpoints", row)

        identity_rows: list[dict[str, Any]] = []
        canonical_events: list[dict[str, Any]] = []
        run_index_rows: list[dict[str, Any]] = []
        run_timeline_rows: list[dict[str, Any]] = []
        incident_rows: list[dict[str, Any]] = []
        cognitive_rows: list[dict[str, Any]] = []

        for root_key, component in by_root.items():
            identity_rows.extend(self._build_identity_rows(root_key=root_key, component=component, now=now))
            events = self._build_component_events(root_key=root_key, component=component, now=now)
            canonical_events.extend(events)
            run_row = self._build_run_index_row(root_key=root_key, component=component, now=now)
            if run_row is not None:
                run_index_rows.append(run_row)
            run_timeline_rows.extend(self._build_timeline_rows(root_key=root_key, events=events))
            incident_rows.extend(self._build_component_incident_rows(root_key=root_key, component=component))
            cognitive_rows.extend(
                self._build_component_cognitive_rows(
                    root_key=root_key,
                    component=component,
                    run_row=run_row,
                    now=now,
                )
            )

        component_health = self._build_component_health(
            runs=run_index_rows,
            incident_rows=incident_rows,
            runtime_reports=source["runtime_reports"],
            openmind=source["openmind"],
            jobs=jobs,
            now=now,
        )
        cognitive_rows.extend(self._build_global_cognitive_rows(openmind=source["openmind"], now=now))

        return {
            "identity_map": identity_rows,
            "canonical_events": canonical_events,
            "run_index": run_index_rows,
            "run_timeline": run_timeline_rows,
            "component_health": component_health,
            "incident_index": incident_rows,
            "cognitive_snapshot": cognitive_rows,
        }

    def _entity_updated_at(
        self,
        *,
        entity_key: str,
        task_by_id: dict[str, dict[str, Any]],
        run_by_id: dict[str, dict[str, Any]],
        job_by_id: dict[str, dict[str, Any]],
        issue_by_id: dict[str, dict[str, Any]],
        lane_by_id: dict[str, dict[str, Any]],
        team_run_by_id: dict[str, dict[str, Any]],
        incident_by_id: dict[str, dict[str, Any]],
    ) -> float:
        entity_type, _, entity_id = entity_key.partition(":")
        if entity_type == "task":
            row = task_by_id.get(entity_id)
        elif entity_type == "run":
            row = run_by_id.get(entity_id)
        elif entity_type == "job":
            row = job_by_id.get(entity_id)
        elif entity_type == "issue":
            row = issue_by_id.get(entity_id)
        elif entity_type == "lane":
            row = lane_by_id.get(entity_id)
        elif entity_type == "teamrun":
            row = team_run_by_id.get(entity_id)
        elif entity_type == "incident":
            row = incident_by_id.get(entity_id)
        else:
            row = None
        if not row:
            return 0.0
        return max(
            _as_float(row.get("updated_at")),
            _as_float(row.get("last_seen_at")),
            _as_float(row.get("heartbeat_at")),
            _as_float(row.get("created_at")),
            _as_float(row.get("started_at")),
        )

    def _choose_root_key(
        self,
        *,
        entity_keys: list[str],
        task_by_id: dict[str, dict[str, Any]],
        run_by_id: dict[str, dict[str, Any]],
        job_by_id: dict[str, dict[str, Any]],
        issue_by_id: dict[str, dict[str, Any]],
        lane_by_id: dict[str, dict[str, Any]],
        team_run_by_id: dict[str, dict[str, Any]],
        incident_by_id: dict[str, dict[str, Any]],
    ) -> str:
        priorities = {
            "task": 0,
            "trace": 1,
            "run": 2,
            "teamrun": 3,
            "job": 4,
            "lane": 5,
            "issue": 6,
            "incident": 7,
            "session": 8,
            "thread": 9,
            "role": 10,
            "checkpoint": 11,
        }

        def _sort_key(entity_key: str) -> tuple[int, float, str]:
            entity_type, _, _ = entity_key.partition(":")
            priority = priorities.get(entity_type, 99)
            updated_at = self._entity_updated_at(
                entity_key=entity_key,
                task_by_id=task_by_id,
                run_by_id=run_by_id,
                job_by_id=job_by_id,
                issue_by_id=issue_by_id,
                lane_by_id=lane_by_id,
                team_run_by_id=team_run_by_id,
                incident_by_id=incident_by_id,
            )
            return (priority, -updated_at, entity_key)

        return sorted(entity_keys, key=_sort_key)[0]

    def _build_identity_rows(self, *, root_key: str, component: dict[str, list[dict[str, Any]]], now: float) -> list[dict[str, Any]]:
        task_row = _pick_latest(component["tasks"], status_fields=("status",), preferred={"running", "completed"})
        run_row = _pick_latest(component["runs"], status_fields=("status",), preferred={"running", "completed"})
        job_row = _pick_latest(component["jobs"], status_fields=("status",), preferred={"in_progress", "completed", "error"})
        lane_row = _pick_latest(component["lanes"], status_fields=("run_state",), preferred={"working", "idle", "completed"})
        issue_row = _pick_latest(component["issues"], status_fields=("status",), preferred={"open", "in_progress", "resolved"})
        incident_row = _pick_latest(component["incidents"], status_fields=("status",), preferred={"open", "resolved"})
        team_run_row = _pick_latest(component["team_runs"], status_fields=("status",), preferred={"running", "completed"})

        task_id = _as_text((task_row or {}).get("task_id"))
        task_ref = _as_text((task_row or {}).get("task_ref"))
        trace_id = self._component_trace_id(component=component)
        run_id = _as_text((run_row or {}).get("run_id"))
        job_id = _as_text((job_row or {}).get("job_id"))
        lane_id = _as_text((lane_row or {}).get("lane_id"))
        team_run_id = _as_text((team_run_row or {}).get("team_run_id"))
        issue_id = _as_text((issue_row or {}).get("issue_id"))
        incident_id = _as_text((incident_row or {}).get("incident_id"))
        ingress = self._component_ingress(component=component)

        rows: list[dict[str, Any]] = []
        for member in component["members"]:
            entity_type, _, entity_id = member.partition(":")
            role_name = ""
            checkpoint_id = ""
            source_system = entity_type
            if entity_type == "role":
                _, _, suffix = member.partition(":")
                team_run_id, _, role_name = suffix.partition(":")
                source_system = "team_control_plane"
            elif entity_type == "checkpoint":
                checkpoint_id = entity_id
                source_system = "team_control_plane"
            elif entity_type in {"task", "run", "job", "issue", "incident"}:
                source_system = "chatgptrest"
            elif entity_type == "lane":
                source_system = "controller"
            elif entity_type == "trace":
                source_system = "identity"
            elif entity_type in {"session", "thread"}:
                source_system = "ingress"
            elif entity_type == "teamrun":
                source_system = "team_control_plane"

            rows.append(
                {
                    "identity_key": member,
                    "root_run_id": root_key,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "source_system": source_system,
                    "task_id": task_id or None,
                    "task_ref": task_ref or None,
                    "trace_id": trace_id or None,
                    "run_id": run_id or None,
                    "job_id": job_id or None,
                    "lane_id": lane_id or None,
                    "team_run_id": team_run_id or None,
                    "role_name": role_name or None,
                    "checkpoint_id": checkpoint_id or None,
                    "issue_id": issue_id or None,
                    "incident_id": incident_id or None,
                    "ingress_channel": ingress.get("channel") or None,
                    "session_id": ingress.get("session_id") or None,
                    "thread_id": ingress.get("thread_id") or None,
                    "tenant_id": ingress.get("tenant_id") or None,
                    "team_id": ingress.get("team_id") or None,
                    "user_id": ingress.get("user_id") or None,
                    "updated_at": max(
                        now,
                        _as_float((task_row or {}).get("updated_at")),
                        _as_float((run_row or {}).get("updated_at")),
                        _as_float((job_row or {}).get("updated_at")),
                    ),
                    "metadata_json": _json_dumps({}),
                }
            )
        return rows

    def _component_trace_id(self, *, component: dict[str, list[dict[str, Any]]]) -> str:
        for row in component["task_links"]:
            trace_id = _as_text(row.get("trace_id"))
            if trace_id:
                return trace_id
        for row in component["jobs"]:
            client = _safe_json_loads(row.get("client_json"), default={})
            input_obj = _safe_json_loads(row.get("input_json"), default={})
            trace_id = _as_text(client.get("trace_id") or input_obj.get("trace_id"))
            if trace_id:
                return trace_id
        for row in component["team_runs"]:
            trace_id = _as_text(row.get("trace_id"))
            if trace_id:
                return trace_id
        for member in component["members"]:
            if member.startswith("trace:"):
                return member.split(":", 1)[1]
        return ""

    def _component_ingress(self, *, component: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
        task_row = _pick_latest(component["tasks"], status_fields=("status",), preferred={"running", "completed"})
        if task_row:
            return {
                "channel": _as_text(task_row.get("source_channel")),
                "session_id": _as_text(task_row.get("source_session_id")),
                "thread_id": _as_text(task_row.get("source_thread_id")),
                "tenant_id": _as_text(task_row.get("owner_kind")),
                "team_id": _as_text(task_row.get("owner_id")),
                "user_id": _as_text(task_row.get("source_message_id")),
            }
        for row in component["jobs"]:
            client = _safe_json_loads(row.get("client_json"), default={})
            return {
                "channel": _as_text(client.get("name") or client.get("route")),
                "session_id": _as_text(client.get("session_id")),
                "thread_id": _as_text(client.get("thread_id")),
                "tenant_id": _as_text(client.get("account_id")),
                "team_id": _as_text(client.get("team_id")),
                "user_id": _as_text(client.get("user_id") or client.get("agent_id")),
            }
        return {
            "channel": "",
            "session_id": "",
            "thread_id": "",
            "tenant_id": "",
            "team_id": "",
            "user_id": "",
        }

    def _build_component_events(self, *, root_key: str, component: dict[str, list[dict[str, Any]]], now: float) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        def _append(
            *,
            source_system: str,
            layer: str,
            entity_type: str,
            entity_id: str,
            event_type: str,
            status: str,
            severity: str,
            ts: float,
            summary: str,
            payload: dict[str, Any],
        ) -> None:
            if ts <= 0:
                ts_value = now
            else:
                ts_value = ts
            event_key = f"{root_key}:{source_system}:{entity_type}:{entity_id}:{event_type}:{ts_value:.6f}"
            events.append(
                {
                    "event_key": event_key,
                    "root_run_id": root_key,
                    "source_system": source_system,
                    "layer": layer,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "event_type": event_type,
                    "status": status,
                    "severity": severity,
                    "ts": ts_value,
                    "summary": summary,
                    "payload_json": _json_dumps(payload),
                }
            )

        for row in component["tasks"]:
            _append(
                source_system="chatgptrest",
                layer="task",
                entity_type="task",
                entity_id=_as_text(row.get("task_id")),
                event_type="task.status",
                status=_as_text(row.get("status")),
                severity="info",
                ts=max(_as_float(row.get("updated_at")), _as_float(row.get("created_at"))),
                summary=f"Task {_as_text(row.get('status')) or 'n/a'} · {_truncate(row.get('title'), 96)}",
                payload=row,
            )
        for row in sorted(component["task_messages"], key=lambda item: _as_float(item.get("created_at")), reverse=True)[:20]:
            _append(
                source_system="chatgptrest",
                layer="message",
                entity_type="task_message",
                entity_id=_as_text(row.get("message_id")),
                event_type=f"task.message.{_as_text(row.get('role')).lower() or 'unknown'}",
                status="logged",
                severity="info",
                ts=_as_float(row.get("created_at")),
                summary=f"{_as_text(row.get('role')) or 'message'} · {_truncate(row.get('content'), 120)}",
                payload=row,
            )
        for row in component["runs"]:
            _append(
                source_system="chatgptrest",
                layer="run",
                entity_type="advisor_run",
                entity_id=_as_text(row.get("run_id")),
                event_type="advisor.run.status",
                status=_as_text(row.get("status")),
                severity="warning" if _as_text(row.get("degraded")) in {"1", "true"} else "info",
                ts=max(_as_float(row.get("updated_at")), _as_float(row.get("created_at"))),
                summary=f"Run {_as_text(row.get('status')) or 'n/a'} · route {_as_text(row.get('route')) or 'n/a'}",
                payload=row,
            )
        for row in component["steps"]:
            _append(
                source_system="chatgptrest",
                layer="run",
                entity_type="advisor_step",
                entity_id=f"{_as_text(row.get('run_id'))}:{_as_text(row.get('step_id'))}",
                event_type=_as_text(row.get("step_type")) or "advisor.step",
                status=_as_text(row.get("status")),
                severity="info",
                ts=max(_as_float(row.get("updated_at")), _as_float(row.get("created_at"))),
                summary=f"Step {_as_text(row.get('step_id'))} · {_as_text(row.get('status')) or 'n/a'}",
                payload=row,
            )
        for row in component["advisor_events"]:
            payload = _safe_json_loads(row.get("payload_json"), default={})
            _append(
                source_system="chatgptrest",
                layer="run",
                entity_type="advisor_event",
                entity_id=f"{_as_text(row.get('run_id'))}:{_as_int(row.get('id'))}",
                event_type=_as_text(row.get("type")) or "advisor.event",
                status=_as_text(payload.get("status")),
                severity=_as_text(payload.get("severity") or "info"),
                ts=_as_float(row.get("ts")),
                summary=f"Advisor event · {_truncate(row.get('type'), 96)}",
                payload=payload,
            )
        for row in component["jobs"]:
            _append(
                source_system="chatgptrest",
                layer="job",
                entity_type="job",
                entity_id=_as_text(row.get("job_id")),
                event_type="job.status",
                status=_as_text(row.get("status")),
                severity="warning" if _as_text(row.get("status")).lower() in {"error", "blocked", "needs_followup", "cooldown"} else "info",
                ts=max(_as_float(row.get("updated_at")), _as_float(row.get("created_at"))),
                summary=f"Job {_as_text(row.get('status')) or 'n/a'} · {_as_text(row.get('kind')) or 'n/a'} · {_as_text(row.get('phase')) or 'n/a'}",
                payload=row,
            )
        for row in component["job_events"]:
            payload = _safe_json_loads(row.get("payload_json"), default={})
            _append(
                source_system="chatgptrest",
                layer="job",
                entity_type="job_event",
                entity_id=f"{_as_text(row.get('job_id'))}:{_as_int(row.get('id'))}",
                event_type=_as_text(row.get("type")) or "job.event",
                status=_as_text(payload.get("status")),
                severity=_as_text(payload.get("severity") or "info"),
                ts=_as_float(row.get("ts")),
                summary=f"Job event · {_truncate(row.get('type'), 96)}",
                payload=payload,
            )
        for row in component["lanes"]:
            stale = self._lane_stale(row=row, now=now)
            _append(
                source_system="controller",
                layer="lane",
                entity_type="lane",
                entity_id=_as_text(row.get("lane_id")),
                event_type="lane.state",
                status=_as_text(row.get("run_state")),
                severity="warning" if stale else "info",
                ts=max(_as_float(row.get("updated_at")), _as_float(row.get("heartbeat_at")), _as_float(row.get("created_at"))),
                summary=f"Lane {_as_text(row.get('run_state')) or 'n/a'} · {_truncate(row.get('purpose'), 96)}",
                payload={**row, "stale": stale},
            )
        for row in component["lane_events"]:
            payload = _safe_json_loads(row.get("payload_json"), default={})
            _append(
                source_system="controller",
                layer="lane",
                entity_type="lane_event",
                entity_id=f"{_as_text(row.get('lane_id'))}:{_as_int(row.get('event_id'))}",
                event_type=_as_text(row.get("event_type")) or "lane.event",
                status=_as_text(payload.get("status")),
                severity=_as_text(payload.get("severity") or "info"),
                ts=_as_float(row.get("created_at")),
                summary=f"Lane event · {_truncate(row.get('event_type'), 96)}",
                payload=payload,
            )
        for row in component["team_runs"]:
            _append(
                source_system="team_control_plane",
                layer="team",
                entity_type="team_run",
                entity_id=_as_text(row.get("team_run_id")),
                event_type="team.run.status",
                status=_as_text(row.get("status")),
                severity="info",
                ts=max(_as_float(row.get("completed_at")), _as_float(row.get("started_at")), _as_float(row.get("created_at"))),
                summary=f"Team run {_as_text(row.get('status')) or 'n/a'} · {_truncate(row.get('team_id'), 64)}",
                payload=row,
            )
        for row in component["team_role_runs"]:
            _append(
                source_system="team_control_plane",
                layer="team_role",
                entity_type="team_role_run",
                entity_id=f"{_as_text(row.get('team_run_id'))}:{_as_text(row.get('role_name'))}",
                event_type="team.role.status",
                status=_as_text(row.get("status")),
                severity="warning" if _as_text(row.get("status")).lower() in {"failed", "blocked"} else "info",
                ts=max(_as_float(row.get("completed_at")), _as_float(row.get("started_at"))),
                summary=f"Role {_as_text(row.get('role_name')) or 'n/a'} · {_as_text(row.get('status')) or 'n/a'}",
                payload=row,
            )
        for row in component["team_checkpoints"]:
            _append(
                source_system="team_control_plane",
                layer="checkpoint",
                entity_type="team_checkpoint",
                entity_id=_as_text(row.get("checkpoint_id")),
                event_type="team.checkpoint.status",
                status=_as_text(row.get("status")),
                severity="warning" if _as_text(row.get("status")).lower() == "pending" else "info",
                ts=max(_as_float(row.get("resolved_at")), _as_float(row.get("created_at"))),
                summary=f"Checkpoint {_as_text(row.get('status')) or 'n/a'} · {_truncate(row.get('summary'), 96)}",
                payload=row,
            )
        for row in component["issues"]:
            _append(
                source_system="chatgptrest",
                layer="issue",
                entity_type="client_issue",
                entity_id=_as_text(row.get("issue_id")),
                event_type="client.issue.status",
                status=_as_text(row.get("status")),
                severity=_as_text(row.get("severity") or "P2"),
                ts=max(_as_float(row.get("updated_at")), _as_float(row.get("created_at"))),
                summary=f"Issue {_as_text(row.get('status')) or 'n/a'} · {_truncate(row.get('title'), 96)}",
                payload=row,
            )
        for row in component["issue_events"][:20]:
            payload = _safe_json_loads(row.get("payload_json"), default={})
            _append(
                source_system="chatgptrest",
                layer="issue",
                entity_type="client_issue_event",
                entity_id=f"{_as_text(row.get('issue_id'))}:{_as_int(row.get('id'))}",
                event_type=_as_text(row.get("type")) or "client.issue.event",
                status=_as_text(payload.get("status")),
                severity=_as_text(payload.get("severity") or "info"),
                ts=_as_float(row.get("ts")),
                summary=f"Issue event · {_truncate(row.get('type'), 96)}",
                payload=payload,
            )
        for row in component["incidents"]:
            _append(
                source_system="chatgptrest",
                layer="runtime",
                entity_type="incident",
                entity_id=_as_text(row.get("incident_id")),
                event_type="incident.status",
                status=_as_text(row.get("status")),
                severity=_as_text(row.get("severity") or "P2"),
                ts=max(_as_float(row.get("updated_at")), _as_float(row.get("created_at"))),
                summary=f"Incident {_as_text(row.get('status')) or 'n/a'} · {_truncate(row.get('signature'), 96)}",
                payload=row,
            )
        events.sort(key=lambda item: (float(item["ts"]), item["event_key"]), reverse=True)
        return events

    def _lane_stale(self, *, row: dict[str, Any], now: float) -> bool:
        stale_after = max(60, _as_int(row.get("stale_after_seconds"), 900))
        heartbeat = max(_as_float(row.get("heartbeat_at")), _as_float(row.get("updated_at")))
        if heartbeat <= 0:
            return _as_text(row.get("run_state")).lower() in {"working", "running", "blocked"}
        return (now - heartbeat) > stale_after

    def _build_run_index_row(self, *, root_key: str, component: dict[str, list[dict[str, Any]]], now: float) -> dict[str, Any] | None:
        if not (
            component["tasks"]
            or component["runs"]
            or component["jobs"]
            or component["lanes"]
            or component["team_runs"]
        ):
            return None

        task_row = _pick_latest(component["tasks"], status_fields=("status",), preferred={"running", "completed"})
        run_row = _pick_latest(component["runs"], status_fields=("status",), preferred={"running", "completed", "failed"})
        issue_row = _pick_latest(component["issues"], status_fields=("status",), preferred={"open", "in_progress", "resolved"})
        incident_row = _pick_latest(component["incidents"], status_fields=("status",), preferred={"open", "resolved"})
        team_run_row = _pick_latest(component["team_runs"], status_fields=("status",), preferred={"running", "completed", "failed"})
        lane_row = _pick_latest(component["lanes"], status_fields=("run_state",), preferred={"working", "blocked", "idle"})
        job_row = _pick_latest(component["jobs"], status_fields=("status",), preferred={"in_progress", "error", "needs_followup", "cooldown", "completed"})
        role_row = _pick_latest(component["team_role_runs"], status_fields=("status",), preferred={"running", "pending", "failed"})
        checkpoint_row = _pick_latest(component["team_checkpoints"], status_fields=("status",), preferred={"pending", "resolved"})

        trace_id = self._component_trace_id(component=component)
        ingress = self._component_ingress(component=component)

        root_entity_type = root_key.partition(":")[0]
        task_id = _as_text((task_row or {}).get("task_id"))
        task_ref = _as_text((task_row or {}).get("task_ref"))
        title = _as_text((task_row or {}).get("title") or (run_row or {}).get("normalized_question") or (run_row or {}).get("raw_question"))
        job_status = _as_text((job_row or {}).get("status"))
        job_phase = _as_text((job_row or {}).get("phase"))
        lane_status = _as_text((lane_row or {}).get("run_state"))
        checkpoint_pending = _as_int((lane_row or {}).get("checkpoint_pending"))
        lane_stale = bool(lane_row and self._lane_stale(row=lane_row, now=now))
        role_status = _as_text((role_row or {}).get("status"))
        checkpoint_status = _as_text((checkpoint_row or {}).get("status"))

        if checkpoint_status.lower() == "pending":
            current_layer = "checkpoint"
            current_status = checkpoint_status or "pending"
            current_owner = _as_text((checkpoint_row or {}).get("actor") or (checkpoint_row or {}).get("gate_id"))
            problem_class = "team_role_or_checkpoint"
        elif role_status.lower() in {"running", "pending", "failed", "blocked"}:
            current_layer = "team_role"
            current_status = role_status
            current_owner = _as_text((role_row or {}).get("role_name"))
            problem_class = "team_role_or_checkpoint"
        elif lane_stale or checkpoint_pending > 0 or lane_status.lower() in {"working", "blocked"}:
            current_layer = "lane"
            current_status = "stale" if lane_stale else (lane_status or "working")
            current_owner = _as_text((lane_row or {}).get("lane_id"))
            problem_class = "lane_continuity"
        elif job_status.lower() in {"in_progress", "error", "blocked", "needs_followup", "cooldown"}:
            current_layer = "job"
            current_status = job_status
            current_owner = _as_text((job_row or {}).get("job_id"))
            problem_class = "job"
        elif _as_text((run_row or {}).get("status")).lower() in {"running", "failed"}:
            current_layer = "run"
            current_status = _as_text((run_row or {}).get("status"))
            current_owner = _as_text((run_row or {}).get("run_id"))
            problem_class = "run"
        elif issue_row and _as_text(issue_row.get("status")).lower() in {"open", "in_progress"}:
            current_layer = "issue"
            current_status = _as_text(issue_row.get("status"))
            current_owner = _as_text(issue_row.get("issue_id"))
            problem_class = "issue"
        else:
            current_layer = "task"
            current_status = _as_text((task_row or {}).get("status") or "completed")
            current_owner = _as_text((task_row or {}).get("task_id"))
            problem_class = "healthy"

        health_tone = _tone_for_status(current_status, severe=problem_class not in {"healthy", "run"})
        upstream = [
            {"label": "ingress", "value": value}
            for label, value in (
                ("channel", ingress.get("channel")),
                ("session", ingress.get("session_id")),
                ("thread", ingress.get("thread_id")),
                ("trace", trace_id),
            )
            if value
        ]
        downstream = [
            {"label": "job", "value": _as_text((job_row or {}).get("job_id")), "status": job_status} if job_row else {},
            {"label": "lane", "value": _as_text((lane_row or {}).get("lane_id")), "status": lane_status} if lane_row else {},
            {"label": "team_role", "value": _as_text((role_row or {}).get("role_name")), "status": role_status} if role_row else {},
            {"label": "checkpoint", "value": _as_text((checkpoint_row or {}).get("checkpoint_id")), "status": checkpoint_status} if checkpoint_row else {},
        ]
        downstream = [item for item in downstream if item]
        created_at = min(
            value
            for value in [
                _as_float((task_row or {}).get("created_at")),
                _as_float((run_row or {}).get("created_at")),
                _as_float((job_row or {}).get("created_at")),
                _as_float((lane_row or {}).get("created_at")),
                _as_float((team_run_row or {}).get("created_at")),
                now,
            ]
            if value > 0
        )
        last_progress_at = max(
            _as_float((task_row or {}).get("updated_at")),
            _as_float((run_row or {}).get("updated_at")),
            _as_float((job_row or {}).get("updated_at")),
            _as_float((job_row or {}).get("conversation_export_chars")),
            _as_float((lane_row or {}).get("heartbeat_at")),
            _as_float((team_run_row or {}).get("completed_at")),
            _as_float((team_run_row or {}).get("started_at")),
            _as_float((issue_row or {}).get("updated_at")),
            _as_float((incident_row or {}).get("updated_at")),
        )
        summary = {
            "task_status": _as_text((task_row or {}).get("status")),
            "run_status": _as_text((run_row or {}).get("status")),
            "job_status": job_status,
            "job_phase": job_phase,
            "lane_status": lane_status,
            "lane_stale": lane_stale,
            "role_status": role_status,
            "checkpoint_status": checkpoint_status,
            "issue_status": _as_text((issue_row or {}).get("status")),
            "incident_status": _as_text((incident_row or {}).get("status")),
            "has_open_issue": bool(issue_row and _as_text(issue_row.get("status")).lower() in {"open", "in_progress"}),
            "has_open_incident": bool(incident_row and _as_text(incident_row.get("status")).lower() == "open"),
            "member_keys": component["members"],
        }

        return {
            "root_run_id": root_key,
            "root_entity_type": root_entity_type,
            "task_id": task_id or None,
            "task_ref": task_ref or None,
            "title": title or root_key,
            "ingress_channel": ingress.get("channel") or None,
            "session_id": ingress.get("session_id") or None,
            "thread_id": ingress.get("thread_id") or None,
            "tenant_id": ingress.get("tenant_id") or None,
            "team_id": ingress.get("team_id") or None,
            "user_id": ingress.get("user_id") or None,
            "trace_id": trace_id or None,
            "run_id": _as_text((run_row or {}).get("run_id")) or None,
            "job_id": _as_text((job_row or {}).get("job_id")) or None,
            "job_kind": _as_text((job_row or {}).get("kind")) or None,
            "job_phase": job_phase or None,
            "job_status": job_status or None,
            "lane_id": _as_text((lane_row or {}).get("lane_id")) or None,
            "lane_status": lane_status or None,
            "team_run_id": _as_text((team_run_row or {}).get("team_run_id")) or None,
            "role_name": _as_text((role_row or {}).get("role_name")) or None,
            "checkpoint_id": _as_text((checkpoint_row or {}).get("checkpoint_id")) or None,
            "issue_id": _as_text((issue_row or {}).get("issue_id")) or None,
            "incident_id": _as_text((incident_row or {}).get("incident_id")) or None,
            "current_layer": current_layer,
            "current_status": current_status or "unknown",
            "current_owner": current_owner,
            "problem_class": problem_class,
            "health_tone": health_tone,
            "upstream_json": _json_dumps(upstream),
            "downstream_json": _json_dumps(downstream),
            "entity_counts_json": _json_dumps(
                {
                    "tasks": len(component["tasks"]),
                    "runs": len(component["runs"]),
                    "jobs": len(component["jobs"]),
                    "lanes": len(component["lanes"]),
                    "team_runs": len(component["team_runs"]),
                    "team_role_runs": len(component["team_role_runs"]),
                    "team_checkpoints": len(component["team_checkpoints"]),
                    "issues": len(component["issues"]),
                    "incidents": len(component["incidents"]),
                }
            ),
            "summary_json": _json_dumps(summary),
            "created_at": created_at,
            "last_progress_at": last_progress_at or created_at,
            "updated_at": max(last_progress_at, created_at),
        }

    def _build_timeline_rows(self, *, root_key: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for rank, event in enumerate(sorted(events, key=lambda item: (float(item["ts"]), item["event_key"]), reverse=True)[:120], start=1):
            rows.append(
                {
                    "root_run_id": root_key,
                    "event_rank": rank,
                    "ts": event["ts"],
                    "layer": event["layer"],
                    "source_system": event["source_system"],
                    "entity_type": event["entity_type"],
                    "entity_id": event["entity_id"],
                    "event_type": event["event_type"],
                    "status": event["status"],
                    "severity": event["severity"],
                    "summary": event["summary"],
                    "payload_json": event["payload_json"],
                }
            )
        return rows

    def _build_component_incident_rows(self, *, root_key: str, component: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in component["issues"]:
            rows.append(
                {
                    "incident_key": f"client_issue:{_as_text(row.get('issue_id'))}",
                    "incident_type": "client_issue",
                    "incident_id": _as_text(row.get("issue_id")),
                    "root_run_id": root_key,
                    "job_id": _as_text(row.get("latest_job_id")) or None,
                    "issue_id": _as_text(row.get("issue_id")) or None,
                    "project": _as_text(row.get("project")) or None,
                    "category": _as_text(row.get("kind")) or None,
                    "severity": _as_text(row.get("severity") or "P2"),
                    "status": _as_text(row.get("status") or "open"),
                    "title": _as_text(row.get("title")) or _as_text(row.get("fingerprint_text")) or "client issue",
                    "summary": _truncate(row.get("symptom") or row.get("raw_error") or row.get("fingerprint_text"), 180),
                    "blast_radius": "local",
                    "guard_source": _as_text(row.get("source")) or None,
                    "updated_at": max(_as_float(row.get("updated_at")), _as_float(row.get("created_at"))),
                    "metadata_json": _json_dumps(_safe_json_loads(row.get("metadata_json"), default={})),
                }
            )
        for row in component["incidents"]:
            job_ids = _safe_json_loads(row.get("job_ids_json"), default=[])
            rows.append(
                {
                    "incident_key": f"incident:{_as_text(row.get('incident_id'))}",
                    "incident_type": "incident",
                    "incident_id": _as_text(row.get("incident_id")),
                    "root_run_id": root_key,
                    "job_id": _as_text(job_ids[0]) if job_ids else None,
                    "issue_id": None,
                    "project": None,
                    "category": _as_text(row.get("category")) or None,
                    "severity": _as_text(row.get("severity") or "P2"),
                    "status": _as_text(row.get("status") or "open"),
                    "title": _as_text(row.get("signature")) or "incident",
                    "summary": _truncate(row.get("signature"), 180),
                    "blast_radius": "multi_job" if len(job_ids) > 1 else "local",
                    "guard_source": "incident_ledger",
                    "updated_at": max(_as_float(row.get("updated_at")), _as_float(row.get("created_at"))),
                    "metadata_json": _json_dumps({"count": _as_int(row.get("count")), "job_ids": job_ids}),
                }
            )
        return rows

    def _build_component_cognitive_rows(
        self,
        *,
        root_key: str,
        component: dict[str, list[dict[str, Any]]],
        run_row: dict[str, Any] | None,
        now: float,
    ) -> list[dict[str, Any]]:
        if run_row is None:
            return []
        route = ""
        latest_advisor_event = ""
        if component["runs"]:
            primary = _pick_latest(component["runs"], status_fields=("status",), preferred={"running", "completed"})
            route = _as_text((primary or {}).get("route"))
        if component["advisor_events"]:
            latest = component["advisor_events"][0]
            latest_advisor_event = _as_text(latest.get("type"))
        summary = {
            "trace_id": _as_text(run_row.get("trace_id")),
            "route": route,
            "latest_advisor_event": latest_advisor_event,
            "advisor_event_count": len(component["advisor_events"]),
            "step_count": len(component["steps"]),
            "signal_overlay_ready": bool(_as_text(run_row.get("trace_id"))),
        }
        return [
            {
                "snapshot_key": f"root:{root_key}",
                "scope": "root",
                "root_run_id": root_key,
                "kind": "run_overlay",
                "ts": now,
                "summary_json": _json_dumps(summary),
                "details_json": _json_dumps({"events": len(component["advisor_events"]), "steps": len(component["steps"])}),
            }
        ]

    def _build_global_cognitive_rows(self, *, openmind: dict[str, Any], now: float) -> list[dict[str, Any]]:
        return [
            {
                "snapshot_key": "global:openmind",
                "scope": "global",
                "root_run_id": None,
                "kind": "openmind_global",
                "ts": now,
                "summary_json": _json_dumps(openmind),
                "details_json": _json_dumps(openmind),
            }
        ]

    def _build_component_health(
        self,
        *,
        runs: list[dict[str, Any]],
        incident_rows: list[dict[str, Any]],
        runtime_reports: dict[str, Any],
        openmind: dict[str, Any],
        jobs: list[dict[str, Any]],
        now: float,
    ) -> list[dict[str, Any]]:
        active_runs = [row for row in runs if _as_text(row.get("current_status")).lower() not in {"completed", "resolved", "closed", "idle"}]
        blocked_runs = [row for row in runs if _as_text(row.get("health_tone")) in {"danger", "warning"}]
        active_incidents = [row for row in incident_rows if _as_text(row.get("status")).lower() in {"open", "in_progress"}]
        stuck_wait_threshold = max(60, _as_int(os.environ.get("CHATGPTREST_OPS_STUCK_WAIT_SECONDS"), 240))
        stuck_wait_jobs = [
            row
            for row in jobs
            if _as_text(row.get("status")).lower() == "in_progress"
            and _as_text(row.get("phase")).lower() == "wait"
            and (now - _as_float(row.get("updated_at"))) >= stuck_wait_threshold
        ]

        guardian = runtime_reports.get("guardian") or {}
        orch = runtime_reports.get("orch") or {}
        ui_canary = runtime_reports.get("ui_canary") or {}
        viewer = runtime_reports.get("viewer") or {}
        runtime_guard = runtime_reports.get("runtime_guard") or {}

        ui_failed = [
            _as_text(item.get("provider"))
            for item in ui_canary.get("providers", [])
            if isinstance(item, dict) and not bool(item.get("ok"))
        ]
        blast_radius = "wide" if len(active_incidents) >= 5 or len(blocked_runs) >= 5 else "local"

        def _row(
            *,
            component_key: str,
            plane: str,
            label: str,
            status: str,
            severity: str,
            ok: bool | None,
            guard_family: str,
            attention_reason: str,
            summary: str,
            details: dict[str, Any],
            signal_ts: float = 0.0,
        ) -> dict[str, Any]:
            return {
                "component_key": component_key,
                "plane": plane,
                "label": label,
                "status": status,
                "severity": severity,
                "ok": None if ok is None else int(bool(ok)),
                "guard_family": guard_family or None,
                "attention_reason": attention_reason or None,
                "blast_radius": blast_radius,
                "signal_ts": signal_ts or now,
                "summary": summary,
                "details_json": _json_dumps(details),
            }

        rows = [
            _row(
                component_key="execution.control",
                plane="execution",
                label="Execution Control Plane",
                status="degraded" if blocked_runs or stuck_wait_jobs else "healthy",
                severity="warning" if blocked_runs or stuck_wait_jobs else "info",
                ok=not (blocked_runs or stuck_wait_jobs),
                guard_family="execution",
                attention_reason="blocked_runs" if blocked_runs else ("stuck_wait_jobs" if stuck_wait_jobs else ""),
                summary=f"active_runs={len(active_runs)} blocked_runs={len(blocked_runs)} stuck_wait_jobs={len(stuck_wait_jobs)}",
                details={"active_runs": len(active_runs), "blocked_runs": len(blocked_runs), "stuck_wait_jobs": len(stuck_wait_jobs)},
            ),
            _row(
                component_key="runtime.guardian",
                plane="runtime",
                label="Guardian",
                status="blocked" if bool(guardian.get("needs_attention")) else ("healthy" if guardian else "unknown"),
                severity="danger" if bool(guardian.get("needs_attention")) else ("info" if guardian else "warning"),
                ok=None if not guardian else bool(guardian.get("ok", True)),
                guard_family="guardian",
                attention_reason="needs_attention" if bool(guardian.get("needs_attention")) else "",
                summary=_truncate(guardian.get("anomalies") or guardian.get("policy_violations") or "guardian ok", 180) if guardian else "guardian report missing",
                details=guardian,
                signal_ts=_as_float(guardian.get("generated_at"), now),
            ),
            _row(
                component_key="runtime.orch",
                plane="runtime",
                label="Orchestrator Doctor",
                status="blocked" if bool(orch.get("needs_attention")) else ("healthy" if orch else "unknown"),
                severity="danger" if bool(orch.get("needs_attention")) else ("info" if orch else "warning"),
                ok=None if not orch else bool(orch.get("ok", True)),
                guard_family="orch",
                attention_reason="needs_attention" if bool(orch.get("needs_attention")) else "",
                summary="orch attention" if bool(orch.get("needs_attention")) else ("orch ok" if orch else "orch report missing"),
                details=orch,
                signal_ts=_as_float(orch.get("generated_at"), now),
            ),
            _row(
                component_key="runtime.ui_canary",
                plane="runtime",
                label="UI Canary",
                status="blocked" if ui_failed else ("healthy" if ui_canary else "unknown"),
                severity="danger" if ui_failed else ("info" if ui_canary else "warning"),
                ok=None if not ui_canary else not ui_failed,
                guard_family="ui_canary",
                attention_reason="provider_failed" if ui_failed else "",
                summary=f"failed={','.join(ui_failed)}" if ui_failed else ("ui canary ok" if ui_canary else "ui canary report missing"),
                details=ui_canary,
                signal_ts=_as_float(ui_canary.get("generated_at") or ui_canary.get("ts"), now),
            ),
            _row(
                component_key="runtime.viewer",
                plane="runtime",
                label="Viewer Watchdog",
                status="healthy" if bool(viewer.get("ok")) else "blocked",
                severity="info" if bool(viewer.get("ok")) else "warning",
                ok=bool(viewer.get("ok")),
                guard_family="viewer_watchdog",
                attention_reason="" if bool(viewer.get("ok")) else "viewer_unhealthy",
                summary="viewer healthy" if bool(viewer.get("ok")) else "viewer unhealthy",
                details=viewer,
                signal_ts=_as_float(viewer.get("checked_at"), now),
            ),
            _row(
                component_key="runtime.runtime_guard",
                plane="runtime",
                label="Runtime Guard",
                status="blocked" if bool(runtime_guard.get("needs_attention")) else ("healthy" if runtime_guard else "unknown"),
                severity="warning" if bool(runtime_guard.get("needs_attention")) else ("info" if runtime_guard else "warning"),
                ok=None if not runtime_guard else bool(runtime_guard.get("ok", True)),
                guard_family="runtime_guard",
                attention_reason="needs_attention" if bool(runtime_guard.get("needs_attention")) else "",
                summary="runtime guard attention" if bool(runtime_guard.get("needs_attention")) else ("runtime guard ok" if runtime_guard else "runtime guard report missing"),
                details=runtime_guard,
                signal_ts=_as_float(runtime_guard.get("generated_at"), now),
            ),
            _row(
                component_key="cognitive.openmind",
                plane="cognitive",
                label="OpenMind",
                status="healthy",
                severity="info",
                ok=True,
                guard_family="openmind",
                attention_reason="",
                summary=f"kb_docs={openmind.get('kb_search_docs', 0)} memory={openmind.get('memory_records', 0)} signals={openmind.get('signal_rows', 0)}",
                details=openmind,
                signal_ts=now,
            ),
        ]
        return rows
