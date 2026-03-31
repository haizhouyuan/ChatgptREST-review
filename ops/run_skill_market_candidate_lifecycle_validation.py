#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MANAGE_SCRIPT = REPO_ROOT / "ops" / "manage_skill_market_candidates.py"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_json_cmd(argv: list[str], *, env: dict[str, str]) -> dict[str, Any]:
    proc = subprocess.run(argv, cwd=str(REPO_ROOT), env=env, check=True, capture_output=True, text=True)
    payload = json.loads(proc.stdout)
    return payload if isinstance(payload, dict) else {}


def _render_markdown(report: dict[str, Any]) -> str:
    checks = report.get("checks") if isinstance(report.get("checks"), dict) else {}
    lines = [
        "# Skill Market Candidate Lifecycle Validation",
        "",
        f"- generated_at: `{report.get('generated_at', '')}`",
        f"- candidate_id: `{report.get('candidate_id', '')}`",
        f"- gap_id: `{report.get('gap_id', '')}`",
        f"- db_path: `{report.get('db_path', '')}`",
        f"- lifecycle_roundtrip_ok: `{bool(checks.get('lifecycle_roundtrip_ok'))}`",
        "",
        "## Statuses",
        f"- register: `{(report.get('register') or {}).get('status', '')}`",
        f"- evaluate: `{(report.get('evaluate') or {}).get('status', '')}`",
        f"- promote: `{(report.get('promote') or {}).get('status', '')}`",
        f"- deprecate: `{(report.get('deprecate') or {}).get('status', '')}`",
        "",
        "## Counts",
        f"- open_gaps: `{(report.get('counts') or {}).get('open_gaps', 0)}`",
        f"- closed_gaps: `{(report.get('counts') or {}).get('closed_gaps', 0)}`",
        f"- promoted_candidates: `{(report.get('counts') or {}).get('promoted_candidates', 0)}`",
        f"- deprecated_candidates: `{(report.get('counts') or {}).get('deprecated_candidates', 0)}`",
    ]
    return "\n".join(lines) + "\n"


def write_skill_market_candidate_lifecycle_report(
    report: dict[str, Any],
    *,
    out_dir: str | Path,
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "report_v1.json"
    md_path = out_path / "report_v1.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return json_path, md_path


def run_skill_market_candidate_lifecycle_validation(
    *,
    out_dir: str | Path,
    db_path: str | Path,
    evomap_db_path: str | Path,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["OPENMIND_SKILL_PLATFORM_DB"] = str(Path(db_path))
    env["OPENMIND_EVOMAP_DB"] = str(Path(evomap_db_path))

    import chatgptrest.kernel.market_gate as market_gate

    market_gate.get_capability_gap_recorder.cache_clear()
    market_gate.get_skill_platform_observer.cache_clear()
    recorder = market_gate.get_capability_gap_recorder(db_path=str(Path(db_path)))

    capability_id = f"external_capability_{uuid.uuid4().hex[:8]}"
    skill_id = f"external-skill-{uuid.uuid4().hex[:8]}"
    trace_id = f"trace-market-{uuid.uuid4().hex[:8]}"
    gap = recorder.promote_unmet(
        trace_id=trace_id,
        agent_id="codex",
        task_type="shared_cognition_acceptance",
        platform="codex",
        unmet_capabilities=[
            {
                "capability_id": capability_id,
                "reason": "bundle_missing",
                "required_by_task": "shared_cognition_acceptance",
                "candidate_bundles": ["shared_cognition_external"],
                "candidate_skills": [skill_id],
            }
        ],
        suggested_agent="codex",
    )[0]

    register = _run_json_cmd(
        [
            sys.executable,
            str(MANAGE_SCRIPT),
            "register",
            "--skill-id",
            skill_id,
            "--source-market",
            "clawhub",
            "--source-uri",
            f"https://example.invalid/{skill_id}",
            "--capability",
            capability_id,
            "--linked-gap-id",
            gap.gap_id,
            "--summary",
            "shared cognition acceptance probe candidate",
        ],
        env=env,
    )
    candidate_id = str(register.get("candidate_id") or "")
    evaluate = _run_json_cmd(
        [
            sys.executable,
            str(MANAGE_SCRIPT),
            "evaluate",
            "--candidate-id",
            candidate_id,
            "--platform",
            "codex",
            "--smoke",
            "passed",
            "--compatibility",
            "passed",
            "--summary",
            "probe smoke + compatibility passed",
        ],
        env=env,
    )
    promote = _run_json_cmd(
        [
            sys.executable,
            str(MANAGE_SCRIPT),
            "promote",
            "--candidate-id",
            candidate_id,
            "--promoted-by",
            "codex",
            "--real-use-trace-id",
            f"trace-real-{uuid.uuid4().hex[:8]}",
            "--real-use-notes",
            "shared cognition acceptance probe real-use",
        ],
        env=env,
    )
    deprecate = _run_json_cmd(
        [
            sys.executable,
            str(MANAGE_SCRIPT),
            "deprecate",
            "--candidate-id",
            candidate_id,
            "--deprecated-by",
            "codex",
            "--reason",
            "probe rollback verification",
            "--reopen-gap",
        ],
        env=env,
    )

    market_gate.get_capability_gap_recorder.cache_clear()
    market_gate.get_skill_platform_observer.cache_clear()
    recorder = market_gate.get_capability_gap_recorder(db_path=str(Path(db_path)))
    open_gaps = recorder.fetch_gaps(status="open")
    closed_gaps = recorder.fetch_gaps(status="closed")
    promoted_candidates = recorder.list_market_candidates(status="promoted", limit=1000)
    deprecated_candidates = recorder.list_market_candidates(status="deprecated", limit=1000)

    report = {
        "generated_at": _now_iso(),
        "db_path": str(Path(db_path)),
        "evomap_db_path": str(Path(evomap_db_path)),
        "gap_id": gap.gap_id,
        "candidate_id": candidate_id,
        "register": register,
        "evaluate": evaluate,
        "promote": promote,
        "deprecate": deprecate,
        "counts": {
            "open_gaps": len(open_gaps),
            "closed_gaps": len(closed_gaps),
            "promoted_candidates": len(promoted_candidates),
            "deprecated_candidates": len(deprecated_candidates),
        },
        "checks": {
            "register_quarantine_ok": str(register.get("status") or "") == "quarantine",
            "evaluate_ok": str(evaluate.get("status") or "") == "evaluated",
            "promote_ok": str(promote.get("status") or "") == "promoted",
            "deprecate_ok": str(deprecate.get("status") or "") == "deprecated",
            "gap_reopened_ok": any(item.gap_id == gap.gap_id for item in open_gaps),
        },
    }
    report["checks"]["lifecycle_roundtrip_ok"] = all(bool(value) for value in report["checks"].values())
    json_path, md_path = write_skill_market_candidate_lifecycle_report(report, out_dir=out_dir)
    report["report_json_path"] = str(json_path)
    report["report_md_path"] = str(md_path)
    return report


def _default_out_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d")
    return REPO_ROOT / "docs" / "dev_log" / "artifacts" / f"skill_market_candidate_lifecycle_validation_{stamp}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an end-to-end market candidate quarantine/evaluate/promote/deprecate validation.")
    parser.add_argument("--out-dir", default=str(_default_out_dir()))
    parser.add_argument("--db-path", default=str(REPO_ROOT / "artifacts" / "tmp" / "skill_market_candidate_validation.db"))
    parser.add_argument("--evomap-db-path", default=str(REPO_ROOT / "artifacts" / "tmp" / "skill_market_candidate_validation_evomap.db"))
    args = parser.parse_args()

    report = run_skill_market_candidate_lifecycle_validation(
        out_dir=args.out_dir,
        db_path=args.db_path,
        evomap_db_path=args.evomap_db_path,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "candidate_id": report["candidate_id"],
                "gap_id": report["gap_id"],
                "report_json_path": report["report_json_path"],
                "report_md_path": report["report_md_path"],
                "lifecycle_roundtrip_ok": report["checks"]["lifecycle_roundtrip_ok"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
