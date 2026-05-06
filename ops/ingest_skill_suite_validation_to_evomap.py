#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chatgptrest.advisor.runtime import get_advisor_runtime, reset_advisor_runtime
from chatgptrest.cognitive.telemetry_service import TelemetryEventInput, TelemetryIngestService
from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.eval.experiment_registry import ExperimentCandidate, ExperimentRegistry
from chatgptrest.evomap.knowledge.skill_suite_review_plane import import_validation_bundle


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "skill_suite_evomap_ingest"
DEFAULT_REGISTRY_PATH = REPO_ROOT / "artifacts" / "monitor" / "skill_suite_experiment_registry.json"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _new_output_dir(root: Path, validation_id: str) -> Path:
    candidate = root / f"{_now_stamp()}_{validation_id}"
    if not candidate.exists():
        return candidate
    idx = 1
    while True:
        candidate = root / f"{_now_stamp()}_{validation_id}_{idx:02d}"
        if not candidate.exists():
            return candidate
        idx += 1


def _load_bundle(bundle_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = _read_json(bundle_dir / "MANIFEST.json")
    case_matrix = _read_json(bundle_dir / "case_matrix.json")
    summary = _read_json(bundle_dir / "summary.json")
    return manifest, case_matrix, summary


def _candidate_exists(registry_path: Path, candidate_id: str) -> bool:
    if not registry_path.exists():
        return False
    payload = _read_json(registry_path)
    return any(str(item.get("candidate_id") or "") == candidate_id for item in payload.get("candidates", []))


def register_bundle_experiment(
    *,
    manifest: dict[str, Any],
    summary: dict[str, Any],
    registry_path: Path,
    owner: str,
    stage: str,
) -> dict[str, Any]:
    registry = ExperimentRegistry(registry_path)
    candidate_id = f"skill_suite_validation::{manifest['validation_id']}"
    if not _candidate_exists(registry_path, candidate_id):
        registry.register_candidate(
            ExperimentCandidate(
                candidate_id=candidate_id,
                decision_id=manifest["validation_id"],
                decision_type="skill_suite_validation",
                owner=owner,
                stage="proposed",
                rollback_trigger="bundle validation mismatch or missing evidence",
            )
        )
    run = registry.start_run(candidate_id=candidate_id, stage=stage, owner=owner)
    outcome = "passed" if summary.get("cases_matching_expectation", 0) == summary.get("case_count", 0) else "failed"
    run = registry.record_result(
        run_id=run.run_id,
        outcome=outcome,
        evidence={
            "validation_id": manifest["validation_id"],
            "case_count": summary.get("case_count", 0),
            "cases_matching_expectation": summary.get("cases_matching_expectation", 0),
            "cases_with_missing_paths": summary.get("cases_with_missing_paths", 0),
            "git_head": manifest.get("repo", {}).get("git_head", ""),
        },
    )
    return {
        "candidate_id": candidate_id,
        "run": run.to_dict(),
        "registry_path": str(registry_path),
    }


def build_telemetry_inputs(
    *,
    manifest: dict[str, Any],
    case_matrix: dict[str, Any],
    bundle_dir: Path,
    session_id: str,
    agent_name: str,
) -> list[TelemetryEventInput]:
    validation_id = str(manifest["validation_id"])
    repo = manifest.get("repo", {})
    bundle_ok = all(bool(case.get("verdict_matches_expectation")) for case in case_matrix.get("cases", []))
    events: list[TelemetryEventInput] = [
        TelemetryEventInput(
            event_type="workflow.completed" if bundle_ok else "workflow.failed",
            source="skill_suite_validation",
            domain="skill",
            session_id=session_id,
            task_ref=f"skill-suite-validation:{validation_id}",
            repo_name=Path(repo.get("root", REPO_ROOT)).name,
            repo_path=str(repo.get("root", REPO_ROOT)),
            repo_head=str(repo.get("git_head", "")),
            agent_name=agent_name,
            data={
                "validation_signal": "skill.validation.bundle.completed" if bundle_ok else "skill.validation.bundle.failed",
                "validation_id": validation_id,
                "logical_task_id": validation_id,
                "bundle_root": str(bundle_dir),
                "workflow": "skill_suite_validation_bundle",
                "case_count": len(case_matrix.get("cases", [])),
                "cases_matching_expectation": sum(1 for case in case_matrix.get("cases", []) if case.get("verdict_matches_expectation")),
            },
        )
    ]
    for case in case_matrix.get("cases", []):
        case_id = str(case["case_id"])
        ok = bool(case.get("checks_ok")) and bool(case.get("verdict_matches_expectation"))
        events.append(
            TelemetryEventInput(
                event_type="tool.completed" if ok else "tool.failed",
                source="skill_suite_validation",
                domain="skill",
                session_id=session_id,
                task_ref=f"skill-suite-validation:{validation_id}:{case_id}",
                repo_name=Path(repo.get("root", REPO_ROOT)).name,
                repo_path=str(repo.get("root", REPO_ROOT)),
                repo_head=str(repo.get("git_head", "")),
                agent_name=agent_name,
                data={
                    "validation_signal": "skill.validation.case.completed" if ok else "skill.validation.case.failed",
                    "validation_id": validation_id,
                    "case_id": case_id,
                    "logical_task_id": case_id,
                    "suite": case.get("suite", ""),
                    "tool": "skill_suite_validation_case",
                    "variant": case.get("variant", ""),
                    "expected_outcome": case.get("expected_outcome", ""),
                    "checks_ok": case.get("checks_ok", False),
                    "verdict_matches_expectation": case.get("verdict_matches_expectation", False),
                    "missing_paths": list(case.get("missing_paths") or []),
                    "failed_check_ids": [item.get("id", "") for item in case.get("checks", []) if not item.get("passed")],
                },
            )
        )
    return events


def emit_bundle_telemetry(
    *,
    manifest: dict[str, Any],
    case_matrix: dict[str, Any],
    bundle_dir: Path,
    session_id: str,
    trace_id: str,
    agent_name: str,
) -> dict[str, Any]:
    runtime = get_advisor_runtime()
    service = TelemetryIngestService(runtime)
    result = service.ingest(
        trace_id=trace_id,
        session_id=session_id,
        events=build_telemetry_inputs(
            manifest=manifest,
            case_matrix=case_matrix,
            bundle_dir=bundle_dir,
            session_id=session_id,
            agent_name=agent_name,
        ),
    )
    return result.to_dict()


def ingest_bundle(
    *,
    bundle_dir: str | Path,
    db_path: str | Path,
    registry_path: str | Path,
    owner: str,
    stage: str,
    output_dir: str | Path,
    emit_telemetry: bool = True,
    session_id: str = "",
    trace_id: str = "",
    agent_name: str = "codex",
) -> dict[str, Any]:
    bundle_root = Path(bundle_dir)
    manifest, case_matrix, summary = _load_bundle(bundle_root)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    registry_result = register_bundle_experiment(
        manifest=manifest,
        summary=summary,
        registry_path=Path(registry_path),
        owner=owner,
        stage=stage,
    )
    telemetry_result = {
        "ok": False,
        "trace_id": trace_id,
        "recorded": 0,
        "signal_types": [],
        "skipped": True,
    }
    active_trace_id = trace_id or uuid.uuid4().hex
    active_session_id = session_id or f"skill-suite-validation::{manifest['validation_id']}"
    if emit_telemetry:
        telemetry_result = emit_bundle_telemetry(
            manifest=manifest,
            case_matrix=case_matrix,
            bundle_dir=bundle_root,
            session_id=active_session_id,
            trace_id=active_trace_id,
            agent_name=agent_name,
        )
        telemetry_result["skipped"] = False

    import_result = import_validation_bundle(
        db_path=db_path,
        bundle_dir=bundle_root,
        promotion_status="staged",
    )
    result = {
        "ok": True,
        "generated_at": time.time(),
        "bundle_dir": str(bundle_root),
        "validation_id": manifest["validation_id"],
        "trace_id": active_trace_id,
        "session_id": active_session_id,
        "registry": registry_result,
        "telemetry": telemetry_result,
        "review_plane_import": import_result,
        "output_dir": str(out),
    }
    _write_json(out / "summary.json", result)
    _write_json(out / "registry_result.json", registry_result)
    _write_json(out / "telemetry_result.json", telemetry_result)
    _write_json(out / "review_plane_import.json", import_result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a skill-suite validation bundle into telemetry, experiment registry, and EvoMap review plane.")
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH))
    parser.add_argument("--owner", default="codex")
    parser.add_argument("--stage", default="offline_replay")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--trace-id", default="")
    parser.add_argument("--agent-name", default="codex")
    parser.add_argument("--skip-telemetry", action="store_true")
    args = parser.parse_args()

    bundle_root = Path(args.bundle_dir)
    manifest = _read_json(bundle_root / "MANIFEST.json")
    output_dir = Path(args.output_dir) if args.output_dir else _new_output_dir(DEFAULT_OUTPUT_ROOT, str(manifest["validation_id"]))
    result = ingest_bundle(
        bundle_dir=bundle_root,
        db_path=args.db,
        registry_path=args.registry_path,
        owner=args.owner,
        stage=args.stage,
        output_dir=output_dir,
        emit_telemetry=not args.skip_telemetry,
        session_id=args.session_id,
        trace_id=args.trace_id,
        agent_name=args.agent_name,
    )
    print(json.dumps(result, ensure_ascii=False))
    reset_advisor_runtime()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
