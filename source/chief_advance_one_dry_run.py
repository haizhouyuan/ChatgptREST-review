#!/usr/bin/env python3
"""Dry-run transition checker for the Hermes chief control plane.

This script is intentionally read-only. It consumes a declared chief manifest
and a board snapshot fixture, then emits a JSON decision. It does not call
Multica, mutate issues, read auth files, or inspect raw secret stores.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "docs/control_plane/chief_manifest.v0.json"
DEFAULT_FIXTURE = ROOT / "docs/control_plane/fixtures/current_high_drift_asf9_blocked.json"
FIXTURE_DIR = ROOT / "docs/control_plane/fixtures"

HIGH_OR_CRITICAL = {"high", "critical"}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3}
PROJECT_PRIORITY_ORDER = {"planned": 0, "active": 1, "backlog": 2, "dormant": 3, "none": 4}
RED_TEAM_CLEARING_GRADES = {"A", "B"}
SECRET_KEY_MARKERS = (
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "secret",
    "password",
    "oauth",
    "bearer",
)
SAFE_SECRET_POLICY_KEYS = {"secret_policy"}


class DryRunError(Exception):
    """Raised for malformed inputs that should produce fail-closed output."""


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise DryRunError(f"file_not_found:{path}") from exc
    except json.JSONDecodeError as exc:
        raise DryRunError(f"invalid_json:{path}:{exc.msg}") from exc


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def utc_run_id() -> str:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    return "chief-dry-run-" + now.isoformat().replace("+00:00", "Z")


def required_path(obj: dict[str, Any], path: str) -> tuple[bool, Any]:
    cursor: Any = obj
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return False, None
        cursor = cursor[part]
    return True, cursor


def validate_manifest(manifest: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest_not_object"]

    required = [
        "manifest_id",
        "manifest_version",
        "actor.agent_id",
        "actor.name",
        "actor.workspace_id",
        "runtime.runtime_provider",
        "runtime.runtime_mode",
        "model.provider",
        "model.name",
        "model.reasoning_effort",
        "auth.lane_id",
        "auth.secret_policy",
        "mcp.lanes",
        "skills.multica_visible_agent_skills_expected",
        "tool_scope.default_mode",
        "transitions.may_propose",
        "transitions.dry_run_only",
        "transitions.forbidden",
        "red_team.primary_gate",
        "red_team.fallback_gate",
        "red_team.fallback_independence",
    ]
    for path in required:
        ok, value = required_path(manifest, path)
        if not ok:
            errors.append(f"missing_required:{path}")
        elif value in (None, ""):
            errors.append(f"empty_required:{path}")

    if manifest.get("manifest_id") != "chief-control-plane":
        errors.append("invalid_manifest_id")

    model = manifest.get("model", {})
    if isinstance(model, dict):
        if model.get("provider") != "openai-codex":
            errors.append("invalid_model_provider")
        if model.get("name") != "gpt-5.5":
            errors.append("invalid_model_name")
        if model.get("reasoning_effort") != "xhigh":
            errors.append("invalid_reasoning_effort")

    transitions = manifest.get("transitions", {})
    if isinstance(transitions, dict):
        if transitions.get("dry_run_only") is not True:
            errors.append("dry_run_only_not_true")
        forbidden = transitions.get("forbidden", [])
        if not isinstance(forbidden, list) or "execute_transition" not in forbidden:
            errors.append("execute_transition_not_forbidden")

    lanes = manifest.get("mcp", {}).get("lanes", []) if isinstance(manifest.get("mcp"), dict) else []
    if not isinstance(lanes, list) or not lanes:
        errors.append("mcp_lanes_empty")

    if find_secret_like_fields(manifest):
        errors.append("secret_like_field_present_in_manifest")

    return errors


def find_secret_like_fields(value: Any, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            lowered = str(key).lower()
            if lowered not in SAFE_SECRET_POLICY_KEYS and any(marker in lowered for marker in SECRET_KEY_MARKERS):
                if nested not in (None, "", [], {}):
                    findings.append(key_path)
            findings.extend(find_secret_like_fields(nested, key_path))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            findings.extend(find_secret_like_fields(item, f"{path}[{idx}]"))
    return findings


def build_drift_items(manifest: dict[str, Any], board: dict[str, Any]) -> list[dict[str, Any]]:
    drift: list[dict[str, Any]] = []
    chief_state = board.get("chief_state", {})
    if not isinstance(chief_state, dict):
        return [
            {
                "field": "chief_state",
                "expected": "object",
                "actual": type(chief_state).__name__,
                "severity": "critical",
                "required_action": "block_transition",
            }
        ]

    expected_model = manifest.get("model", {})
    if isinstance(expected_model, dict):
        for field, severity in (("name", "high"), ("reasoning_effort", "high")):
            expected = expected_model.get(field)
            actual_key = "model" if field == "name" else field
            actual = chief_state.get(actual_key)
            if expected and actual != expected:
                drift.append(
                    {
                        "field": f"model.{field}",
                        "expected": expected,
                        "actual": actual,
                        "severity": severity,
                        "required_action": "block_transition",
                    }
                )

    expected_mcp_lanes = []
    for lane in manifest.get("mcp", {}).get("lanes", []):
        if isinstance(lane, dict):
            expected_mcp_lanes.append(lane.get("name"))
    visible_mcp = chief_state.get("mcp_config")
    visible_lanes = []
    if isinstance(visible_mcp, dict):
        lanes_value = visible_mcp.get("lanes", [])
        if isinstance(lanes_value, list):
            visible_lanes = lanes_value
    for lane_name in expected_mcp_lanes:
        if lane_name and lane_name not in visible_lanes:
            drift.append(
                {
                    "field": f"mcp.lanes.{lane_name}.multica_visible",
                    "expected": "present",
                    "actual": "absent",
                    "severity": "high",
                    "required_action": "block_transition",
                }
            )

    skills = chief_state.get("skills")
    expected_skills_visible = manifest.get("skills", {}).get("multica_visible_agent_skills_expected")
    if expected_skills_visible is True and (not isinstance(skills, list) or not skills):
        drift.append(
            {
                "field": "skills.multica_visible_agent_skills",
                "expected": "non_empty_summary",
                "actual": skills,
                "severity": manifest.get("skills", {}).get("drift_if_empty_in_multica", "high"),
                "required_action": "block_transition",
            }
        )

    secret_fields = find_secret_like_fields(board)
    for field in secret_fields:
        drift.append(
            {
                "field": field,
                "expected": "no_secret_like_values_in_snapshot",
                "actual": "redacted_by_checker",
                "severity": "critical",
                "required_action": "block_transition",
            }
        )
    return drift


def has_high_or_critical_drift(drift_items: list[dict[str, Any]]) -> bool:
    return any(item.get("severity") in HIGH_OR_CRITICAL for item in drift_items)


def issue_sort_key(issue: dict[str, Any]) -> tuple[Any, ...]:
    unlock = issue.get("sidecar_unlock_order")
    unlock_key = unlock if isinstance(unlock, int) else 999999
    priority_key = PRIORITY_ORDER.get(str(issue.get("priority", "none")).lower(), PRIORITY_ORDER["none"])
    project_key = PROJECT_PRIORITY_ORDER.get(
        str(issue.get("project_priority", "none")).lower(),
        PROJECT_PRIORITY_ORDER["none"],
    )
    number = issue.get("number")
    number_key = number if isinstance(number, int) else 999999
    created_at = issue.get("created_at") or ""
    return (unlock_key, priority_key, project_key, number_key, created_at)


def evaluate_issue(
    issue: dict[str, Any],
    *,
    high_drift: bool,
) -> dict[str, Any]:
    failed: list[str] = []
    dependencies = issue.get("dependencies", [])
    red_team = issue.get("red_team", {})
    contract = issue.get("contract", {})

    if not issue.get("id"):
        failed.append("issue_exists")
    if issue.get("status") != "todo":
        failed.append("issue_status_is_todo")
    if not isinstance(contract, dict) or contract.get("full") is not True:
        failed.append("full_issue_contract_present")

    if isinstance(dependencies, list):
        blocked = [
            dep.get("identifier") or dep.get("id")
            for dep in dependencies
            if isinstance(dep, dict) and dep.get("status") in {"blocked", "unresolved"}
        ]
        if blocked:
            failed.append("no_blocked_dependency")
    else:
        failed.append("dependency_snapshot_valid")

    if isinstance(red_team, dict) and red_team.get("status") in {"blocked", "conditional_no_go", "no_go"}:
        failed.append("no_open_red_team_blocker")
    if high_drift:
        failed.append("no_live_drift_severity_high_or_above")
    if issue.get("action_class") == "implementation":
        failed.append("action_class_not_implementation")
    if issue.get("risk_class") == "high":
        grade = red_team.get("independence_grade") if isinstance(red_team, dict) else None
        if grade not in RED_TEAM_CLEARING_GRADES:
            failed.append("high_risk_requires_independent_red_team_gate")

    return {
        "issue_id": issue.get("id"),
        "identifier": issue.get("identifier"),
        "eligible": not failed,
        "failed_checks": failed,
        "sort_key": list(issue_sort_key(issue)),
    }


def choose_candidate(evaluations: list[dict[str, Any]], issues_by_id: dict[str, dict[str, Any]]) -> tuple[str | None, list[str]]:
    eligible = [item for item in evaluations if item.get("eligible")]
    if not eligible:
        return None, []
    eligible.sort(key=lambda item: tuple(item.get("sort_key", [])))
    if len(eligible) > 1:
        first_key = tuple(eligible[0].get("sort_key", []))
        second_key = tuple(eligible[1].get("sort_key", []))
        if first_key == second_key:
            return None, ["ambiguous_candidate_selection"]
    candidate_id = eligible[0].get("issue_id")
    if candidate_id not in issues_by_id:
        return None, ["candidate_missing_from_issue_snapshot"]
    return str(candidate_id), []


def advance_one(manifest: dict[str, Any], board: dict[str, Any], run_id: str) -> dict[str, Any]:
    manifest_errors = validate_manifest(manifest)
    drift_items = [] if manifest_errors else build_drift_items(manifest, board)
    if manifest_errors:
        drift_items = [
            {
                "field": "manifest",
                "expected": "valid_control_plane_manifest",
                "actual": manifest_errors,
                "severity": "critical",
                "required_action": "block_transition",
            }
        ]

    issues = board.get("issues", [])
    if not isinstance(issues, list):
        issues = []
        manifest_errors.append("board_issues_not_list")

    high_drift = has_high_or_critical_drift(drift_items)
    evaluations = [
        evaluate_issue(issue, high_drift=high_drift)
        for issue in issues
        if isinstance(issue, dict)
    ]
    issues_by_id = {
        str(issue.get("id")): issue
        for issue in issues
        if isinstance(issue, dict) and issue.get("id")
    }

    proposed_issue_id, selection_failures = choose_candidate(evaluations, issues_by_id)
    failed_checks: list[str] = []
    failed_checks.extend(manifest_errors)
    if high_drift:
        failed_checks.append("high_or_critical_drift_present")
    failed_checks.extend(selection_failures)
    for item in evaluations:
        for check in item.get("failed_checks", []):
            label = f"{item.get('identifier') or item.get('issue_id')}:{check}"
            if label not in failed_checks:
                failed_checks.append(label)

    allowed_action = "no_op"
    if not manifest_errors and not high_drift:
        if proposed_issue_id:
            allowed_action = "propose_transition"
        elif drift_items:
            allowed_action = "drift_report_only"

    result: dict[str, Any] = {
        "run_id": run_id,
        "manifest_hash": canonical_hash(manifest),
        "board_state_hash": canonical_hash(board),
        "drift_items": drift_items,
        "eligible_candidates": [item for item in evaluations if item.get("eligible")],
        "failed_checks": failed_checks,
        "allowed_action": allowed_action,
        "proposed_issue_id": proposed_issue_id if allowed_action == "propose_transition" else None,
        "evaluated_issues": evaluations,
        "dry_run_only": True,
    }
    return result


def run_self_test(manifest_path: Path, fixture_dir: Path) -> dict[str, Any]:
    cases = [
        ("current_high_drift_asf9_blocked.json", "no_op", None),
        ("metadata_drift_missing_mcp_skills.json", "no_op", None),
        ("multiple_eligible_ambiguous.json", "no_op", None),
        ("fallback_grade_c_high_risk.json", "no_op", None),
        ("clean_low_risk_governance.json", "propose_transition", "clean-low-risk-governance"),
    ]
    manifest = load_json(manifest_path)
    results = []
    ok = True
    for fixture_name, expected_action, expected_issue_id in cases:
        board = load_json(fixture_dir / fixture_name)
        result = advance_one(manifest, board, run_id=f"self-test:{fixture_name}")
        case_ok = result["allowed_action"] == expected_action and result["proposed_issue_id"] == expected_issue_id
        ok = ok and case_ok
        results.append(
            {
                "fixture": fixture_name,
                "expected_action": expected_action,
                "actual_action": result["allowed_action"],
                "expected_issue_id": expected_issue_id,
                "actual_issue_id": result["proposed_issue_id"],
                "ok": case_ok,
            }
        )

    invalid_manifest = load_json(fixture_dir / "manifest_invalid_missing_model.json")
    clean_board = load_json(fixture_dir / "clean_low_risk_governance.json")
    invalid_result = advance_one(invalid_manifest, clean_board, run_id="self-test:manifest-invalid")
    invalid_ok = invalid_result["allowed_action"] == "no_op" and "missing_required:model.provider" in invalid_result["failed_checks"]
    ok = ok and invalid_ok
    results.append(
        {
            "fixture": "manifest_invalid_missing_model.json",
            "expected_action": "no_op",
            "actual_action": invalid_result["allowed_action"],
            "expected_check": "missing_required:model.provider",
            "ok": invalid_ok,
        }
    )

    return {
        "ok": ok,
        "cases": results,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hermes chief advance_one dry-run checker")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Path to chief manifest JSON")
    parser.add_argument("--board-snapshot", type=Path, default=DEFAULT_FIXTURE, help="Path to board snapshot fixture JSON")
    parser.add_argument("--run-id", default=None, help="Stable run id for reproducible evidence")
    parser.add_argument("--self-test", action="store_true", help="Run all bundled fixture checks")
    parser.add_argument("--fixture-dir", type=Path, default=FIXTURE_DIR, help="Fixture directory for --self-test")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            payload = run_self_test(args.manifest, args.fixture_dir)
            print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
            return 0 if payload["ok"] else 1

        manifest = load_json(args.manifest)
        board = load_json(args.board_snapshot)
        payload = advance_one(manifest, board, run_id=args.run_id or utc_run_id())
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
        return 0
    except DryRunError as exc:
        payload = {
            "run_id": args.run_id or utc_run_id(),
            "manifest_hash": None,
            "board_state_hash": None,
            "drift_items": [
                {
                    "field": "input",
                    "expected": "readable_json_inputs",
                    "actual": str(exc),
                    "severity": "critical",
                    "required_action": "block_transition",
                }
            ],
            "eligible_candidates": [],
            "failed_checks": ["input_read_error"],
            "allowed_action": "no_op",
            "proposed_issue_id": None,
            "dry_run_only": True,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
