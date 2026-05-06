#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from chatgptrest.core.openmind_paths import (
    resolve_evomap_knowledge_runtime_db_path,
    resolve_openmind_event_bus_db_path,
)
from chatgptrest.evomap.knowledge.planning_runtime_pack_search import (
    resolve_ready_planning_runtime_pack_bundle,
    search_planning_runtime_pack,
)
from chatgptrest.evomap.knowledge.retrieval import RetrievalConfig
from chatgptrest.telemetry_contract import extract_identity_fields


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTROLLER_LANE_DB_PATH = REPO_ROOT / "state" / "controller_lanes.sqlite3"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "runtime_guard"

WORKFLOW_START_EVENT_TYPES = {"team.run.created"}
WORKFLOW_TERMINAL_EVENT_TYPES = {
    "team.run.completed",
    "team.run.failed",
    "workflow.completed",
    "workflow.failed",
}
TOOL_EVENT_TYPES = {"tool.completed", "tool.failed"}
EXECUTION_EVENT_TYPES = WORKFLOW_START_EVENT_TYPES | WORKFLOW_TERMINAL_EVENT_TYPES | TOOL_EVENT_TYPES
SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
DEFAULT_REQUIRED_IDENTITY_FIELDS = ("trace_id", "task_ref", "role_id", "executor_kind")
DEFAULT_PLANNING_PROBE_QUERIES = ("合同 商务 底线",)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timestamp_dir_name(now: float | None = None) -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now or time.time()))


def _json_dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _safe_text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _parse_iso_timestamp(raw: str) -> float:
    text = str(raw or "").strip()
    if not text:
        return 0.0
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return 0.0


def _normalize_hits_count(body: dict[str, Any]) -> int:
    sources = body.get("sources") if isinstance(body.get("sources"), dict) else {}
    source_hits = int(sources.get("planning_review_pack") or 0)
    if source_hits > 0:
        return source_hits
    hits = body.get("hits")
    if not isinstance(hits, list):
        return 0
    return sum(1 for hit in hits if str(hit.get("source") or "") == "planning_review_pack")


def _request_json(
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    bearer_token: str = "",
    timeout_seconds: float = 20.0,
) -> tuple[int, dict[str, Any]]:
    headers = {"Content-Type": "application/json"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=float(timeout_seconds)) as response:
            body = json.loads(response.read().decode("utf-8"))
            return int(response.status), body
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            body = {"error": str(exc)}
        return int(exc.code), body
    except urllib.error.URLError as exc:
        return 0, {"error": str(exc)}


@dataclass(frozen=True)
class GuardConfig:
    event_bus_db_path: Path
    controller_lane_db_path: Path
    evomap_db_path: Path
    output_root: Path
    lookback_seconds: float = 1800.0
    heartbeat_stale_seconds: float = 900.0
    workflow_sla_seconds: float = 1800.0
    tool_failure_ratio_threshold: float = 0.5
    tool_failure_min_samples: int = 3
    required_identity_fields: tuple[str, ...] = DEFAULT_REQUIRED_IDENTITY_FIELDS
    planning_probe_queries: tuple[str, ...] = DEFAULT_PLANNING_PROBE_QUERIES
    planning_probe_top_k: int = 5
    planning_probe_timeout_seconds: float = 20.0
    planning_bundle_dir: str = ""
    planning_bundle_root: str = ""
    base_url: str = ""
    bearer_token: str = ""
    evomap_min_runtime_visible_atoms: int = 1
    evomap_min_runtime_sources: int = 1


@dataclass(frozen=True)
class DetectorHit:
    detector_id: str
    severity: str
    summary: str
    entity: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detector_id": self.detector_id,
            "severity": self.severity,
            "summary": self.summary,
            "entity": self.entity,
            "evidence": self.evidence,
        }


def _connect_row_db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    return connection


def load_trace_events(db_path: Path, *, lookback_seconds: float, now: float) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    since_iso = datetime.fromtimestamp(now - float(max(0.0, lookback_seconds)), tz=timezone.utc).isoformat()
    connection = _connect_row_db(db_path)
    try:
        rows = connection.execute(
            """
            SELECT event_id, source, event_type, trace_id, timestamp, data, session_id, parent_event_id, security_label
            FROM trace_events
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (since_iso,),
        ).fetchall()
    finally:
        connection.close()

    events: list[dict[str, Any]] = []
    for row in rows:
        raw_data = row["data"]
        parse_error = ""
        payload: dict[str, Any] = {}
        try:
            loaded = json.loads(raw_data or "{}")
            if isinstance(loaded, dict):
                payload = loaded
            else:
                parse_error = "payload_not_object"
        except Exception as exc:
            parse_error = str(exc)
        events.append(
            {
                "event_id": str(row["event_id"] or ""),
                "source": str(row["source"] or ""),
                "event_type": str(row["event_type"] or ""),
                "trace_id": str(row["trace_id"] or ""),
                "timestamp": str(row["timestamp"] or ""),
                "ts_epoch": _parse_iso_timestamp(str(row["timestamp"] or "")),
                "data": payload,
                "data_parse_error": parse_error,
                "session_id": str(row["session_id"] or ""),
                "parent_event_id": str(row["parent_event_id"] or ""),
                "security_label": str(row["security_label"] or ""),
            }
        )
    return events


def load_controller_lanes(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    connection = _connect_row_db(db_path)
    try:
        rows = connection.execute(
            """
            SELECT lane_id, purpose, lane_kind, desired_state, run_state, session_key,
                   stale_after_seconds, heartbeat_at, pid, last_summary, last_error,
                   last_launch_at, created_at, updated_at
            FROM lanes
            ORDER BY updated_at DESC
            """
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def _tracking_key(event: dict[str, Any]) -> str:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    trace_id = _safe_text(event.get("trace_id"))
    task_ref = _safe_text(data.get("task_ref") or data.get("task_id"))
    lane_id = _safe_text(data.get("lane_id"))
    session_id = _safe_text(event.get("session_id") or data.get("session_id"))
    if trace_id:
        return f"trace:{trace_id}"
    if task_ref:
        return f"task:{task_ref}|lane:{lane_id}|session:{session_id}"
    if lane_id:
        return f"lane:{lane_id}|session:{session_id}"
    if session_id:
        return f"session:{session_id}"
    return f"event:{_safe_text(event.get('event_id'))}"


def detect_missing_heartbeat(
    *,
    events: list[dict[str, Any]],
    lanes: list[dict[str, Any]],
    config: GuardConfig,
    now: float,
) -> list[DetectorHit]:
    hits: list[DetectorHit] = []
    for lane in lanes:
        lane_id = _safe_text(lane.get("lane_id"))
        desired_state = _safe_text(lane.get("desired_state"))
        run_state = _safe_text(lane.get("run_state"))
        if desired_state in {"disabled", "retired"} or run_state in {"completed", "failed", "paused"}:
            continue
        heartbeat_at = float(lane.get("heartbeat_at") or 0.0)
        stale_after = float(lane.get("stale_after_seconds") or 0.0) or float(config.heartbeat_stale_seconds)
        if heartbeat_at > 0 and (now - heartbeat_at) <= stale_after:
            continue
        age_seconds = round(max(0.0, now - heartbeat_at), 1) if heartbeat_at > 0 else None
        hits.append(
            DetectorHit(
                detector_id="missing_heartbeat",
                severity="P1",
                summary=f"lane {lane_id or '<unknown>'} has no fresh heartbeat",
                entity=lane_id or "<unknown-lane>",
                evidence={
                    "lane_id": lane_id,
                    "desired_state": desired_state,
                    "run_state": run_state,
                    "heartbeat_at": heartbeat_at or None,
                    "heartbeat_age_seconds": age_seconds,
                    "stale_after_seconds": stale_after,
                    "last_summary": _safe_text(lane.get("last_summary")),
                    "last_error": _safe_text(lane.get("last_error")),
                },
            )
        )

    if hits or not events:
        return hits

    latest_event = max(events, key=lambda item: float(item.get("ts_epoch") or 0.0))
    latest_age = max(0.0, now - float(latest_event.get("ts_epoch") or 0.0))
    if latest_age > float(config.heartbeat_stale_seconds):
        hits.append(
            DetectorHit(
                detector_id="missing_heartbeat",
                severity="P2",
                summary="event stream heartbeat is stale",
                entity=_safe_text(latest_event.get("source")) or "<event-stream>",
                evidence={
                    "latest_event_id": _safe_text(latest_event.get("event_id")),
                    "latest_source": _safe_text(latest_event.get("source")),
                    "latest_event_type": _safe_text(latest_event.get("event_type")),
                    "latest_timestamp": _safe_text(latest_event.get("timestamp")),
                    "heartbeat_age_seconds": round(latest_age, 1),
                    "stale_after_seconds": float(config.heartbeat_stale_seconds),
                },
            )
        )
    return hits


def detect_started_without_terminal(
    *,
    events: list[dict[str, Any]],
    config: GuardConfig,
    now: float,
) -> list[DetectorHit]:
    terminals: set[str] = set()
    starts: list[dict[str, Any]] = []
    for event in events:
        event_type = _safe_text(event.get("event_type"))
        if event_type in WORKFLOW_TERMINAL_EVENT_TYPES:
            terminals.add(_tracking_key(event))
        elif event_type in WORKFLOW_START_EVENT_TYPES:
            starts.append(event)

    hits: list[DetectorHit] = []
    for start in starts:
        tracking_key = _tracking_key(start)
        if tracking_key in terminals:
            continue
        age_seconds = max(0.0, now - float(start.get("ts_epoch") or 0.0))
        if age_seconds <= float(config.workflow_sla_seconds):
            continue
        data = start.get("data") if isinstance(start.get("data"), dict) else {}
        hits.append(
            DetectorHit(
                detector_id="started_without_terminal",
                severity="P1",
                summary=f"workflow {tracking_key} started but has no terminal event after SLA",
                entity=tracking_key,
                evidence={
                    "tracking_key": tracking_key,
                    "age_seconds": round(age_seconds, 1),
                    "workflow_sla_seconds": float(config.workflow_sla_seconds),
                    "event_id": _safe_text(start.get("event_id")),
                    "timestamp": _safe_text(start.get("timestamp")),
                    "source": _safe_text(start.get("source")),
                    "task_ref": _safe_text(data.get("task_ref") or data.get("task_id")),
                    "lane_id": _safe_text(data.get("lane_id")),
                    "session_id": _safe_text(start.get("session_id")),
                },
            )
        )
    return hits


def detect_tool_failure_spike(*, events: list[dict[str, Any]], config: GuardConfig) -> list[DetectorHit]:
    stats: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        event_type = _safe_text(event.get("event_type"))
        if event_type not in TOOL_EVENT_TYPES:
            continue
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        tool_name = _safe_text(data.get("tool") or data.get("tool_name") or data.get("tool_id")) or "<unknown-tool>"
        key = (_safe_text(event.get("source")) or "<unknown-source>", tool_name)
        bucket = stats.setdefault(
            key,
            {
                "total": 0,
                "failed": 0,
                "latest_event_id": "",
                "latest_timestamp": "",
                "sample_event_ids": [],
            },
        )
        bucket["total"] += 1
        if event_type == "tool.failed":
            bucket["failed"] += 1
        bucket["latest_event_id"] = _safe_text(event.get("event_id"))
        bucket["latest_timestamp"] = _safe_text(event.get("timestamp"))
        if len(bucket["sample_event_ids"]) < 5:
            bucket["sample_event_ids"].append(_safe_text(event.get("event_id")))

    hits: list[DetectorHit] = []
    for (source, tool_name), bucket in sorted(stats.items()):
        total = int(bucket["total"])
        failed = int(bucket["failed"])
        if total < int(config.tool_failure_min_samples) or failed <= 0:
            continue
        failure_ratio = failed / max(total, 1)
        if failure_ratio < float(config.tool_failure_ratio_threshold):
            continue
        severity = "P1" if failed == total else "P2"
        hits.append(
            DetectorHit(
                detector_id="tool_failure_spike",
                severity=severity,
                summary=f"tool {tool_name} failure ratio is {failure_ratio:.2f} over {total} samples",
                entity=f"{source}:{tool_name}",
                evidence={
                    "source": source,
                    "tool_name": tool_name,
                    "total": total,
                    "failed": failed,
                    "failure_ratio": round(failure_ratio, 4),
                    "threshold_ratio": float(config.tool_failure_ratio_threshold),
                    "min_samples": int(config.tool_failure_min_samples),
                    "latest_event_id": bucket["latest_event_id"],
                    "latest_timestamp": bucket["latest_timestamp"],
                    "sample_event_ids": bucket["sample_event_ids"],
                },
            )
        )
    return hits


def detect_telemetry_contract_violations(
    *,
    events: list[dict[str, Any]],
    config: GuardConfig,
) -> list[DetectorHit]:
    violations: list[dict[str, Any]] = []
    for event in events:
        if _safe_text(event.get("event_type")) not in EXECUTION_EVENT_TYPES:
            continue
        if _safe_text(event.get("data_parse_error")):
            violations.append(
                {
                    "event_id": _safe_text(event.get("event_id")),
                    "event_type": _safe_text(event.get("event_type")),
                    "source": _safe_text(event.get("source")),
                    "reason": "payload_parse_error",
                    "detail": _safe_text(event.get("data_parse_error")),
                }
            )
            continue
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        identity = extract_identity_fields(
            data,
            event_type=_safe_text(event.get("event_type")),
            trace_id=_safe_text(event.get("trace_id")),
            session_id=_safe_text(event.get("session_id")),
            source=_safe_text(event.get("source")),
        )
        missing_fields = [field_name for field_name in config.required_identity_fields if not _safe_text(identity.get(field_name))]
        if missing_fields:
            violations.append(
                {
                    "event_id": _safe_text(event.get("event_id")),
                    "event_type": _safe_text(event.get("event_type")),
                    "source": _safe_text(event.get("source")),
                    "missing_fields": missing_fields,
                    "trace_id": _safe_text(event.get("trace_id")),
                    "task_ref": _safe_text(data.get("task_ref") or data.get("task_id")),
                    "lane_id": _safe_text(data.get("lane_id")),
                    "session_id": _safe_text(event.get("session_id")),
                }
            )

    if not violations:
        return []
    return [
        DetectorHit(
            detector_id="telemetry_contract_violation",
            severity="P1",
            summary=f"{len(violations)} execution events violate the telemetry identity contract",
            entity="execution.telemetry",
            evidence={
                "required_fields": list(config.required_identity_fields),
                "violation_count": len(violations),
                "examples": violations[:10],
            },
        )
    ]


def _resolve_planning_bundle(config: GuardConfig) -> tuple[bool, Path | None]:
    activated = bool(
        config.planning_bundle_dir
        or config.planning_bundle_root
        or os.environ.get("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR", "").strip()
        or os.environ.get("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_ROOT", "").strip()
    )
    if not activated:
        return False, None
    if config.planning_bundle_dir:
        return True, resolve_ready_planning_runtime_pack_bundle(config.planning_bundle_dir)
    if config.planning_bundle_root:
        original_root = os.environ.get("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_ROOT", "")
        os.environ["CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_ROOT"] = config.planning_bundle_root
        try:
            return True, resolve_ready_planning_runtime_pack_bundle("")
        finally:
            if original_root:
                os.environ["CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_ROOT"] = original_root
            else:
                os.environ.pop("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_ROOT", None)
    return True, resolve_ready_planning_runtime_pack_bundle("")


def probe_planning_runtime_pack(config: GuardConfig) -> dict[str, Any]:
    activated, bundle_path = _resolve_planning_bundle(config)
    if not activated:
        return {
            "activated": False,
            "bundle_path": None,
            "probe_mode": "disabled",
            "queries": [],
            "total_hits": 0,
            "ok": True,
        }

    if bundle_path is None:
        return {
            "activated": True,
            "bundle_path": None,
            "probe_mode": "bundle_missing",
            "queries": [],
            "total_hits": 0,
            "ok": False,
        }

    queries: list[dict[str, Any]] = []
    total_hits = 0
    probe_mode = "direct_search"
    for query in config.planning_probe_queries:
        if config.base_url:
            probe_mode = "advisor_recall"
            status, body = _request_json(
                method="POST",
                url=f"{config.base_url.rstrip('/')}/v1/advisor/recall",
                payload={
                    "query": query,
                    "top_k": int(config.planning_probe_top_k),
                    "source_scope": ["planning_review"],
                },
                bearer_token=config.bearer_token,
                timeout_seconds=float(config.planning_probe_timeout_seconds),
            )
            planning_hits = _normalize_hits_count(body)
            total_hits += planning_hits
            queries.append(
                {
                    "query": query,
                    "mode": probe_mode,
                    "http_status": status,
                    "planning_hit_count": planning_hits,
                    "source_scope": list(body.get("source_scope") or []) if isinstance(body, dict) else [],
                    "ok": bool(status == 200 and planning_hits > 0),
                }
            )
            continue

        try:
            hits = search_planning_runtime_pack(
                query,
                top_k=int(config.planning_probe_top_k),
                bundle_dir=str(bundle_path),
                db_path=str(config.evomap_db_path),
            )
        except Exception as exc:
            hits = []
            queries.append(
                {
                    "query": query,
                    "mode": probe_mode,
                    "planning_hit_count": 0,
                    "ok": False,
                    "error": str(exc),
                }
            )
            continue
        planning_hits = len(hits)
        total_hits += planning_hits
        queries.append(
            {
                "query": query,
                "mode": probe_mode,
                "planning_hit_count": planning_hits,
                "top_artifact_id": _safe_text(hits[0].get("artifact_id")) if hits else "",
                "ok": planning_hits > 0,
            }
        )

    return {
        "activated": True,
        "bundle_path": str(bundle_path),
        "probe_mode": probe_mode,
        "queries": queries,
        "total_hits": total_hits,
        "ok": total_hits > 0,
    }


def detect_planning_opt_in_zero_hit(*, config: GuardConfig) -> tuple[list[DetectorHit], dict[str, Any]]:
    probe = probe_planning_runtime_pack(config)
    if not probe["activated"]:
        return [], probe
    if probe["ok"]:
        return [], probe
    summary = "planning runtime pack is activated but explicit planning probe returned zero hits"
    if probe["probe_mode"] == "bundle_missing":
        summary = "planning runtime pack activation is set but no ready bundle can be resolved"
    return [
        DetectorHit(
            detector_id="planning_opt_in_zero_hit",
            severity="P1",
            summary=summary,
            entity="planning_review_pack",
            evidence=probe,
        )
    ], probe


def collect_evomap_runtime_visibility(config: GuardConfig) -> dict[str, Any]:
    if not config.evomap_db_path.exists():
        return {
            "db_available": False,
            "visible_atom_count": 0,
            "visible_source_count": 0,
            "sources": {},
            "filters": {},
        }

    retrieval_cfg = RetrievalConfig()
    connection = _connect_row_db(config.evomap_db_path)
    placeholders = ",".join("?" for _ in retrieval_cfg.allowed_promotion_status)
    excluded_placeholders = ",".join("?" for _ in retrieval_cfg.exclude_stability)
    filters = [
        f"a.promotion_status IN ({placeholders})",
        f"a.stability NOT IN ({excluded_placeholders})",
        "a.quality_auto >= ?",
        "(a.groundedness IS NULL OR a.groundedness >= 0.5)",
    ]
    params: list[Any] = list(retrieval_cfg.allowed_promotion_status) + list(retrieval_cfg.exclude_stability) + [float(retrieval_cfg.min_quality)]
    query = f"""
        SELECT d.source AS source_name, COUNT(*) AS atom_count
        FROM atoms a
        JOIN episodes e ON e.episode_id = a.episode_id
        JOIN documents d ON d.doc_id = e.doc_id
        WHERE {' AND '.join(filters)}
        GROUP BY d.source
        ORDER BY atom_count DESC, source_name ASC
    """
    try:
        rows = connection.execute(query, params).fetchall()
    except sqlite3.Error as exc:
        connection.close()
        return {
            "db_available": False,
            "visible_atom_count": 0,
            "visible_source_count": 0,
            "sources": {},
            "filters": {},
            "error": str(exc),
        }
    finally:
        if connection:
            try:
                connection.close()
            except Exception:
                pass
    sources = {str(row["source_name"] or ""): int(row["atom_count"] or 0) for row in rows}
    return {
        "db_available": True,
        "visible_atom_count": sum(sources.values()),
        "visible_source_count": len([name for name, count in sources.items() if name and count > 0]),
        "sources": sources,
        "filters": {
            "allowed_promotion_status": list(retrieval_cfg.allowed_promotion_status),
            "exclude_stability": list(retrieval_cfg.exclude_stability),
            "min_quality": float(retrieval_cfg.min_quality),
            "min_groundedness": 0.5,
        },
    }


def detect_evomap_runtime_visibility_regression(*, config: GuardConfig) -> tuple[list[DetectorHit], dict[str, Any]]:
    visibility = collect_evomap_runtime_visibility(config)
    if not visibility["db_available"]:
        return [
            DetectorHit(
                detector_id="evomap_runtime_visibility_regression",
                severity="P1",
                summary="EvoMap runtime visibility check cannot open the knowledge DB",
                entity="evomap.runtime",
                evidence={"db_path": str(config.evomap_db_path)},
            )
        ], visibility

    hits: list[DetectorHit] = []
    visible_atoms = int(visibility["visible_atom_count"] or 0)
    visible_sources = int(visibility["visible_source_count"] or 0)
    if visible_atoms < int(config.evomap_min_runtime_visible_atoms) or visible_sources < int(config.evomap_min_runtime_sources):
        hits.append(
            DetectorHit(
                detector_id="evomap_runtime_visibility_regression",
                severity="P1",
                summary="EvoMap runtime-visible atom/source count fell below the configured floor",
                entity="evomap.runtime",
                evidence={
                    **visibility,
                    "min_runtime_visible_atoms": int(config.evomap_min_runtime_visible_atoms),
                    "min_runtime_sources": int(config.evomap_min_runtime_sources),
                },
            )
        )
    return hits, visibility


def _highest_severity(hits: Iterable[DetectorHit]) -> str | None:
    severities = [hit.severity for hit in hits]
    if not severities:
        return None
    return min(severities, key=lambda value: SEVERITY_ORDER.get(value, 99))


def _build_state_summary(
    *,
    config: GuardConfig,
    now: float,
    events: list[dict[str, Any]],
    lanes: list[dict[str, Any]],
    planning_probe: dict[str, Any],
    evomap_visibility: dict[str, Any],
) -> dict[str, Any]:
    execution_event_count = sum(1 for event in events if _safe_text(event.get("event_type")) in EXECUTION_EVENT_TYPES)
    latest_event_ts = max((float(event.get("ts_epoch") or 0.0) for event in events), default=0.0)
    latest_lane_heartbeat = max((float(lane.get("heartbeat_at") or 0.0) for lane in lanes), default=0.0)
    return {
        "generated_at": _utc_now_iso(),
        "window_seconds": float(config.lookback_seconds),
        "paths": {
            "event_bus_db_path": str(config.event_bus_db_path),
            "controller_lane_db_path": str(config.controller_lane_db_path),
            "evomap_db_path": str(config.evomap_db_path),
        },
        "counts": {
            "trace_events": len(events),
            "execution_events": execution_event_count,
            "lanes": len(lanes),
            "runtime_visible_atoms": int(evomap_visibility.get("visible_atom_count") or 0),
            "runtime_visible_sources": int(evomap_visibility.get("visible_source_count") or 0),
            "planning_probe_total_hits": int(planning_probe.get("total_hits") or 0),
        },
        "freshness": {
            "latest_event_timestamp": datetime.fromtimestamp(latest_event_ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            if latest_event_ts
            else "",
            "latest_event_age_seconds": round(max(0.0, now - latest_event_ts), 1) if latest_event_ts else None,
            "latest_lane_heartbeat_age_seconds": round(max(0.0, now - latest_lane_heartbeat), 1) if latest_lane_heartbeat else None,
        },
        "planning_probe": planning_probe,
        "evomap_visibility": evomap_visibility,
    }


def _build_incident_summary(hits: list[DetectorHit]) -> dict[str, Any]:
    by_detector: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for hit in hits:
        by_detector[hit.detector_id] = by_detector.get(hit.detector_id, 0) + 1
        by_severity[hit.severity] = by_severity.get(hit.severity, 0) + 1
    return {
        "ok": not hits,
        "highest_severity": _highest_severity(hits),
        "attention_required": bool(hits),
        "hit_count": len(hits),
        "by_detector": by_detector,
        "by_severity": by_severity,
    }


def render_digest(*, state_summary: dict[str, Any], incident_summary: dict[str, Any], hits: list[DetectorHit]) -> str:
    counts = state_summary.get("counts") if isinstance(state_summary.get("counts"), dict) else {}
    freshness = state_summary.get("freshness") if isinstance(state_summary.get("freshness"), dict) else {}
    lines = [
        "# OpenClaw Runtime Guard",
        "",
        f"- generated_at: `{state_summary.get('generated_at', '')}`",
        f"- ok: `{incident_summary.get('ok', False)}`",
        f"- highest_severity: `{incident_summary.get('highest_severity') or 'none'}`",
        f"- trace_events: `{counts.get('trace_events', 0)}`",
        f"- execution_events: `{counts.get('execution_events', 0)}`",
        f"- lanes: `{counts.get('lanes', 0)}`",
        f"- runtime_visible_atoms: `{counts.get('runtime_visible_atoms', 0)}`",
        f"- runtime_visible_sources: `{counts.get('runtime_visible_sources', 0)}`",
        f"- planning_probe_total_hits: `{counts.get('planning_probe_total_hits', 0)}`",
        f"- latest_event_age_seconds: `{freshness.get('latest_event_age_seconds')}`",
        "",
        "## Detector Hits",
    ]
    if not hits:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    for hit in hits:
        lines.append(f"- `{hit.severity}` `{hit.detector_id}` `{hit.entity}`: {hit.summary}")
    return "\n".join(lines) + "\n"


def run_guard(config: GuardConfig) -> dict[str, Any]:
    now = time.time()
    events = load_trace_events(config.event_bus_db_path, lookback_seconds=config.lookback_seconds, now=now)
    lanes = load_controller_lanes(config.controller_lane_db_path)

    hits: list[DetectorHit] = []
    hits.extend(detect_missing_heartbeat(events=events, lanes=lanes, config=config, now=now))
    hits.extend(detect_started_without_terminal(events=events, config=config, now=now))
    hits.extend(detect_tool_failure_spike(events=events, config=config))
    hits.extend(detect_telemetry_contract_violations(events=events, config=config))
    planning_hits, planning_probe = detect_planning_opt_in_zero_hit(config=config)
    hits.extend(planning_hits)
    evomap_hits, evomap_visibility = detect_evomap_runtime_visibility_regression(config=config)
    hits.extend(evomap_hits)

    hits.sort(key=lambda item: (SEVERITY_ORDER.get(item.severity, 99), item.detector_id, item.entity))
    state_summary = _build_state_summary(
        config=config,
        now=now,
        events=events,
        lanes=lanes,
        planning_probe=planning_probe,
        evomap_visibility=evomap_visibility,
    )
    incident_summary = _build_incident_summary(hits)
    digest = render_digest(state_summary=state_summary, incident_summary=incident_summary, hits=hits)
    return {
        "ok": not hits,
        "generated_at": state_summary["generated_at"],
        "state_summary": state_summary,
        "incident_summary": incident_summary,
        "detector_hits": [hit.to_dict() for hit in hits],
        "runtime_guard_latest_md": digest,
    }


def write_artifacts(report: dict[str, Any], *, output_root: Path) -> Path:
    output_dir = output_root / _timestamp_dir_name()
    output_dir.mkdir(parents=True, exist_ok=True)
    _json_dump(output_dir / "state_summary.json", report["state_summary"])
    _json_dump(output_dir / "incident_summary.json", report["incident_summary"])
    _json_dump(output_dir / "detector_hits.json", report["detector_hits"])
    (output_dir / "runtime_guard_latest.md").write_text(report["runtime_guard_latest_md"], encoding="utf-8")
    _json_dump(output_dir / "runtime_guard_report.json", report)

    latest_json = output_root / "latest.json"
    latest_md = output_root / "latest.md"
    latest_json.parent.mkdir(parents=True, exist_ok=True)
    _json_dump(latest_json, {"artifact_dir": str(output_dir), **report["incident_summary"], "generated_at": report["generated_at"]})
    latest_md.write_text(report["runtime_guard_latest_md"], encoding="utf-8")
    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Observe-first OpenClaw runtime guard sidecar.")
    parser.add_argument("--event-bus-db-path", default=resolve_openmind_event_bus_db_path())
    parser.add_argument("--controller-lane-db-path", default=str(DEFAULT_CONTROLLER_LANE_DB_PATH))
    parser.add_argument("--evomap-db-path", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--lookback-seconds", type=float, default=1800.0)
    parser.add_argument("--heartbeat-stale-seconds", type=float, default=900.0)
    parser.add_argument("--workflow-sla-seconds", type=float, default=1800.0)
    parser.add_argument("--tool-failure-ratio-threshold", type=float, default=0.5)
    parser.add_argument("--tool-failure-min-samples", type=int, default=3)
    parser.add_argument(
        "--required-identity-field",
        action="append",
        dest="required_identity_fields",
        default=[],
        help="Execution telemetry fields that must be present. May be repeated.",
    )
    parser.add_argument("--planning-probe-query", action="append", default=[])
    parser.add_argument("--planning-probe-top-k", type=int, default=5)
    parser.add_argument("--planning-probe-timeout-seconds", type=float, default=20.0)
    parser.add_argument("--planning-bundle-dir", default=os.environ.get("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR", "").strip())
    parser.add_argument("--planning-bundle-root", default=os.environ.get("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_ROOT", "").strip())
    parser.add_argument("--base-url", default="http://127.0.0.1:18711")
    parser.add_argument("--bearer-token", default=os.environ.get("CHATGPTREST_OPS_TOKEN", "").strip() or os.environ.get("CHATGPTREST_API_TOKEN", "").strip())
    parser.add_argument("--evomap-min-runtime-visible-atoms", type=int, default=1)
    parser.add_argument("--evomap-min-runtime-sources", type=int, default=1)
    parser.add_argument("--output-dir", default="")
    return parser.parse_args()


def args_to_config(args: argparse.Namespace) -> GuardConfig:
    required_identity_fields = tuple(args.required_identity_fields) if args.required_identity_fields else DEFAULT_REQUIRED_IDENTITY_FIELDS
    planning_queries = tuple(query for query in args.planning_probe_query if _safe_text(query)) or DEFAULT_PLANNING_PROBE_QUERIES
    output_root = Path(args.output_dir) if args.output_dir else Path(args.output_root)
    return GuardConfig(
        event_bus_db_path=Path(args.event_bus_db_path).expanduser(),
        controller_lane_db_path=Path(args.controller_lane_db_path).expanduser(),
        evomap_db_path=Path(args.evomap_db_path).expanduser(),
        output_root=output_root,
        lookback_seconds=float(args.lookback_seconds),
        heartbeat_stale_seconds=float(args.heartbeat_stale_seconds),
        workflow_sla_seconds=float(args.workflow_sla_seconds),
        tool_failure_ratio_threshold=float(args.tool_failure_ratio_threshold),
        tool_failure_min_samples=int(args.tool_failure_min_samples),
        required_identity_fields=required_identity_fields,
        planning_probe_queries=planning_queries,
        planning_probe_top_k=int(args.planning_probe_top_k),
        planning_probe_timeout_seconds=float(args.planning_probe_timeout_seconds),
        planning_bundle_dir=_safe_text(args.planning_bundle_dir),
        planning_bundle_root=_safe_text(args.planning_bundle_root),
        base_url=_safe_text(args.base_url),
        bearer_token=_safe_text(args.bearer_token),
        evomap_min_runtime_visible_atoms=int(args.evomap_min_runtime_visible_atoms),
        evomap_min_runtime_sources=int(args.evomap_min_runtime_sources),
    )


def main() -> int:
    args = parse_args()
    config = args_to_config(args)
    try:
        report = run_guard(config)
        artifact_dir = write_artifacts(report, output_root=config.output_root)
    except Exception as exc:
        failure = {
            "ok": False,
            "error": str(exc),
            "generated_at": _utc_now_iso(),
        }
        json.dump(failure, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 1

    report_out = {
        "ok": report["ok"],
        "generated_at": report["generated_at"],
        "artifact_dir": str(artifact_dir),
        "incident_summary": report["incident_summary"],
    }
    json.dump(report_out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
