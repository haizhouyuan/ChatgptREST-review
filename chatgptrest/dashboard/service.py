from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from chatgptrest.core.config import AppConfig
from chatgptrest.core.path_resolver import resolve_finagent_root, resolve_finbot_artifact_roots
from chatgptrest.dashboard.control_plane import DashboardControlPlane, DashboardControlPlaneConfig

try:
    import yaml  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - yaml is present in runtime and tests
    yaml = None


def _safe_json_loads(raw: Any, *, default: Any) -> Any:
    if raw is None:
        return default
    try:
        return json.loads(str(raw))
    except Exception:
        return default


def _as_text(raw: Any) -> str:
    return str(raw or "").strip()


def _as_int(raw: Any, default: int = 0) -> int:
    try:
        return int(raw)
    except Exception:
        return int(default)


def _as_float(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)
    except Exception:
        return float(default)


def _as_optional_int(raw: Any) -> int | None:
    try:
        if raw in (None, ""):
            return None
        return int(raw)
    except Exception:
        return None


def _expression_tradability_label(distance: Any) -> str:
    value = _as_optional_int(distance)
    if value is None:
        return "unknown"
    if value <= 1:
        return "actionable_now"
    if value == 2:
        return "prepare_candidate"
    if value == 3:
        return "watch_but_not_ready"
    return "exploratory_only"


def _information_role_from_fields(*, contribution_role: Any = "", source_trust_tier: Any = "", source_type: Any = "", primaryness: Any = "") -> str:
    contribution = _as_text(contribution_role)
    trust_tier = _as_text(source_trust_tier)
    src_type = _as_text(source_type)
    primary = _as_text(primaryness)
    if contribution == "anchor" or trust_tier == "anchor" or primary == "primary":
        return "originator"
    if contribution == "corroborating" or src_type == "official_disclosure":
        return "corroborator"
    return "amplifier"


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _sql_in_clause(values: list[str]) -> tuple[str, list[str]]:
    placeholders = ",".join(["?"] * len(values))
    return placeholders, [str(value) for value in values]


_TERMINAL_RUN_STATUSES = ("completed", "closed", "resolved", "idle")
_RUN_ORDER_SQL = """
CASE WHEN LOWER(current_status) NOT IN ('completed', 'closed', 'resolved', 'idle') THEN 0 ELSE 1 END,
CASE WHEN COALESCE(task_id, '') <> '' OR COALESCE(trace_id, '') <> '' OR COALESCE(run_id, '') <> '' THEN 0 ELSE 1 END,
CASE health_tone
  WHEN 'danger' THEN 0
  WHEN 'warning' THEN 1
  WHEN 'accent' THEN 2
  WHEN 'success' THEN 3
  ELSE 4
END,
updated_at DESC
"""

_GRAPH_ENTITY_ORDER = (
    "ingress_channel",
    "tenant",
    "team",
    "user",
    "task",
    "trace",
    "run",
    "job",
    "lane",
    "team_run",
    "role",
    "checkpoint",
    "issue",
)

_GRAPH_TYPE_META = {
    "root_run": {"label": "Root Run", "tone": "accent"},
    "ingress_channel": {"label": "Ingress", "tone": "neutral"},
    "tenant": {"label": "Tenant", "tone": "neutral"},
    "team": {"label": "Team", "tone": "neutral"},
    "user": {"label": "User", "tone": "neutral"},
    "task": {"label": "Task", "tone": "accent"},
    "trace": {"label": "Trace", "tone": "accent"},
    "run": {"label": "Advisor Run", "tone": "accent"},
    "job": {"label": "Job", "tone": "warning"},
    "lane": {"label": "Lane", "tone": "warning"},
    "team_run": {"label": "Team Run", "tone": "accent"},
    "role": {"label": "Role", "tone": "neutral"},
    "checkpoint": {"label": "Checkpoint", "tone": "warning"},
    "issue": {"label": "Issue", "tone": "danger"},
    "incident": {"label": "Incident", "tone": "danger"},
    "session": {"label": "Session", "tone": "neutral"},
}


def _is_terminal_status(raw: Any) -> bool:
    return _as_text(raw).lower() in _TERMINAL_RUN_STATUSES


FINAGENT_ROOT = resolve_finagent_root(start=__file__)
FINAGENT_RESEARCH_ROOT = FINAGENT_ROOT / "docs" / "research"
FINAGENT_REVIEW_ROOT = FINAGENT_ROOT / "docs" / "reviews"
FINAGENT_THEME_SPEC_ROOT = FINAGENT_ROOT / "specs" / "theme_runs"
FINAGENT_PLANNING_DOC = FINAGENT_RESEARCH_ROOT / "2026-03-15_current_assets_and_next_planning_options_v1.md"
FINBOT_ARTIFACT_ROOT_CANDIDATES = resolve_finbot_artifact_roots(start=__file__)


def _normalize_key(raw: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _as_text(raw).lower())


def _slug_from_spec_path(path: Path) -> str:
    match = re.match(r"^\d{4}-\d{2}-\d{2}_(.+?)_sentinel_v\d+$", path.stem)
    return match.group(1) if match else path.stem


def _run_report_sort_key(path: Path) -> tuple[int, float]:
    match = re.search(r"_v(\d+)$", path.stem)
    version = int(match.group(1)) if match else 0
    return (version, path.stat().st_mtime)


def _find_latest_run_report(theme_slug: str) -> Path | None:
    paths = sorted(FINAGENT_RESEARCH_ROOT.glob(f"*{theme_slug}*event_engine_run_v*.md"), key=_run_report_sort_key)
    return paths[-1] if paths else None


def _parse_run_report_summary(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {"recommended_posture": "", "best_expression": "", "run_root": ""}
    text = path.read_text(encoding="utf-8", errors="replace")
    posture = ""
    best_expression = ""
    run_root = ""
    patterns = [
        (r"recommended_posture\s*=\s*([^\n]+)", "posture"),
        (r"recommended posture:\s*`?([^\n`]+)`?", "posture"),
        (r"recommended posture\s*[:：]\s*`?([^\n`]+)`?", "posture"),
        (r"best_expression\s*=\s*([^\n]+)", "best_expression"),
        (r"best expression:\s*`?([^\n`]+)`?", "best_expression"),
        (r"best expression\s*[:：]\s*`?([^\n`]+)`?", "best_expression"),
        (r"run_root:\s*`([^`]+)`", "run_root"),
        (r"-\s+`recommended_posture`\s*=\s*`?([^\n`]+)`?", "posture"),
        (r"-\s+`best_expression`\s*=\s*`?([^\n`]+)`?", "best_expression"),
    ]
    for pattern, kind in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        value = _as_text(match.group(1)).strip("`")
        if kind == "posture" and not posture:
            posture = value
        elif kind == "best_expression" and not best_expression:
            best_expression = value
        elif kind == "run_root" and not run_root:
            run_root = value
    return {"recommended_posture": posture, "best_expression": best_expression, "run_root": run_root}


def _read_markdown_sections(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    sections: dict[str, list[str]] = {}
    current = "__root__"
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        heading = re.match(r"^(#{2,4})\s+(.*)$", line.strip())
        if heading:
            current = heading.group(2).strip()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line.rstrip())
    return sections


def _parse_bullet_list(lines: list[str]) -> list[str]:
    return [_as_text(line[2:]) for line in lines if line.strip().startswith("- ")]


def _parse_markdown_table(lines: list[str]) -> list[dict[str, str]]:
    raw_rows = [line.strip() for line in lines if line.strip().startswith("|")]
    if len(raw_rows) < 3:
        return []
    headers = [cell.strip() for cell in raw_rows[0].strip("|").split("|")]
    parsed: list[dict[str, str]] = []
    for row in raw_rows[2:]:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        parsed.append({headers[idx]: cells[idx] for idx in range(len(headers))})
    return parsed


def _parse_assets_planning_doc() -> dict[str, Any]:
    sections = _read_markdown_sections(FINAGENT_PLANNING_DOC)
    theme_assets_lines = sections.get("一、已经正式成形的主题", [])
    current_sources = _parse_bullet_list(sections.get("三、当前已经有的一手源 / 强 source", []))
    current_kols = _parse_bullet_list(sections.get("四、当前已经有的 KOL / 二手源池", []))
    planning_rows = _parse_markdown_table(sections.get("下一步规划选项表", []))
    formed_themes: list[str] = []
    for line in theme_assets_lines:
        if line.strip().startswith("- `") and "`" in line:
            formed_themes.append(_as_text(line.split("`")[1]))
    return {
        "planning_doc": FINAGENT_PLANNING_DOC,
        "formed_themes": formed_themes,
        "strong_sources": current_sources,
        "kols": current_kols,
        "planning_rows": planning_rows,
    }


def _section_excerpt(sections: dict[str, list[str]], *needles: str, max_lines: int = 8) -> str:
    for heading, lines in sections.items():
        normalized_heading = _normalize_key(heading)
        if any(_normalize_key(needle) in normalized_heading for needle in needles):
            excerpt = _render_markdown_excerpt(lines, max_lines=max_lines)
            if excerpt:
                return excerpt
    return ""


def _find_finbot_artifact_root() -> Path | None:
    for candidate in FINBOT_ARTIFACT_ROOT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _research_package_root() -> Path | None:
    artifact_root = _find_finbot_artifact_root()
    if artifact_root is None:
        return None
    root = artifact_root / "opportunities"
    return root if root.exists() else None


def _source_score_root() -> Path | None:
    artifact_root = _find_finbot_artifact_root()
    if artifact_root is None:
        return None
    root = artifact_root / "source_scores"
    return root if root.exists() else None


def _theme_state_root() -> Path | None:
    artifact_root = _find_finbot_artifact_root()
    if artifact_root is None:
        return None
    root = artifact_root / "themes"
    return root if root.exists() else None


def _opportunity_root() -> Path | None:
    artifact_root = _find_finbot_artifact_root()
    if artifact_root is None:
        return None
    root = artifact_root / "opportunities"
    return root if root.exists() else None


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _reader_href(path: Path | None) -> str:
    if path is None:
        return ""
    return f"/v2/dashboard/reader?path={quote(str(path))}"


def _theme_detail_href(theme_slug: str) -> str:
    return f"/v2/dashboard/investor/themes/{quote(theme_slug)}"


def _source_detail_href(source_id: str) -> str:
    return f"/v2/dashboard/investor/sources/{quote(source_id)}"


def _render_markdown_excerpt(lines: list[str], *, max_lines: int = 8) -> str:
    content = [line.strip() for line in lines if _as_text(line)]
    return "\n".join(content[:max_lines]).strip()


def _parse_source_column(raw: str) -> list[str]:
    text = _as_text(raw)
    if not text:
        return []
    return [part.strip("` ").strip() for part in text.split("+") if _as_text(part)]


def _parse_expression_column(raw: str) -> list[str]:
    text = _as_text(raw)
    if not text:
        return []
    return [part.strip("` ").strip() for part in text.split("、") if _as_text(part)]


def _parse_priority_rank(raw: str) -> int:
    match = re.search(r"P(\d+)", _as_text(raw), re.IGNORECASE)
    return int(match.group(1)) if match else 99


def _safe_name_to_slug(raw: str) -> str:
    text = _as_text(raw).lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    text = text.strip("-")
    return text or "item"


def _source_match_tokens(name: str) -> list[str]:
    raw = _as_text(name)
    normalized = _normalize_key(raw)
    tokens = {normalized}
    compact = re.sub(r"\b(ir|earningscall|earnings|call|investorrelations|investor)\b", "", normalized)
    if compact:
        tokens.add(compact)
    for piece in re.split(r"[/+·,&\s]+", raw):
        normalized_piece = _normalize_key(piece)
        if len(normalized_piece) >= 4:
            tokens.add(normalized_piece)
    return [token for token in tokens if token]


def _run_finagent_json(command: list[str], *, timeout: float = 20.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["python3", "-m", "finagent.cli", *command],
            cwd=str(FINAGENT_ROOT),
            env={**os.environ, "PYTHONPATH": str(FINAGENT_ROOT)},
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception:
        return {}
    if completed.returncode != 0:
        return {}
    try:
        return json.loads(completed.stdout)
    except Exception:
        return {}


def _allowed_reader_paths() -> list[Path]:
    allowed = [FINAGENT_ROOT, Path(__file__).resolve().parents[2] / "artifacts" / "finbot"]
    artifact_root = _find_finbot_artifact_root()
    if artifact_root is not None:
        allowed.append(artifact_root)
    return allowed
class DashboardService:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.control_plane = DashboardControlPlane(DashboardControlPlaneConfig.from_app_config(cfg))

    def refresh_control_plane(self, *, force: bool = False) -> dict[str, Any]:
        return self.control_plane.refresh(force=force)

    def _ensure_ready(self) -> dict[str, Any]:
        self.control_plane.maybe_bootstrap()
        meta = self.control_plane.get_meta()
        return {
            "refreshed_at": _as_float(meta.get("refreshed_at")),
            "refresh_status": _as_text(meta.get("refresh_status") or "unknown"),
            "root_count": _as_int(meta.get("root_count")),
            "source_summary": _safe_json_loads(meta.get("source_summary_json"), default={}),
        }

    def _connect(self) -> Any:
        return self.control_plane.connect_read_db()

    def _deserialize_run_row(self, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["upstream"] = _safe_json_loads(data.get("upstream_json"), default=[])
        data["downstream"] = _safe_json_loads(data.get("downstream_json"), default=[])
        data["entity_counts"] = _safe_json_loads(data.get("entity_counts_json"), default={})
        data["summary"] = _safe_json_loads(data.get("summary_json"), default={})
        return data

    def _deserialize_component_row(self, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["details"] = _safe_json_loads(data.get("details_json"), default={})
        data["ok"] = None if data.get("ok") is None else bool(_as_int(data.get("ok")))
        return data

    def _deserialize_incident_row(self, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["metadata"] = _safe_json_loads(data.get("metadata_json"), default={})
        return data

    def _deserialize_cognitive_row(self, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["summary"] = _safe_json_loads(data.get("summary_json"), default={})
        data["details"] = _safe_json_loads(data.get("details_json"), default={})
        return data

    def _deserialize_identity_row(self, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["metadata"] = _safe_json_loads(data.get("metadata_json"), default={})
        return data

    def _graph_root_node(self, run: dict[str, Any]) -> dict[str, Any]:
        root_run_id = _as_text(run.get("root_run_id"))
        title = _as_text(run.get("title")) or root_run_id
        subtitle = " · ".join(
            part
            for part in (
                _as_text(run.get("current_layer")),
                _as_text(run.get("current_status")),
                _as_text(run.get("problem_class")),
            )
            if part
        )
        return {
            "data": {
                "id": f"root:{root_run_id}",
                "entity_id": root_run_id,
                "entity_type": "root_run",
                "label": title,
                "subtitle": subtitle,
                "tone": _as_text(run.get("health_tone") or "accent"),
                "href": f"/v2/dashboard/runs/{root_run_id}",
            }
        }

    def _graph_identity_node(self, identity: dict[str, Any]) -> dict[str, Any]:
        entity_type = _as_text(identity.get("entity_type"))
        entity_id = _as_text(identity.get("entity_id"))
        meta = _GRAPH_TYPE_META.get(entity_type, {"label": entity_type or "Identity", "tone": "neutral"})
        return {
            "data": {
                "id": f"identity:{entity_type}:{entity_id}",
                "entity_id": entity_id,
                "entity_type": entity_type,
                "label": entity_id,
                "subtitle": meta["label"],
                "tone": meta["tone"],
                "href": f"/v2/dashboard/api/graph/neighborhood?id=identity:{entity_type}:{entity_id}&depth=2",
            }
        }

    def _graph_incident_node(self, incident: dict[str, Any]) -> dict[str, Any]:
        incident_key = _as_text(incident.get("incident_key"))
        severity = _as_text(incident.get("severity") or "warning").lower()
        tone = "danger" if severity in {"p0", "p1", "danger", "critical"} else "warning"
        return {
            "data": {
                "id": f"incident:{incident_key}",
                "entity_id": _as_text(incident.get("incident_id") or incident_key),
                "entity_type": "incident",
                "label": _as_text(incident.get("title") or incident.get("incident_id") or incident_key),
                "subtitle": _as_text(incident.get("status") or incident.get("incident_type") or "incident"),
                "tone": tone,
                "href": "/v2/dashboard/incidents",
            }
        }

    def _append_graph_edge(
        self,
        edges: list[dict[str, Any]],
        *,
        seen: set[str],
        source: str,
        target: str,
        kind: str,
        label: str,
    ) -> None:
        edge_id = f"{source}->{target}:{kind}"
        if not source or not target or edge_id in seen:
            return
        seen.add(edge_id)
        edges.append({"data": {"id": edge_id, "source": source, "target": target, "kind": kind, "label": label}})

    def _build_run_lineage_graph(self, root_run_id: str, *, conn: sqlite3.Connection) -> dict[str, Any]:
        run_row = conn.execute("SELECT * FROM run_index WHERE root_run_id=?", (root_run_id,)).fetchone()
        if run_row is None:
            raise KeyError(root_run_id)
        run = self._deserialize_run_row(run_row)
        identities = [
            self._deserialize_identity_row(row)
            for row in conn.execute(
                """
                SELECT *
                FROM identity_map
                WHERE root_run_id=?
                ORDER BY updated_at DESC, entity_type ASC, entity_id ASC
                """,
                (root_run_id,),
            ).fetchall()
        ]
        incidents = [
            self._deserialize_incident_row(row)
            for row in conn.execute(
                """
                SELECT *
                FROM incident_index
                WHERE root_run_id=?
                ORDER BY updated_at DESC, incident_key ASC
                """,
                (root_run_id,),
            ).fetchall()
        ]

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        node_ids: set[str] = set()
        edge_ids: set[str] = set()

        def _append_node(node: dict[str, Any]) -> None:
            node_id = _as_text(((node.get("data") or {}).get("id")))
            if node_id and node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append(node)

        root_node = self._graph_root_node(run)
        _append_node(root_node)

        grouped: dict[str, list[dict[str, Any]]] = {}
        for identity in identities:
            grouped.setdefault(_as_text(identity.get("entity_type")), []).append(identity)
            _append_node(self._graph_identity_node(identity))

        chain_ids: list[str] = []
        for entity_type in _GRAPH_ENTITY_ORDER:
            for identity in grouped.get(entity_type, []):
                chain_ids.append(f"identity:{entity_type}:{_as_text(identity.get('entity_id'))}")
        chain_ids.insert(min(len(chain_ids), 6), root_node["data"]["id"])
        if root_node["data"]["id"] not in chain_ids:
            chain_ids.append(root_node["data"]["id"])
        for source, target in zip(chain_ids, chain_ids[1:]):
            self._append_graph_edge(edges, seen=edge_ids, source=source, target=target, kind="lineage", label="lineage")

        for entity_type, items in grouped.items():
            if entity_type in _GRAPH_ENTITY_ORDER:
                continue
            for identity in items:
                self._append_graph_edge(
                    edges,
                    seen=edge_ids,
                    source=root_node["data"]["id"],
                    target=f"identity:{entity_type}:{_as_text(identity.get('entity_id'))}",
                    kind="context",
                    label=entity_type or "context",
                )

        issue_anchor = next((node_id for node_id in reversed(chain_ids) if node_id.startswith("identity:issue:")), root_node["data"]["id"])
        for incident in incidents:
            incident_node = self._graph_incident_node(incident)
            _append_node(incident_node)
            self._append_graph_edge(
                edges,
                seen=edge_ids,
                source=issue_anchor,
                target=incident_node["data"]["id"],
                kind="incident",
                label=_as_text(incident.get("status") or "incident"),
            )

        return {
            "run": run,
            "nodes": nodes,
            "edges": edges,
            "incident_count": len(incidents),
            "identity_count": len(identities),
        }

    def _lineage_seed_runs(self, *, conn: sqlite3.Connection, limit: int = 12) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT *
            FROM run_index
            ORDER BY
            """
            + _RUN_ORDER_SQL
            + """
            LIMIT ?
            """,
            (max(1, min(int(limit), 50)),),
        ).fetchall()
        return [self._deserialize_run_row(row) for row in rows]

    def overview_snapshot(self, *, limit: int = 12) -> dict[str, Any]:
        control_plane = self._ensure_ready()
        limit = max(1, min(int(limit), 50))
        with self._connect() as conn:
            active_runs = _as_int(conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM run_index
                WHERE LOWER(current_status) NOT IN ('completed', 'closed', 'resolved', 'idle')
                """
            ).fetchone()["count"])
            blocked_runs = _as_int(conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM run_index
                WHERE health_tone IN ('danger', 'warning')
                """
            ).fetchone()["count"])
            guards_blocking = _as_int(conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM component_health
                WHERE plane='runtime' AND severity IN ('danger', 'warning')
                """
            ).fetchone()["count"])
            open_incidents = _as_int(conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM incident_index
                WHERE incident_type='incident' AND LOWER(status) IN ('open', 'in_progress')
                """
            ).fetchone()["count"])
            open_client_issues = _as_int(conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM incident_index
                WHERE incident_type='client_issue' AND LOWER(status) IN ('open', 'in_progress')
                """
            ).fetchone()["count"])
            problem_breakdown = _rows_to_dicts(
                conn.execute(
                    """
                    SELECT problem_class, COUNT(*) AS count
                    FROM run_index
                    GROUP BY problem_class
                    ORDER BY count DESC, problem_class ASC
                    """
                ).fetchall()
            )
            ingress_breakdown = _rows_to_dicts(
                conn.execute(
                    """
                    SELECT COALESCE(ingress_channel, 'unknown') AS ingress_channel, COUNT(*) AS count
                    FROM run_index
                    GROUP BY COALESCE(ingress_channel, 'unknown')
                    ORDER BY count DESC, ingress_channel ASC
                    """
                ).fetchall()
            )
            attention_runs = [
                self._deserialize_run_row(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM run_index
                    ORDER BY
                      CASE health_tone
                        WHEN 'danger' THEN 0
                        WHEN 'warning' THEN 1
                        WHEN 'accent' THEN 2
                        ELSE 3
                      END,
                      updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            ]
            component_health = [
                self._deserialize_component_row(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM component_health
                    ORDER BY
                      CASE severity
                        WHEN 'danger' THEN 0
                        WHEN 'warning' THEN 1
                        ELSE 2
                      END,
                      signal_ts DESC
                    """
                ).fetchall()
            ]
            incident_preview = [
                self._deserialize_incident_row(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM incident_index
                    ORDER BY
                      CASE LOWER(status)
                        WHEN 'open' THEN 0
                        WHEN 'in_progress' THEN 1
                        ELSE 2
                      END,
                      updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            ]
            cognitive_global = conn.execute(
                """
                SELECT *
                FROM cognitive_snapshot
                WHERE scope='global'
                ORDER BY ts DESC
                LIMIT 1
                """
            ).fetchone()
        cognitive_summary = self._deserialize_cognitive_row(cognitive_global) if cognitive_global else {"summary": {}}
        cognitive_signals = _as_int((cognitive_summary.get("summary") or {}).get("signal_rows"))
        return {
            "generated_at": time.time(),
            "control_plane": control_plane,
            "summary": {
                "active_runs": active_runs,
                "blocked_runs": blocked_runs,
                "guards_blocking": guards_blocking,
                "open_incidents": open_incidents,
                "open_client_issues": open_client_issues,
                "cognitive_signals": cognitive_signals,
            },
            "hero_metrics": [
                {"label": "Active Runs", "value": active_runs, "tone": "accent"},
                {"label": "Blocked Runs", "value": blocked_runs, "tone": "warning" if blocked_runs else "success"},
                {"label": "Blocking Guards", "value": guards_blocking, "tone": "warning" if guards_blocking else "success"},
                {"label": "Open Incidents", "value": open_incidents, "tone": "warning" if open_incidents else "success"},
                {"label": "Open Client Issues", "value": open_client_issues, "tone": "warning" if open_client_issues else "success"},
                {"label": "OpenMind Signals", "value": cognitive_signals, "tone": "accent"},
            ],
            "problem_breakdown": problem_breakdown,
            "ingress_breakdown": ingress_breakdown,
            "attention_runs": attention_runs,
            "component_health": component_health,
            "incident_preview": incident_preview,
            "cognitive_global": cognitive_summary,
        }

    def runs_snapshot(
        self,
        *,
        q: str = "",
        status: str = "",
        problem: str = "",
        ingress: str = "",
        running_only: bool = False,
        limit: int = 100,
        task_only: bool = False,
    ) -> dict[str, Any]:
        control_plane = self._ensure_ready()
        limit = max(1, min(int(limit), 200))
        clauses: list[str] = []
        params: list[Any] = []

        search = _as_text(q)
        if search:
            like = f"%{search}%"
            clauses.append(
                "("
                "root_run_id LIKE ? OR COALESCE(task_id, '') LIKE ? OR COALESCE(task_ref, '') LIKE ? "
                "OR COALESCE(title, '') LIKE ? OR COALESCE(trace_id, '') LIKE ? OR COALESCE(run_id, '') LIKE ? "
                "OR COALESCE(job_id, '') LIKE ? OR COALESCE(team_id, '') LIKE ? OR COALESCE(tenant_id, '') LIKE ? "
                "OR COALESCE(user_id, '') LIKE ? OR COALESCE(session_id, '') LIKE ?"
                ")"
            )
            params.extend([like] * 11)
        if _as_text(status):
            clauses.append("LOWER(current_status) = LOWER(?)")
            params.append(_as_text(status))
        if _as_text(problem):
            clauses.append("LOWER(problem_class) = LOWER(?)")
            params.append(_as_text(problem))
        if _as_text(ingress):
            clauses.append("LOWER(COALESCE(ingress_channel, '')) = LOWER(?)")
            params.append(_as_text(ingress))
        if running_only:
            clauses.append("LOWER(current_status) NOT IN ('completed', 'closed', 'resolved', 'idle')")
        if task_only:
            clauses.append("COALESCE(task_id, '') <> ''")

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with self._connect() as conn:
            rows = [
                self._deserialize_run_row(row)
                for row in conn.execute(
                    f"""
                    SELECT *
                    FROM run_index
                    {where_sql}
                    ORDER BY
                      CASE health_tone
                        WHEN 'danger' THEN 0
                        WHEN 'warning' THEN 1
                        WHEN 'accent' THEN 2
                        ELSE 3
                      END,
                      updated_at DESC
                    LIMIT ?
                    """,
                    [*params, limit],
                ).fetchall()
            ]
            summary = conn.execute(
                f"""
                SELECT
                  COUNT(*) AS total,
                  SUM(CASE WHEN LOWER(current_status) NOT IN ('completed', 'closed', 'resolved', 'idle') THEN 1 ELSE 0 END) AS active,
                  SUM(CASE WHEN health_tone IN ('danger', 'warning') THEN 1 ELSE 0 END) AS attention,
                  SUM(CASE WHEN problem_class='job' THEN 1 ELSE 0 END) AS job_problems,
                  SUM(CASE WHEN problem_class='lane_continuity' THEN 1 ELSE 0 END) AS lane_problems,
                  SUM(CASE WHEN problem_class='team_role_or_checkpoint' THEN 1 ELSE 0 END) AS team_problems
                FROM run_index
                {where_sql}
                """,
                params,
            ).fetchone()
        return {
            "generated_at": time.time(),
            "control_plane": control_plane,
            "filters": {
                "q": search,
                "status": _as_text(status),
                "problem": _as_text(problem),
                "ingress": _as_text(ingress),
                "running_only": bool(running_only),
                "task_only": bool(task_only),
                "limit": limit,
            },
            "summary": {
                "total": _as_int(summary["total"] if summary else 0),
                "active": _as_int(summary["active"] if summary else 0),
                "attention": _as_int(summary["attention"] if summary else 0),
                "job_problems": _as_int(summary["job_problems"] if summary else 0),
                "lane_problems": _as_int(summary["lane_problems"] if summary else 0),
                "team_problems": _as_int(summary["team_problems"] if summary else 0),
            },
            "runs": rows,
        }

    def run_detail(self, root_run_id: str) -> dict[str, Any]:
        control_plane = self._ensure_ready()
        root_run_id = _as_text(root_run_id)
        with self._connect() as conn:
            run_row = conn.execute(
                "SELECT * FROM run_index WHERE root_run_id=?",
                (root_run_id,),
            ).fetchone()
            if run_row is None:
                raise KeyError(root_run_id)
            timeline = [
                {
                    **dict(row),
                    "payload": _safe_json_loads(row["payload_json"], default={}),
                }
                for row in conn.execute(
                    """
                    SELECT *
                    FROM run_timeline
                    WHERE root_run_id=?
                    ORDER BY event_rank ASC
                    """,
                    (root_run_id,),
                ).fetchall()
            ]
            identities = [
                self._deserialize_identity_row(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM identity_map
                    WHERE root_run_id=?
                    ORDER BY entity_type ASC, entity_id ASC
                    """,
                    (root_run_id,),
                ).fetchall()
            ]
            incidents = [
                self._deserialize_incident_row(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM incident_index
                    WHERE root_run_id=?
                    ORDER BY updated_at DESC, incident_key ASC
                    """,
                    (root_run_id,),
                ).fetchall()
            ]
            cognitive = [
                self._deserialize_cognitive_row(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM cognitive_snapshot
                    WHERE root_run_id=? OR scope='global'
                    ORDER BY scope DESC, ts DESC
                    """,
                    (root_run_id,),
                ).fetchall()
            ]
        run = self._deserialize_run_row(run_row)
        return {
            "generated_at": time.time(),
            "control_plane": control_plane,
            "run": run,
            "timeline": timeline,
            "identities": identities,
            "incidents": incidents,
            "cognitive": cognitive,
        }

    def runtime_snapshot(self, *, limit: int = 20) -> dict[str, Any]:
        control_plane = self._ensure_ready()
        limit = max(1, min(int(limit), 100))
        with self._connect() as conn:
            components = [
                self._deserialize_component_row(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM component_health
                    WHERE plane IN ('execution', 'runtime')
                    ORDER BY
                      CASE severity
                        WHEN 'danger' THEN 0
                        WHEN 'warning' THEN 1
                        ELSE 2
                      END,
                      signal_ts DESC
                    """
                ).fetchall()
            ]
            attention_runs = [
                self._deserialize_run_row(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM run_index
                    WHERE problem_class IN ('job', 'lane_continuity', 'team_role_or_checkpoint', 'issue')
                    ORDER BY
                      CASE health_tone
                        WHEN 'danger' THEN 0
                        WHEN 'warning' THEN 1
                        ELSE 2
                      END,
                      updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            ]
            incidents = [
                self._deserialize_incident_row(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM incident_index
                    WHERE LOWER(status) IN ('open', 'in_progress')
                    ORDER BY severity DESC, updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            ]
        guards_blocking = sum(1 for row in components if row["plane"] == "runtime" and row["severity"] in {"danger", "warning"})
        system_health = "blocked" if any(row["severity"] == "danger" for row in components) else ("degraded" if guards_blocking else "healthy")
        return {
            "generated_at": time.time(),
            "control_plane": control_plane,
            "summary": {
                "system_health": system_health,
                "guards_blocking": guards_blocking,
                "attention_runs": len(attention_runs),
                "open_incidents": len([row for row in incidents if row["incident_type"] == "incident"]),
                "open_client_issues": len([row for row in incidents if row["incident_type"] == "client_issue"]),
            },
            "components": components,
            "attention_runs": attention_runs,
            "incidents": incidents,
        }

    def identity_snapshot(self, *, limit: int = 50) -> dict[str, Any]:
        control_plane = self._ensure_ready()
        limit = max(1, min(int(limit), 200))
        with self._connect() as conn:
            summary = conn.execute(
                """
                SELECT
                  COUNT(*) AS total_roots,
                  SUM(CASE WHEN COALESCE(task_id, '') = '' THEN 1 ELSE 0 END) AS missing_task,
                  SUM(CASE WHEN COALESCE(trace_id, '') = '' THEN 1 ELSE 0 END) AS missing_trace,
                  SUM(CASE WHEN COALESCE(ingress_channel, '') = '' THEN 1 ELSE 0 END) AS missing_ingress
                FROM run_index
                """
            ).fetchone()
            mapped_entities = _as_int(conn.execute("SELECT COUNT(*) AS count FROM identity_map").fetchone()["count"])
            unmapped_incidents = _as_int(
                conn.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM incident_index
                    WHERE COALESCE(root_run_id, '') = ''
                    """
                ).fetchone()["count"]
            )
            mappings = [
                self._deserialize_identity_row(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM identity_map
                    ORDER BY updated_at DESC, entity_type ASC, entity_id ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            ]
            entity_breakdown = _rows_to_dicts(
                conn.execute(
                    """
                    SELECT entity_type, COUNT(*) AS count
                    FROM identity_map
                    GROUP BY entity_type
                    ORDER BY count DESC, entity_type ASC
                    """
                ).fetchall()
            )
            gaps = [
                self._deserialize_run_row(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM run_index
                    WHERE COALESCE(task_id, '') = ''
                       OR COALESCE(trace_id, '') = ''
                       OR COALESCE(ingress_channel, '') = ''
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            ]
        return {
            "generated_at": time.time(),
            "control_plane": control_plane,
            "summary": {
                "total_roots": _as_int(summary["total_roots"] if summary else 0),
                "missing_task": _as_int(summary["missing_task"] if summary else 0),
                "missing_trace": _as_int(summary["missing_trace"] if summary else 0),
                "missing_ingress": _as_int(summary["missing_ingress"] if summary else 0),
                "mapped_entities": mapped_entities,
                "unmapped_incidents": unmapped_incidents,
            },
            "entity_breakdown": entity_breakdown,
            "mappings": mappings,
            "gaps": gaps,
        }

    def incident_snapshot(
        self,
        *,
        q: str = "",
        status: str = "",
        incident_type: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        control_plane = self._ensure_ready()
        limit = max(1, min(int(limit), 200))
        clauses: list[str] = []
        params: list[Any] = []
        search = _as_text(q)
        if search:
            like = f"%{search}%"
            clauses.append(
                "(incident_id LIKE ? OR title LIKE ? OR COALESCE(project, '') LIKE ? OR COALESCE(category, '') LIKE ? OR COALESCE(root_run_id, '') LIKE ?)"
            )
            params.extend([like] * 5)
        if _as_text(status):
            clauses.append("LOWER(status) = LOWER(?)")
            params.append(_as_text(status))
        if _as_text(incident_type):
            clauses.append("LOWER(incident_type) = LOWER(?)")
            params.append(_as_text(incident_type))
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = [
                self._deserialize_incident_row(row)
                for row in conn.execute(
                    f"""
                    SELECT *
                    FROM incident_index
                    {where_sql}
                    ORDER BY
                      CASE LOWER(status)
                        WHEN 'open' THEN 0
                        WHEN 'in_progress' THEN 1
                        ELSE 2
                      END,
                      updated_at DESC
                    LIMIT ?
                    """,
                    [*params, limit],
                ).fetchall()
            ]
            summary = conn.execute(
                f"""
                SELECT
                  COUNT(*) AS total,
                  SUM(CASE WHEN incident_type='incident' THEN 1 ELSE 0 END) AS incidents,
                  SUM(CASE WHEN incident_type='client_issue' THEN 1 ELSE 0 END) AS client_issues,
                  SUM(CASE WHEN LOWER(status) IN ('open', 'in_progress') THEN 1 ELSE 0 END) AS open_total
                FROM incident_index
                {where_sql}
                """,
                params,
            ).fetchone()
        return {
            "generated_at": time.time(),
            "control_plane": control_plane,
            "filters": {"q": search, "status": _as_text(status), "incident_type": _as_text(incident_type), "limit": limit},
            "summary": {
                "total": _as_int(summary["total"] if summary else 0),
                "incidents": _as_int(summary["incidents"] if summary else 0),
                "client_issues": _as_int(summary["client_issues"] if summary else 0),
                "open_total": _as_int(summary["open_total"] if summary else 0),
            },
            "incidents": rows,
        }

    def cognitive_snapshot(self) -> dict[str, Any]:
        control_plane = self._ensure_ready()
        with self._connect() as conn:
            globals_ = [
                self._deserialize_cognitive_row(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM cognitive_snapshot
                    WHERE scope='global'
                    ORDER BY ts DESC
                    """
                ).fetchall()
            ]
            overlays = [
                self._deserialize_cognitive_row(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM cognitive_snapshot
                    WHERE scope='root'
                    ORDER BY ts DESC
                    LIMIT 50
                    """
                ).fetchall()
            ]
            roots_with_trace = _as_int(
                conn.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM run_index
                    WHERE COALESCE(trace_id, '') <> ''
                    """
                ).fetchone()["count"]
            )
        return {
            "generated_at": time.time(),
            "control_plane": control_plane,
            "summary": {
                "global_snapshots": len(globals_),
                "root_overlays": len(overlays),
                "roots_with_trace": roots_with_trace,
            },
            "globals": globals_,
            "overlays": overlays,
        }

    def graph_lineage(self, *, root_run_id: str = "", limit: int = 12) -> dict[str, Any]:
        control_plane = self._ensure_ready()
        now = time.time()
        with self._connect() as conn:
            seed_runs = self._lineage_seed_runs(conn=conn, limit=limit)
            selected_root_run_id = _as_text(root_run_id) or (_as_text(seed_runs[0].get("root_run_id")) if seed_runs else "")
            graph = self._build_run_lineage_graph(selected_root_run_id, conn=conn) if selected_root_run_id else {"run": {}, "nodes": [], "edges": [], "incident_count": 0, "identity_count": 0}
        return {
            "generated_at": now,
            "control_plane": control_plane,
            "view": "execution_lineage",
            "selected_root_run_id": selected_root_run_id,
            "summary": {
                "runs_visible": len(seed_runs),
                "nodes": len(graph["nodes"]),
                "edges": len(graph["edges"]),
                "incident_count": graph["incident_count"],
                "identity_count": graph["identity_count"],
            },
            "roots": [
                {
                    "root_run_id": _as_text(row.get("root_run_id")),
                    "title": _as_text(row.get("title")) or _as_text(row.get("root_run_id")),
                    "status": _as_text(row.get("current_status")),
                    "layer": _as_text(row.get("current_layer")),
                    "problem_class": _as_text(row.get("problem_class")),
                    "tone": _as_text(row.get("health_tone") or "neutral"),
                }
                for row in seed_runs
            ],
            "graph": {"nodes": graph["nodes"], "edges": graph["edges"]},
            "legend": [
                {"type": "root_run", "label": "Root Run", "tone": "accent"},
                {"type": "task", "label": "Task / Trace / Run", "tone": "accent"},
                {"type": "job", "label": "Job / Lane / Checkpoint", "tone": "warning"},
                {"type": "incident", "label": "Issue / Incident", "tone": "danger"},
            ],
        }

    def graph_neighborhood(self, node_id: str, *, depth: int = 2, limit_roots: int = 6) -> dict[str, Any]:
        control_plane = self._ensure_ready()
        node_id = _as_text(node_id)
        depth = max(1, min(int(depth), 3))
        limit_roots = max(1, min(int(limit_roots), 12))
        roots: list[str] = []
        with self._connect() as conn:
            if node_id.startswith("root:"):
                roots = [_as_text(node_id.split(":", 1)[1])]
            elif node_id.startswith("identity:"):
                _, entity_type, entity_id = node_id.split(":", 2)
                rows = conn.execute(
                    """
                    SELECT DISTINCT root_run_id
                    FROM identity_map
                    WHERE entity_type=? AND entity_id=?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (entity_type, entity_id, limit_roots),
                ).fetchall()
                roots = [_as_text(row["root_run_id"]) for row in rows if _as_text(row["root_run_id"])]
            elif node_id.startswith("incident:"):
                row = conn.execute(
                    "SELECT root_run_id FROM incident_index WHERE incident_key=?",
                    (_as_text(node_id.split(":", 1)[1]),),
                ).fetchone()
                roots = [_as_text(row["root_run_id"])] if row and _as_text(row["root_run_id"]) else []

            merged_nodes: dict[str, dict[str, Any]] = {}
            merged_edges: dict[str, dict[str, Any]] = {}
            for root_run_id in roots[:limit_roots]:
                graph = self._build_run_lineage_graph(root_run_id, conn=conn)
                for node in graph["nodes"]:
                    merged_nodes[_as_text((node.get("data") or {}).get("id"))] = node
                for edge in graph["edges"]:
                    merged_edges[_as_text((edge.get("data") or {}).get("id"))] = edge
        return {
            "generated_at": time.time(),
            "control_plane": control_plane,
            "view": "execution_neighborhood",
            "node_id": node_id,
            "depth": depth,
            "roots": roots[:limit_roots],
            "graph": {"nodes": list(merged_nodes.values()), "edges": list(merged_edges.values())},
            "summary": {"roots": len(roots[:limit_roots]), "nodes": len(merged_nodes), "edges": len(merged_edges)},
        }

    def graph_snapshot(self) -> dict[str, Any]:
        snapshot = self.graph_lineage(limit=12)
        snapshot["status_cards"] = [
            {"label": "Runs Visible", "value": snapshot["summary"]["runs_visible"], "tone": "accent"},
            {"label": "Nodes In View", "value": snapshot["summary"]["nodes"], "tone": "accent"},
            {"label": "Incidents Linked", "value": snapshot["summary"]["incident_count"], "tone": "warning" if snapshot["summary"]["incident_count"] else "success"},
        ]
        return snapshot

    def _theme_spec_paths(self) -> list[Path]:
        latest_by_slug: dict[str, Path] = {}
        for path in sorted(FINAGENT_THEME_SPEC_ROOT.glob("*_sentinel_v*.yaml")):
            slug = _slug_from_spec_path(path)
            current = latest_by_slug.get(slug)
            if current is None or _run_report_sort_key(path) >= _run_report_sort_key(current):
                latest_by_slug[slug] = path
        return sorted(latest_by_slug.values())

    def _load_theme_spec(self, path: Path) -> dict[str, Any]:
        if yaml is None or not path.exists():
            return {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        return data

    def _planning_snapshot(self) -> dict[str, Any]:
        return _parse_assets_planning_doc()

    def _theme_radar_snapshot(self) -> dict[str, Any]:
        payload = _run_finagent_json(["theme-radar-board", "--limit", "12"])
        return payload if isinstance(payload, dict) else {}

    def _source_board_snapshot(self) -> dict[str, Any]:
        payload = _run_finagent_json(["source-board"])
        return payload if isinstance(payload, dict) else {}

    def _finbot_inbox_snapshot(self, *, limit: int = 8) -> list[dict[str, Any]]:
        artifact_root = _find_finbot_artifact_root()
        if artifact_root is None:
            return []
        pending = artifact_root / "inbox" / "pending"
        if not pending.exists():
            return []
        items: list[dict[str, Any]] = []
        for path in sorted(pending.glob("*.json"), key=lambda candidate: candidate.stat().st_mtime, reverse=True)[:limit]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            nested = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
            logical_key = _as_text(nested.get("logical_key"))
            category = _as_text(payload.get("category") or payload.get("type"))
            candidate_id = _as_text(nested.get("candidate_id"))
            thesis_name = _as_text(nested.get("thesis_name"))
            next_action = _as_text(nested.get("next_action") or payload.get("next_action"))
            topic = (
                _as_text(nested.get("theme_slug"))
                or _as_text(nested.get("scope"))
                or _as_text(payload.get("topic"))
            )
            thesis = thesis_name or _as_text(nested.get("thesis_statement")) or _as_text(payload.get("thesis"))
            theme_slug = _as_text(nested.get("theme_slug"))
            detail_href = _theme_detail_href(theme_slug) if theme_slug else ""
            related_themes = []
            for row in nested.get("related_themes") or []:
                if not isinstance(row, dict):
                    continue
                related_themes.append(
                    {
                        "theme_slug": _as_text(row.get("theme_slug")),
                        "title": _as_text(row.get("title")),
                        "detail_href": _as_text(row.get("detail_href")),
                        "best_expression": _as_text(row.get("best_expression")),
                    }
                )
            items.append(
                {
                    "item_id": _as_text(payload.get("item_id") or path.stem),
                    "path": str(path),
                    "reader_href": _reader_href(Path(_as_text(nested.get("markdown_path")))) if category == "research_package" and _as_text(nested.get("markdown_path")) else _reader_href(path),
                    "title": _as_text(payload.get("title") or topic or category or path.stem),
                    "topic": topic,
                    "type": category,
                    "category": category,
                    "severity": _as_text(payload.get("severity")),
                    "summary": _as_text(payload.get("summary")),
                    "thesis": thesis,
                    "logical_key": logical_key,
                    "candidate_id": candidate_id,
                    "next_action": next_action,
                    "theme_slug": theme_slug,
                    "detail_href": detail_href,
                    "opportunity_href": f"/v2/dashboard/investor/opportunities/{candidate_id}" if candidate_id else "",
                    "next_proving_milestone": _as_text(nested.get("next_proving_milestone")),
                    "current_decision": _as_text(nested.get("current_decision")),
                    "best_expression_today": _as_text(nested.get("best_expression_today")),
                    "best_absorption_theme": _as_text(nested.get("best_absorption_theme")),
                    "why_not_investable_yet": _as_text(nested.get("why_not_investable_yet")),
                    "markdown_path": _as_text(nested.get("markdown_path")),
                    "json_path": _as_text(nested.get("json_path")),
                    "suggested_sources": list(nested.get("suggested_sources") or []),
                    "key_sources": list(nested.get("key_sources") or []),
                    "forcing_events": list(nested.get("forcing_events") or []),
                    "research_gaps": list(nested.get("research_gaps") or []),
                    "research_questions": list(nested.get("research_questions") or []),
                    "related_themes": related_themes,
                    "created_at": _as_text(payload.get("created_at")),
                    "updated_at": _as_text(payload.get("updated_at")),
                }
            )
        return items

    def _research_package_lookup(self) -> dict[str, dict[str, Any]]:
        root = _research_package_root()
        if root is None:
            return {}
        lookup: dict[str, dict[str, Any]] = {}
        for latest in root.glob("*/latest.json"):
            payload = _load_json_file(latest)
            candidate_id = _as_text(payload.get("candidate_id"))
            if not candidate_id:
                continue
            lookup[candidate_id] = {
                **payload,
                "reader_href": _reader_href(Path(_as_text(payload.get("markdown_path")))) if _as_text(payload.get("markdown_path")) else "",
                "json_reader_href": _reader_href(Path(_as_text(payload.get("json_path")))) if _as_text(payload.get("json_path")) else "",
                "context_reader_href": _reader_href(Path(_as_text(payload.get("context_path")))) if _as_text(payload.get("context_path")) else "",
            }
        return lookup

    def _source_score_lookup(self) -> dict[str, dict[str, Any]]:
        root = _source_score_root()
        if root is None:
            return {}
        payload = _load_json_file(root / "latest.json")
        rows = payload.get("sources") if isinstance(payload.get("sources"), list) else []
        lookup: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = _as_text(row.get("source_id") or row.get("name"))
            if not key:
                continue
            lookup[key] = dict(row)
        return lookup

    def _theme_state_lookup(self) -> dict[str, dict[str, Any]]:
        root = _theme_state_root()
        if root is None:
            return {}
        lookup: dict[str, dict[str, Any]] = {}
        for latest in root.glob("*/latest.json"):
            payload = _load_json_file(latest)
            theme_slug = _as_text(payload.get("theme_slug"))
            if not theme_slug:
                continue
            lookup[theme_slug] = payload
        return lookup

    def _theme_state_history(self, theme_slug: str, *, limit: int = 6) -> list[dict[str, Any]]:
        root = _theme_state_root()
        if root is None:
            return []
        history_dir = root / _safe_name_to_slug(theme_slug) / "history"
        if not history_dir.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(history_dir.glob("*.json"), reverse=True)[:limit]:
            payload = _load_json_file(path)
            if not payload:
                continue
            rows.append(
                {
                    "generated_at": _as_float(payload.get("generated_at")),
                    "recommended_posture": _as_text(payload.get("recommended_posture")),
                    "best_expression": _as_text(payload.get("best_expression")),
                    "why_now": _as_text(payload.get("why_now")),
                    "action_distance": _as_text(payload.get("action_distance")),
                    "history": dict(payload.get("history") or {}),
                }
            )
        rows.sort(key=lambda item: item["generated_at"], reverse=True)
        return rows

    def _opportunity_history(self, candidate_id: str, *, limit: int = 6) -> list[dict[str, Any]]:
        root = _opportunity_root()
        if root is None:
            return []
        history_root = root / _safe_name_to_slug(candidate_id.replace("candidate_", "")) / "history"
        if not history_root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(history_root.glob("*/research_package.json"), reverse=True)[:limit]:
            payload = _load_json_file(path)
            if not payload:
                continue
            rows.append(
                {
                    "generated_at": _as_float(payload.get("generated_at")),
                    "current_decision": _as_text(payload.get("current_decision")),
                    "best_expression_today": _as_text(payload.get("best_expression_today")),
                    "next_proving_milestone": _as_text(payload.get("next_proving_milestone")),
                    "why_not_investable_yet": _as_text(payload.get("why_not_investable_yet")),
                    "distance_to_action": _as_text(payload.get("distance_to_action")),
                    "history": dict(payload.get("history") or {}),
                    "reader_href": _reader_href(path),
                }
            )
        rows.sort(key=lambda item: item["generated_at"], reverse=True)
        return rows

    def _source_score_history(self, source_id: str, name: str, *, limit: int = 8) -> list[dict[str, Any]]:
        root = _source_score_root()
        if root is None:
            return []
        history_dir = root / "history"
        if not history_dir.exists():
            return []
        prefixes = {_safe_name_to_slug(source_id)}
        if name:
            prefixes.add(_safe_name_to_slug(name))
        rows: list[dict[str, Any]] = []
        for path in sorted(history_dir.glob("*.json"), reverse=True):
            stem = path.stem
            if not any(stem.startswith(prefix) for prefix in prefixes if prefix):
                continue
            payload = _load_json_file(path)
            if not payload:
                continue
            rows.append(
                {
                    "generated_at": _as_float(payload.get("last_supported_at") or path.stat().st_mtime),
                    "quality_score": _as_float(payload.get("quality_score")),
                    "quality_band": _as_text(payload.get("quality_band")),
                    "trend_label": _as_text(payload.get("trend_label")),
                    "supported_claim_count": _as_int(payload.get("supported_claim_count")),
                    "load_bearing_claim_count": _as_int(payload.get("load_bearing_claim_count")),
                    "packages_seen": _as_int(payload.get("packages_seen")),
                    "quality_explanation": _as_text(payload.get("quality_explanation")),
                }
            )
            if len(rows) >= limit:
                break
        rows.sort(key=lambda item: item["generated_at"], reverse=True)
        return rows

    def _opportunity_cards(self, *, themes: list[dict[str, Any]], inbox_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raw_items = list(self._theme_radar_snapshot().get("items") or [])
        package_lookup = self._research_package_lookup()
        theme_lookup: dict[str, list[dict[str, Any]]] = {}
        for theme in themes:
            for opportunity in theme.get("related_opportunities", []) or []:
                candidate_id = _as_text(opportunity.get("candidate_id"))
                if not candidate_id:
                    continue
                theme_lookup.setdefault(candidate_id, []).append(
                    {
                        "theme_slug": _as_text(theme.get("theme_slug")),
                        "title": _as_text(theme.get("title")),
                        "detail_href": _as_text(theme.get("detail_href")),
                        "best_expression": _as_text(theme.get("best_expression")),
                    }
                )
        brief_lookup = {
            _as_text(item.get("candidate_id")): item
            for item in inbox_items
            if _as_text(item.get("category")) == "deepening_brief" and _as_text(item.get("candidate_id"))
        }
        cards: list[dict[str, Any]] = []
        for item in raw_items:
            candidate_id = _as_text(item.get("candidate_id"))
            related_themes = theme_lookup.get(candidate_id, [])
            brief = brief_lookup.get(candidate_id, {})
            package = package_lookup.get(candidate_id, {})
            cards.append(
                {
                    **item,
                    "detail_href": f"/v2/dashboard/investor/opportunities/{candidate_id}" if candidate_id else "",
                    "reader_href": _as_text(brief.get("reader_href")),
                    "related_themes": related_themes,
                    "suggested_sources": list(brief.get("suggested_sources") or []),
                    "brief_summary": _as_text(brief.get("summary")),
                    "brief_next_action": _as_text(brief.get("next_action") or item.get("next_action")),
                    "brief_next_proving_milestone": _as_text(brief.get("next_proving_milestone") or item.get("next_proving_milestone")),
                    "research_package": package,
                }
            )
        return cards

    def _theme_matches_planning_rows(self, theme: dict[str, Any], planning_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
        slug_norm = _normalize_key(theme.get("theme_slug"))
        title_norm = _normalize_key(theme.get("title"))
        matches: list[dict[str, Any]] = []
        for row in planning_rows:
            theme_value = _as_text(row.get("主题"))
            theme_norm = _normalize_key(theme_value)
            if slug_norm and slug_norm in theme_norm or title_norm and title_norm in theme_norm:
                matches.append(
                    {
                        "theme": theme_value,
                        "logic": _as_text(row.get("核心逻辑")),
                        "expressions": _parse_expression_column(_as_text(row.get("标的 / 表达"))),
                        "priority": _as_text(row.get("优先级")),
                        "priority_rank": _parse_priority_rank(_as_text(row.get("优先级"))),
                        "sources": _parse_source_column(_as_text(row.get("KOL / 源"))),
                        "why": _as_text(row.get("为什么选")),
                    }
                )
        return matches

    def _theme_matches_opportunities(self, theme: dict[str, Any], radar_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        title = _as_text(theme.get("title"))
        slug = _as_text(theme.get("theme_slug"))
        grammar_keys = {_as_text(item.get("grammar_key")) for item in theme.get("sentinels", [])}
        keywords = {_normalize_key(title), _normalize_key(slug)}
        if "silicon_photonics" in slug:
            keywords.update({_normalize_key("CPO"), _normalize_key("硅光"), _normalize_key("TSMC"), _normalize_key("Broadcom")})
        if "memory_bifurcation" in slug:
            keywords.update({_normalize_key("HBM"), _normalize_key("SK Hynix"), _normalize_key("DDR5")})
        if "transformer" in slug or "ai_energy_onsite_power" in slug:
            keywords.update({_normalize_key("变压器"), _normalize_key("AI 电力"), _normalize_key("onsite power")})
        matches: list[dict[str, Any]] = []
        for item in radar_items:
            blob = " ".join(
                [
                    _as_text(item.get("candidate_id")),
                    _as_text(item.get("thesis_name")),
                    _as_text(item.get("note")),
                    _as_text(item.get("residual_class")),
                ]
            )
            normalized_blob = _normalize_key(blob)
            if any(keyword and keyword in normalized_blob for keyword in keywords):
                matches.append(
                    {
                        "candidate_id": _as_text(item.get("candidate_id")),
                        "thesis_name": _as_text(item.get("thesis_name")),
                        "route": _as_text(item.get("route")),
                        "residual_class": _as_text(item.get("residual_class")),
                        "ranking_score": _as_float(item.get("ranking_score")),
                        "note": _as_text(item.get("note")),
                    }
                )
                continue
            if any(grammar_key and grammar_key in normalized_blob for grammar_key in grammar_keys):
                matches.append(
                    {
                        "candidate_id": _as_text(item.get("candidate_id")),
                        "thesis_name": _as_text(item.get("thesis_name")),
                        "route": _as_text(item.get("route")),
                        "residual_class": _as_text(item.get("residual_class")),
                        "ranking_score": _as_float(item.get("ranking_score")),
                        "note": _as_text(item.get("note")),
                    }
                )
        return matches

    def _theme_cards(self) -> list[dict[str, Any]]:
        planning = self._planning_snapshot()
        planning_rows = planning.get("planning_rows", [])
        radar_items = (self._theme_radar_snapshot().get("items") or [])
        theme_state_lookup = self._theme_state_lookup()
        package_lookup = self._research_package_lookup()
        cards: list[dict[str, Any]] = []
        for spec_path in self._theme_spec_paths():
            raw = self._load_theme_spec(spec_path)
            theme_raw = raw.get("theme") or {}
            theme_slug = _slug_from_spec_path(spec_path)
            theme_state = dict(theme_state_lookup.get(theme_slug) or {})
            sentinels = [item for item in raw.get("sentinel", []) if isinstance(item, dict)]
            run_doc = _find_latest_run_report(theme_slug)
            run_summary = _parse_run_report_summary(run_doc)
            sections = _read_markdown_sections(run_doc) if run_doc else {}
            planning_matches = self._theme_matches_planning_rows({"theme_slug": theme_slug, "title": _as_text(theme_raw.get("title"))}, planning_rows)
            related_opportunities = self._theme_matches_opportunities({"theme_slug": theme_slug, "title": _as_text(theme_raw.get("title")), "sentinels": sentinels}, radar_items)
            related_opportunities = [
                {
                    **row,
                    "detail_href": f"/v2/dashboard/investor/opportunities/{_as_text(row.get('candidate_id'))}" if _as_text(row.get("candidate_id")) else "",
                    "research_package": dict(package_lookup.get(_as_text(row.get("candidate_id"))) or {}),
                }
                for row in related_opportunities
            ]
            related_sources: list[str] = []
            for row in planning_matches:
                for source_name in row["sources"]:
                    if source_name not in related_sources:
                        related_sources.append(source_name)
            cards.append(
                {
                    "theme_slug": theme_slug,
                    "title": _as_text(theme_raw.get("title")) or theme_slug,
                    "investor_question": _as_text(theme_raw.get("investor_question")),
                    "thesis_statement": _as_text(theme_raw.get("thesis_statement")),
                    "why_now": _as_text(theme_raw.get("why_now")),
                    "why_mispriced": _as_text(theme_raw.get("why_mispriced")),
                    "current_posture": _as_text(theme_raw.get("current_posture")),
                    "recommended_posture": _as_text(theme_state.get("recommended_posture") or run_summary.get("recommended_posture")),
                    "best_expression": _as_text(theme_state.get("best_expression") or run_summary.get("best_expression")),
                    "run_root": _as_text(theme_state.get("run_root") or run_summary.get("run_root")),
                    "summary_excerpt": _section_excerpt(sections, "投资视角", "Decision Card", max_lines=6)
                    or _section_excerpt(sections, "结果", "Summary", max_lines=6),
                    "spec_path": str(spec_path),
                    "spec_reader_href": _reader_href(spec_path),
                    "run_doc_path": str(run_doc) if run_doc else "",
                    "run_doc_reader_href": _reader_href(run_doc),
                    "planning_reader_href": _reader_href(FINAGENT_PLANNING_DOC),
                    "detail_href": _theme_detail_href(theme_slug),
                    "action_distance": _as_int(theme_state.get("action_distance")),
                    "latest_change": _as_text(((theme_state.get("history") or {}).get("summary_lines") or [""])[0]),
                    "sentinel_count": len(sentinels),
                    "core_count": sum(1 for item in sentinels if _as_text(item.get("bucket_role")) == "core"),
                    "option_count": sum(1 for item in sentinels if _as_text(item.get("bucket_role")) == "option"),
                    "alternative_count": sum(1 for item in sentinels if _as_text(item.get("bucket_role")) == "alternative"),
                    "competitor_count": sum(1 for item in sentinels if _as_text(item.get("entity_role")) == "competitor"),
                    "planning_matches": planning_matches,
                    "related_opportunities": related_opportunities,
                    "related_sources": related_sources,
                    "theme_state": theme_state,
                }
            )
        cards.sort(key=lambda item: (_parse_priority_rank(_as_text(item["planning_matches"][0]["priority"])) if item["planning_matches"] else 99, item["title"]))
        return cards

    def investor_snapshot(self) -> dict[str, Any]:
        control_plane = self._ensure_ready()
        planning = self._planning_snapshot()
        source_board = self._source_board_snapshot()
        themes = self._theme_cards()
        inbox = self._finbot_inbox_snapshot()
        opportunities = self._opportunity_cards(themes=themes, inbox_items=inbox)
        research_packages = self._research_package_lookup()
        source_score_lookup = self._source_score_lookup()
        source_items = [item for item in (source_board.get("items") or []) if isinstance(item, dict)]
        strong_sources: list[dict[str, Any]] = []
        kols: list[dict[str, Any]] = []
        for item in source_items:
            scorecard = dict(source_score_lookup.get(_as_text(item.get("source_id") or item.get("name"))) or {})
            card = {
                "source_id": _as_text(item.get("source_id")),
                "name": _as_text(item.get("name")),
                "source_type": _as_text(item.get("source_type")),
                "source_trust_tier": _as_text(item.get("source_trust_tier")),
                "track_record_label": _as_text(item.get("track_record_label")),
                "source_priority_label": _as_text(item.get("source_priority_label")),
                "latest_viewpoint_summary": _as_text(item.get("latest_viewpoint_summary")),
                "accepted_route_count": _as_int(item.get("accepted_route_count")),
                "validated_case_count": _as_int(item.get("validated_case_count")),
                "detail_href": _source_detail_href(_as_text(item.get("source_id"))),
                "quality_score": _as_float(scorecard.get("quality_score")),
                "quality_band": _as_text(scorecard.get("quality_band")),
                "trend_label": _as_text(scorecard.get("trend_label")),
                "packages_seen": _as_int(scorecard.get("packages_seen")),
                "supported_claim_count": _as_int(scorecard.get("supported_claim_count")),
            }
            if _as_text(item.get("primaryness")) == "first_hand" or _as_text(item.get("source_trust_tier")) in {"anchor", "reference"}:
                strong_sources.append(card)
            if _as_text(item.get("source_type")) == "kol":
                kols.append(card)
        strong_sources.sort(key=lambda item: (-item["accepted_route_count"], item["name"]))
        kols.sort(key=lambda item: (-item["accepted_route_count"], item["name"]))
        hero_metrics = [
            {"label": "Themes", "value": len(themes), "tone": "accent"},
            {"label": "Opportunities", "value": len(opportunities), "tone": "accent"},
            {"label": "Research Packages", "value": len(research_packages), "tone": "success"},
            {"label": "Strong Sources", "value": len(strong_sources[:8]), "tone": "success"},
            {"label": "KOL Watchlist", "value": len(kols[:8]), "tone": "warning"},
            {"label": "Finbot Inbox", "value": len(inbox), "tone": "accent" if inbox else "neutral"},
        ]
        research_updates: list[dict[str, Any]] = []
        for item in opportunities:
            package = dict(item.get("research_package") or {})
            if not package:
                continue
            history = dict(package.get("history") or {})
            research_updates.append(
                {
                    "kind": "opportunity",
                    "title": _as_text(item.get("thesis_name")),
                    "subtitle": _as_text(package.get("current_decision")) or _as_text(item.get("route")),
                    "detail_href": _as_text(item.get("detail_href")),
                    "reader_href": _as_text(package.get("reader_href")),
                    "summary": _as_text((history.get("summary_lines") or [""])[0]) or _as_text(package.get("thesis_change_summary")),
                    "generated_at": _as_float(package.get("generated_at")),
                }
            )
        for theme in themes:
            latest_change = _as_text(theme.get("latest_change"))
            if not latest_change:
                continue
            research_updates.append(
                {
                    "kind": "theme",
                    "title": _as_text(theme.get("title")),
                    "subtitle": _as_text(theme.get("recommended_posture")) or _as_text(theme.get("current_posture")),
                    "detail_href": _as_text(theme.get("detail_href")),
                    "reader_href": _as_text(theme.get("run_doc_reader_href")),
                    "summary": latest_change,
                    "generated_at": _as_float((theme.get("theme_state") or {}).get("generated_at")),
                }
            )
        research_updates.sort(key=lambda item: item.get("generated_at") or 0, reverse=True)
        return {
            "generated_at": time.time(),
            "control_plane": control_plane,
            "summary": {
                "theme_count": len(themes),
                "opportunity_count": len(opportunities),
                "research_package_count": len(research_packages),
                "strong_source_count": len(strong_sources),
                "kol_count": len(kols),
                "inbox_count": len(inbox),
            },
            "hero_metrics": hero_metrics,
            "themes": themes,
            "opportunities": opportunities,
            "strong_sources": strong_sources[:8],
            "kols": kols[:8],
            "planning_rows": planning.get("planning_rows", []),
            "research_updates": research_updates[:8],
            "planning_doc_path": str(FINAGENT_PLANNING_DOC),
            "planning_doc_reader_href": _reader_href(FINAGENT_PLANNING_DOC),
            "finbot_inbox": inbox,
        }

    def investor_theme_detail(self, theme_slug: str) -> dict[str, Any]:
        theme_slug = _as_text(theme_slug)
        control_plane = self._ensure_ready()
        theme = next((item for item in self._theme_cards() if _as_text(item.get("theme_slug")) == theme_slug), None)
        if theme is None:
            raise KeyError(theme_slug)
        spec_path = Path(theme["spec_path"])
        run_doc = Path(theme["run_doc_path"]) if _as_text(theme.get("run_doc_path")) else None
        raw = self._load_theme_spec(spec_path)
        theme_raw = raw.get("theme") or {}
        sentinels = [item for item in raw.get("sentinel", []) if isinstance(item, dict)]
        sections = _read_markdown_sections(run_doc) if run_doc and run_doc.exists() else {}
        investor_snapshot = self.investor_snapshot()
        source_lookup = {
            _as_text(item.get("name")): item
            for item in investor_snapshot.get("strong_sources", []) + investor_snapshot.get("kols", [])
            if _as_text(item.get("name"))
        }
        expressions = []
        for item in sentinels:
            notes = item.get("notes") or {}
            expressions.append(
                {
                    "sentinel_id": _as_text(item.get("sentinel_id")),
                    "entity": _as_text(item.get("entity")),
                    "product": _as_text(item.get("product")),
                    "bucket_role": _as_text(item.get("bucket_role") or item.get("entity_role") or "tracked"),
                    "entity_role": _as_text(item.get("entity_role")),
                    "current_stage": _as_text(item.get("current_stage")),
                    "expected_next_stage": _as_text(item.get("expected_next_stage")),
                    "expected_by": _as_text(item.get("expected_by")),
                    "current_confidence": _as_text(item.get("current_confidence")),
                    "evidence_text": _as_text(item.get("evidence_text")),
                    "source_role": _as_text(item.get("source_role")),
                    "current_action": _as_text(notes.get("current_action")),
                    "why_not_now": _as_text(notes.get("why_not_now")),
                    "upgrade_requirements": notes.get("upgrade_requirements") or [],
                    "anti_thesis_focus": item.get("anti_thesis_focus") or [],
                }
            )
        decision_card = {
            "current_posture": _as_text(theme_raw.get("current_posture")),
            "recommended_posture": _as_text(theme.get("recommended_posture")),
            "best_expression": _as_text(theme.get("best_expression")),
            "capital_gate": theme_raw.get("capital_gate") or [],
            "stop_rule": theme_raw.get("stop_rule") or [],
            "thesis_level_falsifiers": theme_raw.get("thesis_level_falsifiers") or [],
            "timing_level_falsifiers": theme_raw.get("timing_level_falsifiers") or [],
            "decision_excerpt": _section_excerpt(sections, "Decision Card", max_lines=10),
            "investor_excerpt": _section_excerpt(sections, "投资视角", max_lines=8),
        }
        related_sources = []
        for source_name in theme.get("related_sources", []) or []:
            row = dict(source_lookup.get(source_name) or {})
            if row:
                related_sources.append(row)
        theme_history = self._theme_state_history(theme_slug)
        return {
            "generated_at": time.time(),
            "control_plane": control_plane,
            "theme": theme,
            "detail": {
                "investor_question": _as_text(theme_raw.get("investor_question")),
                "thesis_statement": _as_text(theme_raw.get("thesis_statement")),
                "why_now": _as_text(theme_raw.get("why_now")),
                "why_mispriced": _as_text(theme_raw.get("why_mispriced")),
                "decision_card": decision_card,
                "expressions": expressions,
                "run_sections": {
                    "why_rerun": _section_excerpt(sections, "为什么要重跑", max_lines=8),
                    "results": _section_excerpt(sections, "输出结果", "结果", max_lines=8),
                    "judgment": _section_excerpt(sections, "投资视角", max_lines=10),
                },
                "theme_state": theme.get("theme_state") or {},
                "theme_evolution": dict((theme.get("theme_state") or {}).get("history") or {}),
                "theme_history": theme_history,
                "related_sources": related_sources,
                "spec_reader_href": _reader_href(spec_path),
                "run_doc_reader_href": _reader_href(run_doc),
                "planning_doc_reader_href": _reader_href(FINAGENT_PLANNING_DOC),
            },
        }

    def investor_opportunity_detail(self, candidate_id: str) -> dict[str, Any]:
        candidate_id = _as_text(candidate_id)
        control_plane = self._ensure_ready()
        snapshot = self.investor_snapshot()
        opportunity = next((item for item in snapshot["opportunities"] if _as_text(item.get("candidate_id")) == candidate_id), None)
        if opportunity is None:
            raise KeyError(candidate_id)
        related_source_names: list[str] = []
        for source_name in opportunity.get("suggested_sources", []) or []:
            source_name = _as_text(source_name)
            if source_name and source_name not in related_source_names:
                related_source_names.append(source_name)
        for theme in opportunity.get("related_themes", []) or []:
            theme_detail = next((item for item in snapshot["themes"] if _as_text(item.get("theme_slug")) == _as_text(theme.get("theme_slug"))), None)
            if theme_detail is None:
                continue
            for source_name in theme_detail.get("related_sources", []) or []:
                if source_name and source_name not in related_source_names:
                    related_source_names.append(source_name)
        related_sources: list[dict[str, Any]] = []
        package = dict(opportunity.get("research_package") or {})
        for item in snapshot["strong_sources"] + snapshot["kols"]:
            if _as_text(item.get("name")) in related_source_names:
                related_sources.append(item)
        citation_lookup = {
            _as_text(row.get("citation_id")): row
            for row in package.get("citation_objects") or []
            if _as_text(row.get("citation_id"))
        }
        edges_by_claim: dict[str, list[dict[str, Any]]] = {}
        for edge in package.get("claim_citation_edges") or []:
            if not isinstance(edge, dict):
                continue
            claim_id = _as_text(edge.get("claim_id"))
            citation_id = _as_text(edge.get("citation_id"))
            if not claim_id or not citation_id:
                continue
            citation = citation_lookup.get(citation_id)
            if citation is None:
                continue
            edges_by_claim.setdefault(claim_id, []).append({**edge, "citation": citation})
        citation_register = sorted(
            [
                {
                    **row,
                    "information_role": _as_text(row.get("information_role"))
                    or _information_role_from_fields(
                        contribution_role=row.get("contribution_role"),
                        source_trust_tier=row.get("source_trust_tier"),
                        source_type=row.get("source_type"),
                    ),
                }
                for row in citation_lookup.values()
            ],
            key=lambda row: (-_as_float(row.get("quality_score")), _as_text(row.get("source_name"))),
        )
        opportunity_history = self._opportunity_history(candidate_id)
        decision_card = {
            "current_decision": _as_text(package.get("current_decision")),
            "thesis_status": _as_text(package.get("thesis_status")),
            "best_expression_today": _as_text(package.get("best_expression_today")),
            "why_not_investable_yet": _as_text(package.get("why_not_investable_yet")),
            "next_proving_milestone": _as_text(package.get("next_proving_milestone")),
            "distance_to_action": _as_text(package.get("distance_to_action") or (package.get("history") or {}).get("action_distance_after")),
            "expression_tradability": _expression_tradability_label(package.get("distance_to_action") or (package.get("history") or {}).get("action_distance_after")),
            "blocking_facts": list(package.get("blocking_facts") or []),
            "thesis_change_summary": _as_text(package.get("thesis_change_summary")),
        }
        package["claim_support_map"] = edges_by_claim
        package["citation_register"] = citation_register
        package["opportunity_history"] = opportunity_history
        package["decision_card"] = decision_card
        return {
            "generated_at": time.time(),
            "control_plane": control_plane,
            "opportunity": opportunity,
            "research_package": package,
            "related_sources": related_sources[:8],
            "planning_doc_reader_href": snapshot["planning_doc_reader_href"],
        }

    def investor_source_detail(self, source_id: str) -> dict[str, Any]:
        source_id = _as_text(source_id)
        control_plane = self._ensure_ready()
        planning_rows = self._planning_snapshot().get("planning_rows", [])
        source_items = [item for item in (self._source_board_snapshot().get("items") or []) if isinstance(item, dict)]
        source_score_lookup = self._source_score_lookup()
        target = next((item for item in source_items if _as_text(item.get("source_id")) == source_id), None)
        if target is None:
            raise KeyError(source_id)
        name = _as_text(target.get("name"))
        scorecard = dict(source_score_lookup.get(source_id) or source_score_lookup.get(name) or {})
        score_history = self._source_score_history(source_id, name)
        match_tokens = _source_match_tokens(name)
        related_rows = []
        for row in planning_rows:
            normalized_source_cell = _normalize_key(_as_text(row.get("KOL / 源")))
            if any(token and token in normalized_source_cell for token in match_tokens):
                related_rows.append(
                    {
                        "theme": _as_text(row.get("主题")),
                        "logic": _as_text(row.get("核心逻辑")),
                        "expressions": _parse_expression_column(_as_text(row.get("标的 / 表达"))),
                        "priority": _as_text(row.get("优先级")),
                        "why": _as_text(row.get("为什么选")),
                    }
                )

        from chatgptrest.finbot_modules.source_scoring import source_keep_or_downgrade
        elo_rating = scorecard.get("elo_rating")
        keep_downgrade = source_keep_or_downgrade(
            scorecard,
            _as_float(elo_rating) if elo_rating is not None else None
        )

        return {
            "generated_at": time.time(),
            "control_plane": control_plane,
            "source": {
                "source_id": source_id,
                "name": name,
                "source_type": _as_text(target.get("source_type")),
                "source_trust_tier": _as_text(target.get("source_trust_tier")),
                "source_priority_label": _as_text(target.get("source_priority_label")),
                "track_record_label": _as_text(target.get("track_record_label")),
                "primaryness": _as_text(target.get("primaryness")),
                "accepted_route_count": _as_int(target.get("accepted_route_count")),
                "validated_case_count": _as_int(target.get("validated_case_count")),
                "claim_count": _as_int(target.get("claim_count")),
                "latest_viewpoint_summary": _as_text(target.get("latest_viewpoint_summary")),
                "effective_operator_feedback_score": _as_float(target.get("effective_operator_feedback_score")),
                "related_rows": related_rows,
                "quality_score": _as_float(scorecard.get("quality_score")),
                "quality_band": _as_text(scorecard.get("quality_band")),
                "trend_label": _as_text(scorecard.get("trend_label")),
                "packages_seen": _as_int(scorecard.get("packages_seen")),
                "supported_claim_count": _as_int(scorecard.get("supported_claim_count")),
                "anchor_claim_count": _as_int(scorecard.get("anchor_claim_count")),
                "load_bearing_claim_count": _as_int(scorecard.get("load_bearing_claim_count")),
                "lead_support_count": _as_int(scorecard.get("lead_support_count")),
                "contradicted_claim_count": _as_int(scorecard.get("contradicted_claim_count")),
                "information_role": _as_text(scorecard.get("information_role"))
                or _information_role_from_fields(
                    contribution_role=scorecard.get("contribution_role"),
                    source_trust_tier=target.get("source_trust_tier"),
                    source_type=target.get("source_type"),
                    primaryness=target.get("primaryness"),
                ),
                "quality_explanation": _as_text(scorecard.get("quality_explanation")),
                "theme_slugs": list(scorecard.get("theme_slugs") or []),
                "support_history": list(scorecard.get("support_history") or []),
                "score_history": score_history,
                "keep_downgrade": keep_downgrade,
            },
            "links": {
                "planning_doc_reader_href": _reader_href(FINAGENT_PLANNING_DOC),
            },
        }

    def investor_graph_snapshot(self) -> dict[str, Any]:
        snapshot = self.investor_snapshot()
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        seen_nodes: set[str] = set()
        seen_edges: set[str] = set()

        def append_node(node_id: str, *, label: str, subtitle: str, tone: str, href: str = "") -> None:
            if not node_id or node_id in seen_nodes:
                return
            seen_nodes.add(node_id)
            nodes.append({"data": {"id": node_id, "label": label, "subtitle": subtitle, "tone": tone, "href": href}})

        def append_edge(source: str, target: str, *, label: str) -> None:
            edge_id = f"{source}->{target}:{label}"
            if not source or not target or edge_id in seen_edges:
                return
            seen_edges.add(edge_id)
            edges.append({"data": {"id": edge_id, "source": source, "target": target, "label": label}})

        for theme in snapshot["themes"]:
            theme_node = f"theme:{theme['theme_slug']}"
            append_node(theme_node, label=theme["title"], subtitle=theme["recommended_posture"] or theme["current_posture"], tone="accent", href=theme["detail_href"])
            if _as_text(theme.get("best_expression")):
                expression_node = f"expression:{_safe_name_to_slug(_as_text(theme.get('best_expression')))}"
                append_node(expression_node, label=_as_text(theme.get("best_expression")), subtitle="best expression", tone="success")
                append_edge(expression_node, theme_node, label="best_expression")
            for source_name in theme.get("related_sources", [])[:6]:
                source_node = f"source:{_safe_name_to_slug(source_name)}"
                source_row = next((item for item in snapshot["strong_sources"] + snapshot["kols"] if _as_text(item.get("name")) == source_name), {})
                append_node(source_node, label=source_name, subtitle="source / KOL", tone="neutral", href=_as_text(source_row.get("detail_href")))
                append_edge(source_node, theme_node, label="supports")
            for opportunity in theme.get("related_opportunities", [])[:3]:
                opp_node = f"opp:{opportunity['candidate_id']}"
                append_node(opp_node, label=opportunity["candidate_id"], subtitle=opportunity["residual_class"], tone="warning", href=opportunity.get("detail_href") or "/v2/dashboard/investor")
                append_edge(opp_node, theme_node, label=opportunity["route"] or "candidate")
                if _as_text((opportunity.get("research_package") or {}).get("best_expression_today")):
                    expression_node = f"expression:{_safe_name_to_slug(_as_text((opportunity.get('research_package') or {}).get('best_expression_today')))}"
                    append_node(expression_node, label=_as_text((opportunity.get("research_package") or {}).get("best_expression_today")), subtitle="opportunity leader", tone="success")
                    append_edge(opp_node, expression_node, label="best_expression_today")
        return {
            "generated_at": time.time(),
            "control_plane": snapshot["control_plane"],
            "summary": {"nodes": len(nodes), "edges": len(edges), "themes": len(snapshot["themes"])},
            "graph": {"nodes": nodes, "edges": edges},
        }

    def read_dashboard_document(self, path: str) -> dict[str, Any]:
        control_plane = self._ensure_ready()
        raw_path = Path(path).expanduser().resolve()
        allowed = any(raw_path.is_relative_to(candidate.resolve()) for candidate in _allowed_reader_paths() if candidate.exists())
        if not allowed:
            raise PermissionError(str(raw_path))
        text = raw_path.read_text(encoding="utf-8", errors="replace")
        return {
            "generated_at": time.time(),
            "control_plane": control_plane,
            "path": str(raw_path),
            "reader_title": raw_path.name,
            "content": text,
        }
    # Compatibility aliases for earlier dashboard URLs / callers.
    def tasks_snapshot(
        self,
        *,
        status: str = "",
        kind: str = "",
        search: str = "",
        limit: int = 100,
        attention_only: bool = False,
    ) -> dict[str, Any]:
        del kind
        runs = self.runs_snapshot(
            q=search,
            status=status,
            running_only=attention_only,
            limit=limit,
            task_only=True,
        )
        return {
            "generated_at": runs["generated_at"],
            "control_plane": runs["control_plane"],
            "filters": runs["filters"],
            "summary": runs["summary"],
            "tasks": runs["runs"],
        }

    def task_detail(self, task_id: str) -> dict[str, Any]:
        task_id = _as_text(task_id)
        self._ensure_ready()
        with self._connect() as conn:
            row = conn.execute("SELECT root_run_id FROM run_index WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        return self.run_detail(_as_text(row["root_run_id"]))

    def openmind_snapshot(self) -> dict[str, Any]:
        return self.cognitive_snapshot()

    def openclaw_snapshot(self) -> dict[str, Any]:
        return self.runtime_snapshot()

    def lineage_snapshot(self, *, limit: int = 50) -> dict[str, Any]:
        return self.identity_snapshot(limit=limit)
