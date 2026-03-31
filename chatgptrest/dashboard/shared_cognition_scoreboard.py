from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from chatgptrest.kernel.market_gate import get_capability_gap_recorder
from ops.sync_skill_platform_frontend_consumers import inspect_frontend_skill_platform_consumers


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "docs" / "dev_log" / "artifacts"


def _artifact_root() -> Path:
    raw = str(os.environ.get("CHATGPTREST_SHARED_COGNITION_ARTIFACT_ROOT") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_ARTIFACT_ROOT


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _latest_report(prefix: str, *, artifact_root: Path) -> tuple[Path | None, dict[str, Any]]:
    candidates = sorted(artifact_root.glob(f"{prefix}*/report_v1.json"))
    if not candidates:
        return None, {}
    latest = candidates[-1]
    try:
        return latest, _read_json(latest)
    except Exception:
        return latest, {}


def _latest_report_from_prefixes(*prefixes: str, artifact_root: Path) -> tuple[Path | None, dict[str, Any]]:
    for prefix in prefixes:
        path, payload = _latest_report(prefix, artifact_root=artifact_root)
        if path is not None:
            return path, payload
    return None, {}


def _summarize_semantic_validation(*, artifact_root: Path) -> dict[str, Any]:
    path, payload = _latest_report("phase8_multi_ingress_work_sample_validation_", artifact_root=artifact_root)
    if path is None or not payload:
        return {
            "status": "missing",
            "evidence_path": "",
            "dataset_name": "",
            "num_items": 0,
            "num_cases": 0,
            "num_failed": 0,
        }
    num_failed = int(payload.get("num_failed") or 0)
    return {
        "status": "ok" if num_failed == 0 else "failed",
        "evidence_path": str(path),
        "dataset_name": str(payload.get("dataset_name") or ""),
        "num_items": int(payload.get("num_items") or 0),
        "num_cases": int(payload.get("num_cases") or 0),
        "num_failed": num_failed,
    }


def _summarize_skill_consumers() -> dict[str, Any]:
    try:
        rows = inspect_frontend_skill_platform_consumers()
    except Exception as exc:
        return {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "summary": {"total": 0, "ok": 0, "stale": 0, "missing": 0},
            "consumers": [],
        }
    summary = {
        "total": len(rows),
        "ok": sum(1 for row in rows if row.get("status") == "ok"),
        "stale": sum(1 for row in rows if row.get("status") == "stale"),
        "missing": sum(1 for row in rows if row.get("status") == "missing"),
    }
    if summary["total"] == 0:
        status = "missing"
    elif summary["stale"] == 0 and summary["missing"] == 0:
        status = "ok"
    elif summary["ok"] > 0:
        status = "degraded"
    else:
        status = "missing"
    return {
        "status": status,
        "summary": summary,
        "consumers": rows,
    }


def _summarize_market_candidate_runtime(*, artifact_root: Path) -> dict[str, Any]:
    report_path, payload = _latest_report("skill_market_candidate_lifecycle_validation_", artifact_root=artifact_root)
    db_path = str(os.environ.get("OPENMIND_SKILL_PLATFORM_DB") or "").strip()
    try:
        recorder = get_capability_gap_recorder(db_path=db_path)
        open_gaps = recorder.fetch_gaps(status="open")
        closed_gaps = recorder.fetch_gaps(status="closed")
        candidate_statuses = ("quarantine", "evaluated", "promoted", "deprecated")
        candidate_counts = {
            status: len(recorder.list_market_candidates(status=status, limit=1000))
            for status in candidate_statuses
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "evidence_path": str(report_path) if report_path else "",
            "gap_counts": {"open": 0, "closed": 0},
            "candidate_counts": {},
            "checks": {},
        }
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    lifecycle_ok = bool(checks.get("lifecycle_roundtrip_ok")) if checks else False
    if report_path is None:
        status = "missing"
    elif lifecycle_ok:
        status = "ok"
    else:
        status = "failed"
    return {
        "status": status,
        "evidence_path": str(report_path) if report_path else "",
        "gap_counts": {"open": len(open_gaps), "closed": len(closed_gaps)},
        "candidate_counts": candidate_counts,
        "checks": checks,
    }


def _summarize_four_terminal_acceptance(*, artifact_root: Path) -> dict[str, Any]:
    path, payload = _latest_report_from_prefixes(
        "four_terminal_live_acceptance_",
        "shared_cognition_four_terminal_acceptance_",
        artifact_root=artifact_root,
    )
    if path is None:
        return {
            "status": "pending",
            "evidence_path": "",
            "summary": "pending_live_acceptance",
        }
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    status = "ok" if bool(checks.get("all_terminals_green")) else "failed"
    return {
        "status": status,
        "evidence_path": str(path),
        "summary": str(payload.get("summary") or ""),
        "checks": checks,
    }


def build_shared_cognition_status_board() -> dict[str, Any]:
    artifact_root = _artifact_root()
    semantic_validation = _summarize_semantic_validation(artifact_root=artifact_root)
    skill_consumers = _summarize_skill_consumers()
    market_candidate_runtime = _summarize_market_candidate_runtime(artifact_root=artifact_root)
    four_terminal_acceptance = _summarize_four_terminal_acceptance(artifact_root=artifact_root)

    blockers: list[str] = []
    if semantic_validation["status"] != "ok":
        blockers.append("multi_ingress_semantic_validation_not_green")
    if skill_consumers["status"] != "ok":
        blockers.append("skill_platform_runtime_consumers_not_green")
    if market_candidate_runtime["status"] != "ok":
        blockers.append("external_skill_candidate_lifecycle_not_green")
    if four_terminal_acceptance["status"] != "ok":
        blockers.append("four_terminal_live_acceptance_pending")

    return {
        "generated_at": time.time(),
        "artifact_root": str(artifact_root),
        "refresh_status": "ok",
        "shared_cognition": {
            "semantic_validation": semantic_validation,
            "skill_platform_runtime_consumers": skill_consumers,
            "market_candidate_runtime": market_candidate_runtime,
            "four_terminal_acceptance": four_terminal_acceptance,
            "remaining_blockers": blockers,
            "owner_scope_ready": not any(
                blocker in blockers
                for blocker in (
                    "multi_ingress_semantic_validation_not_green",
                    "skill_platform_runtime_consumers_not_green",
                    "external_skill_candidate_lifecycle_not_green",
                )
            ),
            "system_scope_ready": len(blockers) == 0,
        },
    }


def render_shared_cognition_status_board_markdown(payload: dict[str, Any]) -> str:
    board = payload.get("shared_cognition") if isinstance(payload.get("shared_cognition"), dict) else {}
    semantic = board.get("semantic_validation") if isinstance(board.get("semantic_validation"), dict) else {}
    consumers = board.get("skill_platform_runtime_consumers") if isinstance(board.get("skill_platform_runtime_consumers"), dict) else {}
    market = board.get("market_candidate_runtime") if isinstance(board.get("market_candidate_runtime"), dict) else {}
    four_terminal = board.get("four_terminal_acceptance") if isinstance(board.get("four_terminal_acceptance"), dict) else {}
    summary = consumers.get("summary") if isinstance(consumers.get("summary"), dict) else {}
    blockers = board.get("remaining_blockers") if isinstance(board.get("remaining_blockers"), list) else []
    lines = [
        "# Shared Cognition Status Board",
        "",
        f"- refresh_status: `{payload.get('refresh_status', 'unknown')}`",
        f"- owner_scope_ready: `{bool(board.get('owner_scope_ready'))}`",
        f"- system_scope_ready: `{bool(board.get('system_scope_ready'))}`",
        "",
        "## Semantic Validation",
        f"- status: `{semantic.get('status', 'missing')}`",
        f"- dataset: `{semantic.get('dataset_name', '')}`",
        f"- cases: `{semantic.get('num_cases', 0)}`",
        f"- failed: `{semantic.get('num_failed', 0)}`",
        f"- evidence: `{semantic.get('evidence_path', '')}`",
        "",
        "## Skill Runtime Consumers",
        f"- status: `{consumers.get('status', 'missing')}`",
        f"- total: `{summary.get('total', 0)}`",
        f"- ok: `{summary.get('ok', 0)}`",
        f"- stale: `{summary.get('stale', 0)}`",
        f"- missing: `{summary.get('missing', 0)}`",
        "",
        "## Market Candidate Runtime",
        f"- status: `{market.get('status', 'missing')}`",
        f"- evidence: `{market.get('evidence_path', '')}`",
        f"- open_gaps: `{(market.get('gap_counts') or {}).get('open', 0)}`",
        f"- closed_gaps: `{(market.get('gap_counts') or {}).get('closed', 0)}`",
        "",
        "## Four-Terminal Acceptance",
        f"- status: `{four_terminal.get('status', 'pending')}`",
        f"- evidence: `{four_terminal.get('evidence_path', '')}`",
        "",
        "## Remaining Blockers",
    ]
    if blockers:
        for item in blockers:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def write_shared_cognition_status_board(
    payload: dict[str, Any],
    *,
    out_dir: str | Path,
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "report_v1.json"
    md_path = out_path / "report_v1.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_shared_cognition_status_board_markdown(payload), encoding="utf-8")
    return json_path, md_path
