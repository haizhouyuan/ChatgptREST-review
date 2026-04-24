#!/usr/bin/env python3
"""Scheduled read-only dry-run reporter for the Hermes chief control plane.

This script is the local replacement for the paused Multica create-issue
autopilot. It collects a sanitized live snapshot, runs the existing dry-run
checker, scans the generated artifacts for secret-like material, and writes a
local report under state/. It performs no Multica writes itself.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "state/control_plane/sweeps"
SNAPSHOT_SCRIPT = ROOT / "ops/scripts/chief_collect_live_snapshot.py"
DRY_RUN_SCRIPT = ROOT / "ops/scripts/chief_advance_one_dry_run.py"
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("vendor_key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("authorization_header", re.compile(r"(?i)\bAuthorization\s*:")),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{10,}")),
    ("api_key_assignment", re.compile(r"(?i)\bapi[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9._~+/-]{8,}")),
    ("access_token_assignment", re.compile(r"(?i)\baccess[_-]?token\s*[:=]\s*['\"]?[A-Za-z0-9._~+/-]{8,}")),
    ("refresh_token_assignment", re.compile(r"(?i)\brefresh[_-]?token\s*[:=]\s*['\"]?[A-Za-z0-9._~+/-]{8,}")),
    ("password_assignment", re.compile(r"(?i)\bpassword\s*[:=]\s*['\"]?[^'\"\s]{8,}")),
]


class ReportError(Exception):
    """Fail-closed scheduled report error."""


def now_rfc3339() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_slug() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReportError(f"missing_json:{path}") from exc
    except json.JSONDecodeError as exc:
        raise ReportError(f"invalid_json:{path}:{exc.msg}") from exc


def run_command(cmd: list[str], *, timeout: int) -> str:
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ReportError(f"timeout:{' '.join(cmd)}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        message = detail[0] if detail else "no_error_output"
        raise ReportError(f"command_failed:{' '.join(cmd)}:{message}")
    return proc.stdout


def scan_file(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    findings: list[dict[str, str]] = []
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append({"path": str(path), "pattern": name, "match_preview": "[redacted]"})
    return findings


def atomic_write_json(path: Path, payload: dict[str, Any], *, pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=pretty) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as fh:
        tmp_name = fh.name
        fh.write(encoded)
    try:
        os.replace(tmp_name, path)
    except OSError as exc:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise ReportError(f"atomic_write_failed:{path}:{exc}") from exc


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    stamp = args.stamp or now_slug()
    run_id = args.run_id or f"chief-scheduled-dry-run-{stamp}"
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = output_dir / f"{stamp}.snapshot.json"
    decision_path = output_dir / f"{stamp}.decision.json"
    report_path = output_dir / f"{stamp}.report.json"

    run_command(
        [
            sys.executable,
            str(SNAPSHOT_SCRIPT),
            "--snapshot-id",
            run_id,
            "--output",
            str(snapshot_path),
            "--pretty",
        ],
        timeout=args.timeout,
    )
    decision_stdout = run_command(
        [
            sys.executable,
            str(DRY_RUN_SCRIPT),
            "--board-snapshot",
            str(snapshot_path),
            "--run-id",
            run_id,
            "--pretty",
        ],
        timeout=args.timeout,
    )
    decision_path.write_text(decision_stdout, encoding="utf-8")

    snapshot = load_json(snapshot_path)
    decision = load_json(decision_path)
    findings = scan_file(snapshot_path) + scan_file(decision_path)
    if findings:
        raise ReportError("secret_scan_failed")

    drift_items = decision.get("drift_items", [])
    eligible = decision.get("eligible_candidates", [])
    if not isinstance(drift_items, list):
        raise ReportError("decision_drift_items_not_list")
    if not isinstance(eligible, list):
        raise ReportError("decision_eligible_candidates_not_list")

    report = {
        "schema_version": "0.1.0",
        "report_id": run_id,
        "created_at": now_rfc3339(),
        "mode": "read_only_local_report",
        "artifacts": {
            "snapshot_path": str(snapshot_path),
            "snapshot_sha256": sha256_file(snapshot_path),
            "decision_path": str(decision_path),
            "decision_sha256": sha256_file(decision_path),
        },
        "decision": {
            "allowed_action": decision.get("allowed_action"),
            "proposed_issue_id": decision.get("proposed_issue_id"),
            "eligible_count": len(eligible),
            "drift_count": len(drift_items),
            "manifest_hash": decision.get("manifest_hash"),
            "board_state_hash": decision.get("board_state_hash"),
            "dry_run_only": decision.get("dry_run_only"),
        },
        "drift_summary": [
            {
                "field": item.get("field"),
                "severity": item.get("severity"),
                "required_action": item.get("required_action"),
            }
            for item in drift_items
            if isinstance(item, dict)
        ],
        "source_counts": {
            "snapshot_issues": len(snapshot.get("issues", [])) if isinstance(snapshot, dict) else None,
            "evaluated_issues": len(decision.get("evaluated_issues", [])) if isinstance(decision, dict) else None,
        },
        "secret_scan": {
            "status": "passed",
            "patterns": [name for name, _pattern in SECRET_PATTERNS],
            "matches": [],
        },
        "control_boundary": {
            "multica_writes": False,
            "auth_reads": False,
            "issue_creation": False,
            "transition_execution": False,
        },
    }
    atomic_write_json(report_path, report, pretty=True)
    return report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id")
    parser.add_argument("--stamp")
    parser.add_argument("--timeout", type=int, default=60)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    try:
        report = build_report(parse_args(argv))
    except ReportError as exc:
        print(f"chief_scheduled_dry_run_report failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report["decision"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
