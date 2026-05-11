#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED_PHASES = [
    "phase0_baseline",
    "phase1_operating_kernel",
    "phase2_finbot_flywheel",
    "phase3_planning_main_loop",
    "phase4_governance_capability",
    "phase5_memory_substrate",
    "phase6_learning_local_llm",
]

FORBIDDEN_CLAIMS = [
    "production-ready",
    "production ready",
    "fully autonomous",
    "investment advice",
    "target price recommendation",
    "trade signal",
    "automatic trading",
    "broker action",
    "production watchlist",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_operator_review_phase_20260511.py <phase7-root>", file=sys.stderr)
        return 2

    root = Path(sys.argv[1])
    repo = Path.cwd()
    errors: list[dict[str, str]] = []

    required_files = [
        "operator_dashboard.md",
        "review_packet_manifest.json",
        "public_packet_safety_result.json",
        "next_execution_queue.tsv",
    ]
    for rel in required_files:
        if not (root / rel).exists():
            errors.append({"code": "missing_required_file", "path": str(root / rel)})

    dashboard = root / "operator_dashboard.md"
    if dashboard.exists():
        text = dashboard.read_text(encoding="utf-8").lower()
        for claim in FORBIDDEN_CLAIMS:
            if claim in text:
                errors.append({"code": "forbidden_dashboard_claim", "claim": claim})
        for marker in [
            "current status",
            "active companies",
            "last successful issue",
            "current blockers",
            "candidate capabilities",
            "next queue",
            "forbidden claims",
        ]:
            if marker not in text:
                errors.append({"code": "dashboard_missing_marker", "marker": marker})

    safety_path = root / "public_packet_safety_result.json"
    if safety_path.exists():
        safety = load_json(safety_path)
        if safety.get("status") != "pass":
            errors.append({"code": "public_packet_safety_not_pass", "status": str(safety.get("status"))})
        for key in ["secret_scan", "large_file_check", "forbidden_path_check", "hash_manifest_check"]:
            if safety.get(key) != "pass":
                errors.append({"code": "public_packet_safety_gate_not_pass", "gate": key, "status": str(safety.get(key))})

    manifest_path = root / "review_packet_manifest.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        artifacts = manifest.get("artifacts", [])
        if len(artifacts) < 8:
            errors.append({"code": "review_manifest_too_small", "count": str(len(artifacts))})
        for item in artifacts:
            item_path = item.get("path", "")
            if not item_path:
                errors.append({"code": "manifest_artifact_missing_path"})
                continue
            if any(bad in item_path for bad in ["/MAIN/secrets/", ".env", "auth.json", "session", "sec_cache"]):
                errors.append({"code": "unsafe_manifest_path", "path": item_path})

    long_root = repo / "docs/paperclip_long_range_os"
    for phase in REQUIRED_PHASES:
        phase_root = long_root / phase
        if not phase_root.exists():
            errors.append({"code": "missing_prior_phase_root", "phase": phase})
            continue
        result_paths = list(phase_root.glob("*validator_result.json")) + list(phase_root.glob("validator_result.json"))
        if not result_paths:
            errors.append({"code": "missing_prior_phase_validator_result", "phase": phase})
            continue
        passed = False
        for result_path in result_paths:
            try:
                result = load_json(result_path)
            except Exception as exc:  # noqa: BLE001
                errors.append({"code": "invalid_prior_phase_validator_json", "phase": phase, "path": str(result_path), "error": repr(exc)})
                continue
            passed = passed or result.get("status") == "pass"
        if not passed:
            errors.append({"code": "prior_phase_not_pass", "phase": phase})

    result = {
        "schema": "paperclip.long_range.phase7.operator_review.validator.v1",
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }
    out = root / "validator_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
