"""Team control plane for multi-role Codex/OpenClaw execution.

This module provides:
  - topology/role resolution from catalog config
  - persistent run, role, and checkpoint state in SQLite
  - deterministic digest generation
  - gate evaluation / approve / reject lifecycle
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from chatgptrest.evomap.paths import resolve_evomap_db_path
from chatgptrest.kernel.team_catalog import TeamCatalogBundle, TeamGate, TeamTopology, load_team_catalog
from chatgptrest.kernel.team_types import TeamSpec

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS team_runs (
    team_run_id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL DEFAULT '',
    topology_id TEXT NOT NULL DEFAULT '',
    repo TEXT NOT NULL DEFAULT '',
    task_type TEXT NOT NULL DEFAULT '',
    trace_id TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'running',
    execution_mode TEXT NOT NULL DEFAULT 'parallel',
    team_spec_json TEXT NOT NULL DEFAULT '{}',
    output_contract_json TEXT NOT NULL DEFAULT '{}',
    success_criteria_json TEXT NOT NULL DEFAULT '{}',
    digest TEXT NOT NULL DEFAULT '',
    final_ok INTEGER NOT NULL DEFAULT 0,
    final_quality REAL NOT NULL DEFAULT 0.0,
    final_error TEXT NOT NULL DEFAULT '',
    final_output_preview TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL DEFAULT 0,
    started_at REAL NOT NULL DEFAULT 0,
    completed_at REAL NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_team_runs_status ON team_runs(status, created_at DESC);

CREATE TABLE IF NOT EXISTS team_role_runs (
    team_run_id TEXT NOT NULL,
    role_name TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    task_trace_id TEXT NOT NULL DEFAULT '',
    started_at REAL NOT NULL DEFAULT 0,
    completed_at REAL NOT NULL DEFAULT 0,
    ok INTEGER NOT NULL DEFAULT 0,
    quality_score REAL NOT NULL DEFAULT 0.0,
    elapsed_seconds REAL NOT NULL DEFAULT 0.0,
    output_preview TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    role_spec_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (team_run_id, role_name),
    FOREIGN KEY (team_run_id) REFERENCES team_runs(team_run_id)
);

CREATE INDEX IF NOT EXISTS idx_team_role_runs_status ON team_role_runs(status, started_at DESC);

CREATE TABLE IF NOT EXISTS team_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    team_run_id TEXT NOT NULL,
    gate_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    summary TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL DEFAULT 0,
    resolved_at REAL NOT NULL DEFAULT 0,
    actor TEXT NOT NULL DEFAULT '',
    resolution TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (team_run_id) REFERENCES team_runs(team_run_id)
);

CREATE INDEX IF NOT EXISTS idx_team_checkpoints_status ON team_checkpoints(status, created_at DESC);
"""


def _now() -> float:
    return float(time.time())


def _preview(text: str | None, limit: int = 600) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 3] + "..."


@dataclass
class TeamCheckpoint:
    checkpoint_id: str = ""
    team_run_id: str = ""
    gate_id: str = ""
    status: str = "pending"
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    resolved_at: float = 0.0
    actor: str = ""
    resolution: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.checkpoint_id:
            self.checkpoint_id = f"tcp_{uuid.uuid4().hex[:12]}"
        if self.created_at <= 0:
            self.created_at = _now()


class TeamControlPlane:
    def __init__(
        self,
        *,
        db_path: str = "",
        catalog: TeamCatalogBundle | None = None,
        clock: Any = None,
    ) -> None:
        raw_db_path = db_path or resolve_evomap_db_path()
        self._db_uri = False
        if raw_db_path == ":memory:":
            raw_db_path = f"file:team_control_plane_{id(self)}?mode=memory&cache=shared"
            self._db_uri = True
        self._db_path = raw_db_path
        self._catalog = catalog or load_team_catalog()
        self._clock = clock or _now
        self._local = threading.local()
        self._init_db()

    @property
    def db_path(self) -> str:
        return self._db_path

    @property
    def catalog(self) -> TeamCatalogBundle:
        return self._catalog

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            path = str(self._db_path)
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._local.conn = sqlite3.connect(path, check_same_thread=False, uri=self._db_uri)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._conn
        conn.executescript(_DDL)
        conn.commit()

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    def resolve_team_spec(
        self,
        *,
        team: TeamSpec | dict[str, Any] | None = None,
        topology_id: str = "",
        task_type: str = "",
    ) -> tuple[TeamSpec | None, TeamTopology | None]:
        requested_topology_id = str(topology_id or "").strip()
        explicit_spec: TeamSpec | None = None
        explicit_topology_id = ""

        if isinstance(team, TeamSpec) and team.roles:
            explicit_spec = team
            explicit_topology_id = str((team.metadata or {}).get("topology_id") or "").strip()
        elif isinstance(team, dict) and team:
            spec = TeamSpec.from_dict(team)
            if spec.roles:
                explicit_spec = spec
                explicit_topology_id = str((spec.metadata or {}).get("topology_id") or "").strip()

        selected_topology_id = requested_topology_id or explicit_topology_id
        topology = self._catalog.topologies.get(selected_topology_id) if selected_topology_id else None

        if explicit_spec is not None and explicit_spec.roles:
            return (
                self._merge_explicit_spec_with_topology(
                    explicit_spec,
                    topology=topology,
                    force_topology=bool(requested_topology_id),
                ),
                topology,
            )

        if topology is not None:
            spec = self._catalog.build_team_spec(topology.topology_id)
            return spec, topology
        topology = self._catalog.recommend_topology(str(task_type or ""))
        if topology is not None:
            spec = self._catalog.build_team_spec(topology.topology_id)
            return spec, topology
        return None, None

    def _merge_explicit_spec_with_topology(
        self,
        explicit_spec: TeamSpec,
        *,
        topology: TeamTopology | None,
        force_topology: bool = False,
    ) -> TeamSpec:
        if topology is None:
            return explicit_spec

        merged_metadata = dict(explicit_spec.metadata or {})
        if force_topology or not str(merged_metadata.get("topology_id", "") or "").strip():
            merged_metadata["topology_id"] = topology.topology_id
        if force_topology or "execution_mode" not in merged_metadata:
            merged_metadata["execution_mode"] = topology.execution_mode
        if force_topology or "synthesis_role" not in merged_metadata:
            merged_metadata["synthesis_role"] = topology.synthesis_role
        if force_topology or "max_concurrent" not in merged_metadata:
            merged_metadata["max_concurrent"] = topology.max_concurrent
        if force_topology or "gate_ids" not in merged_metadata:
            merged_metadata["gate_ids"] = list(topology.gate_ids)

        return TeamSpec(
            roles=list(explicit_spec.roles),
            team_id=explicit_spec.team_id,
            output_contract=dict(explicit_spec.output_contract or topology.output_contract),
            success_criteria=dict(explicit_spec.success_criteria or topology.success_criteria),
            metadata=merged_metadata,
        )

    def create_run(
        self,
        *,
        team_run_id: str,
        team_spec: TeamSpec,
        topology_id: str,
        task: Any,
        repo: str = "",
    ) -> None:
        now = float(self._clock())
        execution_mode = str((team_spec.metadata or {}).get("execution_mode", "parallel") or "parallel")
        conn = self._conn
        conn.execute(
            """
            INSERT OR REPLACE INTO team_runs (
                team_run_id, team_id, topology_id, repo, task_type, trace_id, description,
                status, execution_mode, team_spec_json, output_contract_json, success_criteria_json,
                digest, final_ok, final_quality, final_error, final_output_preview,
                created_at, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 0, 0.0, '', '', ?, ?, 0)
            """,
            (
                str(team_run_id),
                str(team_spec.team_id or ""),
                str(topology_id or (team_spec.metadata or {}).get("topology_id") or ""),
                str(repo or ""),
                str(getattr(task, "task_type", "") or ""),
                str(getattr(task, "trace_id", "") or ""),
                str(getattr(task, "description", "") or ""),
                "running",
                execution_mode,
                json.dumps(team_spec.to_dict(), ensure_ascii=False),
                json.dumps(team_spec.output_contract, ensure_ascii=False),
                json.dumps(team_spec.success_criteria, ensure_ascii=False),
                now,
                now,
            ),
        )
        for role in team_spec.roles:
            conn.execute(
                """
                INSERT OR REPLACE INTO team_role_runs (
                    team_run_id, role_name, model, status, task_trace_id, started_at, completed_at,
                    ok, quality_score, elapsed_seconds, output_preview, error, role_spec_json
                ) VALUES (?, ?, ?, 'pending', '', 0, 0, 0, 0.0, 0.0, '', '', ?)
                """,
                (
                    str(team_run_id),
                    str(role.name),
                    str(role.model),
                    json.dumps(role.to_dict(), ensure_ascii=False),
                ),
            )
        conn.commit()

    def mark_role_started(self, team_run_id: str, role_name: str, *, task_trace_id: str = "") -> None:
        conn = self._conn
        conn.execute(
            """
            UPDATE team_role_runs
            SET status='running', task_trace_id=?, started_at=?
            WHERE team_run_id=? AND role_name=?
            """,
            (str(task_trace_id), float(self._clock()), str(team_run_id), str(role_name)),
        )
        conn.commit()

    def mark_role_completed(self, team_run_id: str, role_name: str, result: Any) -> None:
        conn = self._conn
        conn.execute(
            """
            UPDATE team_role_runs
            SET status=?, completed_at=?, ok=?, quality_score=?, elapsed_seconds=?, output_preview=?, error=?
            WHERE team_run_id=? AND role_name=?
            """,
            (
                "completed" if bool(getattr(result, "ok", False)) else "failed",
                float(self._clock()),
                1 if bool(getattr(result, "ok", False)) else 0,
                float(getattr(result, "quality_score", 0.0) or 0.0),
                float(getattr(result, "elapsed_seconds", 0.0) or 0.0),
                _preview(getattr(result, "output", "")),
                _preview(getattr(result, "error", ""), 300),
                str(team_run_id),
                str(role_name),
            ),
        )
        conn.commit()

    def finalize_run(
        self,
        *,
        team_run_id: str,
        team_spec: TeamSpec,
        final_result: Any,
        role_outcomes: dict[str, dict[str, Any]],
    ) -> list[TeamCheckpoint]:
        checkpoints = self._evaluate_gates(team_run_id=team_run_id, team_spec=team_spec, final_result=final_result, role_outcomes=role_outcomes)
        digest = self._build_digest(team_run_id=team_run_id, team_spec=team_spec, final_result=final_result, checkpoints=checkpoints)
        status = "needs_review" if checkpoints else ("completed" if bool(getattr(final_result, "ok", False)) else "failed")

        conn = self._conn
        conn.execute(
            """
            UPDATE team_runs
            SET status=?, digest=?, final_ok=?, final_quality=?, final_error=?, final_output_preview=?, completed_at=?
            WHERE team_run_id=?
            """,
            (
                status,
                digest,
                1 if bool(getattr(final_result, "ok", False)) else 0,
                float(getattr(final_result, "quality_score", 0.0) or 0.0),
                _preview(getattr(final_result, "error", ""), 300),
                _preview(getattr(final_result, "output", "")),
                float(self._clock()),
                str(team_run_id),
            ),
        )
        for checkpoint in checkpoints:
            conn.execute(
                """
                INSERT OR REPLACE INTO team_checkpoints (
                    checkpoint_id, team_run_id, gate_id, status, summary, details_json,
                    created_at, resolved_at, actor, resolution, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.checkpoint_id,
                    checkpoint.team_run_id,
                    checkpoint.gate_id,
                    checkpoint.status,
                    checkpoint.summary,
                    json.dumps(checkpoint.details, ensure_ascii=False),
                    checkpoint.created_at,
                    checkpoint.resolved_at,
                    checkpoint.actor,
                    checkpoint.resolution,
                    checkpoint.reason,
                ),
            )
        conn.commit()
        return checkpoints

    def list_runs(self, *, status: str = "", limit: int = 20) -> list[dict[str, Any]]:
        conn = self._conn
        if status:
            rows = conn.execute(
                "SELECT * FROM team_runs WHERE status=? ORDER BY created_at DESC LIMIT ?",
                (str(status), int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM team_runs ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [self._row_to_run_dict(row) for row in rows]

    def get_run(self, team_run_id: str) -> dict[str, Any] | None:
        conn = self._conn
        row = conn.execute(
            "SELECT * FROM team_runs WHERE team_run_id=?",
            (str(team_run_id),),
        ).fetchone()
        if row is None:
            return None
        payload = self._row_to_run_dict(row)
        payload["roles"] = self._list_role_rows(team_run_id)
        payload["checkpoints"] = self.list_checkpoints(team_run_id=team_run_id)
        return payload

    def list_checkpoints(self, *, status: str = "", team_run_id: str = "", limit: int = 50) -> list[dict[str, Any]]:
        conn = self._conn
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(str(status))
        if team_run_id:
            clauses.append("team_run_id=?")
            params.append(str(team_run_id))
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM team_checkpoints {where} ORDER BY created_at DESC LIMIT ?",
            (*params, int(limit)),
        ).fetchall()
        return [self._row_to_checkpoint_dict(row) for row in rows]

    def approve_checkpoint(self, checkpoint_id: str, *, actor: str, reason: str = "") -> dict[str, Any] | None:
        return self._resolve_checkpoint(checkpoint_id, status="approved", actor=actor, resolution="approve", reason=reason)

    def reject_checkpoint(self, checkpoint_id: str, *, actor: str, reason: str = "") -> dict[str, Any] | None:
        return self._resolve_checkpoint(checkpoint_id, status="rejected", actor=actor, resolution="reject", reason=reason)

    def _resolve_checkpoint(self, checkpoint_id: str, *, status: str, actor: str, resolution: str, reason: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM team_checkpoints WHERE checkpoint_id=?",
            (str(checkpoint_id),),
        ).fetchone()
        if row is None:
            return None
        now = float(self._clock())
        self._conn.execute(
            """
            UPDATE team_checkpoints
            SET status=?, resolved_at=?, actor=?, resolution=?, reason=?
            WHERE checkpoint_id=?
            """,
            (str(status), now, str(actor), str(resolution), str(reason), str(checkpoint_id)),
        )
        team_run_id = str(row["team_run_id"] or "")
        pending = self._conn.execute(
            "SELECT COUNT(1) AS c FROM team_checkpoints WHERE team_run_id=? AND status='pending'",
            (team_run_id,),
        ).fetchone()
        count = int((pending["c"] if pending else 0) or 0)
        if count == 0:
            rejected = self._conn.execute(
                "SELECT COUNT(1) AS c FROM team_checkpoints WHERE team_run_id=? AND status='rejected'",
                (team_run_id,),
            ).fetchone()
            rejected_count = int((rejected["c"] if rejected else 0) or 0)
            run_row = self._conn.execute(
                "SELECT final_ok FROM team_runs WHERE team_run_id=?",
                (team_run_id,),
            ).fetchone()
            final_ok = bool(int((run_row["final_ok"] if run_row else 0) or 0))
            final_status = "rejected" if rejected_count > 0 else ("completed" if final_ok else "failed")
            self._conn.execute(
                "UPDATE team_runs SET status=? WHERE team_run_id=?",
                (final_status, team_run_id),
            )
        self._conn.commit()
        return self._row_to_checkpoint_dict(
            self._conn.execute(
                "SELECT * FROM team_checkpoints WHERE checkpoint_id=?",
                (str(checkpoint_id),),
            ).fetchone()
        )

    def _evaluate_gates(
        self,
        *,
        team_run_id: str,
        team_spec: TeamSpec,
        final_result: Any,
        role_outcomes: dict[str, dict[str, Any]],
    ) -> list[TeamCheckpoint]:
        checkpoints: list[TeamCheckpoint] = []
        gate_defs = self._catalog.gate_defs_for_spec(team_spec)
        if not gate_defs:
            return checkpoints
        role_names = list(role_outcomes.keys())
        final_ok = bool(getattr(final_result, "ok", False))
        final_quality = float(getattr(final_result, "quality_score", 0.0) or 0.0)
        final_text = str(getattr(final_result, "output", "") or "")
        failed_roles = [name for name, info in role_outcomes.items() if not bool(info.get("ok", False))]

        for gate in gate_defs:
            if not self._gate_triggered(gate, role_names=role_names, failed_roles=failed_roles, final_ok=final_ok, final_quality=final_quality, final_text=final_text):
                continue
            checkpoints.append(
                TeamCheckpoint(
                    team_run_id=str(team_run_id),
                    gate_id=gate.gate_id,
                    summary=self._gate_summary(gate, failed_roles=failed_roles, final_quality=final_quality),
                    details={
                        "failed_roles": failed_roles,
                        "final_ok": final_ok,
                        "final_quality": final_quality,
                        "role_names": role_names,
                    },
                )
            )
        return checkpoints

    def _gate_triggered(
        self,
        gate: TeamGate,
        *,
        role_names: list[str],
        failed_roles: list[str],
        final_ok: bool,
        final_quality: float,
        final_text: str,
    ) -> bool:
        trigger = str(gate.trigger or "").strip().lower()
        if trigger == "result_not_ok":
            return not final_ok
        if trigger == "min_quality":
            return final_quality < float(gate.threshold or 0.0)
        if trigger == "role_present":
            wanted = {str(v) for v in gate.roles}
            return any(name in wanted for name in role_names)
        if trigger == "role_failed":
            wanted = {str(v) for v in gate.roles}
            if wanted:
                return any(name in wanted for name in failed_roles)
            return bool(failed_roles)
        if trigger == "marker":
            upper = final_text.upper()
            return any(str(marker).upper() in upper for marker in gate.markers)
        return False

    def _gate_summary(self, gate: TeamGate, *, failed_roles: list[str], final_quality: float) -> str:
        if gate.trigger == "result_not_ok":
            return f"Team run failed and requires review ({gate.gate_id})."
        if gate.trigger == "min_quality":
            return f"Team quality {final_quality:.2f} is below threshold for {gate.gate_id}."
        if gate.trigger == "role_present":
            return f"Writer lane present; manual review required by {gate.gate_id}."
        if gate.trigger == "role_failed":
            return f"Role failure detected ({', '.join(failed_roles) or 'unknown'}) for {gate.gate_id}."
        if gate.trigger == "marker":
            return f"Explicit approval/input marker detected for {gate.gate_id}."
        return f"Checkpoint requested by gate {gate.gate_id}."

    def _build_digest(
        self,
        *,
        team_run_id: str,
        team_spec: TeamSpec,
        final_result: Any,
        checkpoints: list[TeamCheckpoint],
    ) -> str:
        roles = self._list_role_rows(team_run_id)
        parts = [
            f"team_run_id={team_run_id}",
            f"team_id={team_spec.team_id}",
            f"roles={','.join(role['role_name'] for role in roles)}",
            f"status={'needs_review' if checkpoints else ('completed' if getattr(final_result, 'ok', False) else 'failed')}",
            f"quality={float(getattr(final_result, 'quality_score', 0.0) or 0.0):.2f}",
        ]
        for role in roles:
            parts.append(
                f"{role['role_name']}:{role['status']}"
                + (f" q={role['quality_score']:.2f}" if role["quality_score"] else "")
            )
        if checkpoints:
            parts.append("checkpoints=" + ",".join(cp.gate_id for cp in checkpoints))
        preview = _preview(getattr(final_result, "output", ""), 220)
        if preview:
            parts.append(f"summary={preview}")
        return " | ".join(parts)

    def _list_role_rows(self, team_run_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM team_role_runs WHERE team_run_id=? ORDER BY role_name",
            (str(team_run_id),),
        ).fetchall()
        payload: list[dict[str, Any]] = []
        for row in rows:
            payload.append(
                {
                    "role_name": str(row["role_name"]),
                    "model": str(row["model"]),
                    "status": str(row["status"]),
                    "task_trace_id": str(row["task_trace_id"]),
                    "started_at": float(row["started_at"] or 0.0),
                    "completed_at": float(row["completed_at"] or 0.0),
                    "ok": bool(int(row["ok"] or 0)),
                    "quality_score": float(row["quality_score"] or 0.0),
                    "elapsed_seconds": float(row["elapsed_seconds"] or 0.0),
                    "output_preview": str(row["output_preview"] or ""),
                    "error": str(row["error"] or ""),
                    "role_spec": json.loads(str(row["role_spec_json"] or "{}")),
                }
            )
        return payload

    def _row_to_run_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = dict(row)
        payload["team_spec"] = json.loads(str(payload.pop("team_spec_json", "{}") or "{}"))
        payload["output_contract"] = json.loads(str(payload.pop("output_contract_json", "{}") or "{}"))
        payload["success_criteria"] = json.loads(str(payload.pop("success_criteria_json", "{}") or "{}"))
        payload["final_ok"] = bool(int(payload.get("final_ok", 0) or 0))
        return payload

    def _row_to_checkpoint_dict(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        payload = dict(row)
        payload["details"] = json.loads(str(payload.pop("details_json", "{}") or "{}"))
        return payload
