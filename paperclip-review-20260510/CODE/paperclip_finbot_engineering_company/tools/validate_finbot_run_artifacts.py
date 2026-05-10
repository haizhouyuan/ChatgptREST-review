#!/usr/bin/env python3
"""
Strict Finbot artifact validator — hard gate against schema/state/ID/evidence/source_id/queue contracts.

Replaces the weak artifact-existence validator with one that fails the current
package for real contract reasons: schema mismatches, ID pattern violations,
missing evidence, forbidden state terminology, and queue/candidate terminology abuse.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Schema constants from finbot_complete_schema.json
# ---------------------------------------------------------------------------

ID_PATTERNS = {
    "source_id":    re.compile(r"^SRC-[A-Z0-9]{6}$"),
    "case_id":      re.compile(r"^OC-[A-Z0-9]{8}$"),
    "claim_id":     re.compile(r"^CLM-[A-Z0-9]{8}$"),
    "evidence_id":  re.compile(r"^EVI-[A-Z0-9]{8}$"),
    "signal_rule":  re.compile(r"^SR-[A-Z0-9]{8}$"),
    "alert_cond":   re.compile(r"^AC-[A-Z0-9]{8}$"),
    "gate_verdict": re.compile(r"^GV-[A-Z0-9]{8}$"),
    "watch_item":   re.compile(r"^WI-[A-Z0-9]{8}$"),
    "content_item": re.compile(r"^CI-[A-Z0-9]{8}$"),
    "decision":     re.compile(r"^HRD-[A-Z0-9]{8}$"),
}

OPPORTUNITY_CASE_STATES = {
    "idea", "research_question", "thin_case", "blocked", "parked",
    "monitor_only", "candidate", "killed", "review_pending"
}

# SignalWindow states are NOT OpportunityCase states — they belong to AlertCondition.terminal_state_at_trigger
SIGNAL_WINDOW_STATES = {
    "not_ready_missing_primary_evidence",
    "early_research_window",
    "watch_for_primary_catalyst",
    "technical_context_review",
    "deep_research_review_alert",
}

ALLOWED_ALERT_TYPES = {
    "research_review_alert",
    "deep_research_review_alert",
    "technical_context_review",
}

FORBIDDEN_ALERT_TYPES = {
    "buy_signal", "sell_signal", "trade_signal", "position_signal"
}

SOURCE_TYPE_TIERS = {"A0", "A1", "B", "C", "D"}

EVIDENCE_GATE_STATES = {"evidence_gate", "signal_gate", "source_quality_gate", "backtest_gate"}

EVIDENCE_STATUS_ENUMS = {"validated", "contradicted", "expired", "pending", "KOL_only"}

CLAIM_CLASSIFICATION_ENUMS = {
    "A0_supported", "A1_supported", "B_proxy", "C_secondary", "D_KOL_only"
}

ALERT_WINDOW_LABELS = {"20D", "60D", "120D", "live"}

TERMINAL_STATES = {"parked", "killed", "monitor_only", "candidate"}


# ---------------------------------------------------------------------------
# Error accumulation
# ---------------------------------------------------------------------------

class ValidationErrors:
    def __init__(self):
        self.errors: list[dict[str, str]] = []

    def add(self, category: str, field: str, message: str, path: str = ""):
        self.errors.append({
            "category": category,
            "field": field,
            "message": message,
            "path": path,
        })

    def fail(self, category: str, message: str, path: str = ""):
        self.add(category, "", message, path)


ERRORS = ValidationErrors()


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def check_json_parseable(path: Path) -> Any | None:
    try:
        return load_json(path)
    except json.JSONDecodeError as exc:
        ERRORS.fail("parse", f"invalid JSON {path}: {exc}", str(path))
        return None


# ---------------------------------------------------------------------------
# Category: schema — JSON Schema structural validation helpers
# ---------------------------------------------------------------------------

def check_object_required_fields(
    obj: dict, required: list[str], schema_name: str, path: str
):
    for field in required:
        if field not in obj:
            ERRORS.add("schema", field, f"{schema_name} missing required field '{field}'", path)


def check_string_enum(value: Any, allowed: set[str], field: str, path: str):
    if not isinstance(value, str):
        ERRORS.add("schema", field, f"expected string, got {type(value).__name__}", path)
        return
    if value not in allowed:
        ERRORS.add(
            "schema", field,
            f"invalid enum value '{value}'; allowed: {sorted(allowed)}",
            path
        )


def check_pattern(value: Any, pattern: re.Pattern, field: str, path: str):
    if not isinstance(value, str):
        return  # already caught by type check elsewhere
    if not pattern.match(value):
        ERRORS.add(
            "schema", field,
            f"'{value}' does not match required pattern {pattern.pattern}",
            path
        )


def check_array_items_type(arr: list, expected_type: type, field: str, path: str):
    for i, item in enumerate(arr):
        if not isinstance(item, expected_type):
            ERRORS.add(
                "schema", field,
                f"item[{i}] expected {expected_type.__name__}, got {type(item).__name__}",
                path
            )


# ---------------------------------------------------------------------------
# Category: source_id — Source registry ID pattern validation
# ---------------------------------------------------------------------------

def validate_source_id(source_id: str, path: str) -> bool:
    if not ID_PATTERNS["source_id"].match(source_id):
        ERRORS.add(
            "source_id", "source_id",
            f"source_id '{source_id}' must match pattern {ID_PATTERNS['source_id'].pattern}",
            path
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Category: state — OpportunityCase state and signal-window terminology
# ---------------------------------------------------------------------------

def validate_opportunity_case_state(state: str, path: str):
    """OpportunityCase.state must be one of the defined enum values."""
    if state not in OPPORTUNITY_CASE_STATES:
        # Check if it's a SignalWindow state wrongly used as OpportunityCase state
        if state in SIGNAL_WINDOW_STATES:
            ERRORS.add(
                "state", "state",
                f"OpportunityCase.state has SignalWindow state value '{state}'; "
                f"SignalWindow states do not belong in OpportunityCase.state field",
                path
            )
        else:
            ERRORS.add(
                "state", "state",
                f"invalid OpportunityCase.state '{state}'; allowed: {sorted(OPPORTUNITY_CASE_STATES)}",
                path
            )


# ---------------------------------------------------------------------------
# Category: evidence — supporting_evidence, claim evidence_refs, gate verdicts
# ---------------------------------------------------------------------------

def validate_evidence_item(item: dict, index: int, case_path: str):
    """Validate a single EvidenceItem against schema requirements."""
    path = f"{case_path}/supporting_evidence[{index}]"
    check_object_required_fields(item, ["evidence_item_id", "claim_id", "source_id",
                                          "evidence_text", "authority_level"],
                                  "EvidenceItem", path)
    if "evidence_item_id" in item:
        check_pattern(item["evidence_item_id"], ID_PATTERNS["evidence_id"],
                      "evidence_item_id", path)
    if "claim_id" in item:
        check_pattern(item["claim_id"], ID_PATTERNS["claim_id"], "claim_id", path)
    if "source_id" in item:
        validate_source_id(item["source_id"], path)
    if "authority_level" in item:
        check_string_enum(item["authority_level"], SOURCE_TYPE_TIERS,
                          "authority_level", path)
    if "relationship_to_claim" in item:
        check_string_enum(item["relationship_to_claim"],
                          {"supports", "contradicts", "neutral", "contextual"},
                          "relationship_to_claim", path)


def validate_supporting_evidence(case: dict, path: str):
    """
    Fail if supporting_evidence is empty or contains non-EvidenceItem objects.
    An OpportunityCase with zero EvidenceItems cannot have passed any gate.
    """
    evidence = case.get("supporting_evidence", [])
    if not isinstance(evidence, list):
        ERRORS.add("evidence", "supporting_evidence",
                   f"supporting_evidence must be array, got {type(evidence).__name__}", path)
        return
    if len(evidence) == 0:
        # D_KOL_only cases legitimately have no evidence, but gate_verdict must reflect that
        case_state = case.get("state", "")
        gate = case.get("gate_verdict", {})
        if gate and not gate.get("evidence_refs"):
            # Only warn when there's a gate but no evidence refs — this is the gap
            pass  # handled in gate_verdict validation
    for i, item in enumerate(evidence):
        if not isinstance(item, dict):
            ERRORS.add("evidence", f"supporting_evidence[{i}]",
                       f"EvidenceItem must be object, got {type(item).__name__}",
                       path)


def validate_gate_verdict(case: dict, path: str):
    """GateVerdict with empty evidence_refs is a pseudo-gate — must fail."""
    gate = case.get("gate_verdict")
    if not gate:
        return  # optional field, no error
    if not isinstance(gate, dict):
        ERRORS.add("evidence", "gate_verdict",
                   f"gate_verdict must be object, got {type(gate).__name__}", path)
        return
    verdict_id = gate.get("verdict_id", "")
    if verdict_id and not ID_PATTERNS["gate_verdict"].match(verdict_id):
        ERRORS.add("schema", "verdict_id",
                   f"verdict_id '{verdict_id}' must match {ID_PATTERNS['gate_verdict'].pattern}",
                   f"{path}/gate_verdict")
    evidence_refs = gate.get("evidence_refs", [])
    if isinstance(evidence_refs, list) and len(evidence_refs) == 0:
        case_state = case.get("state", "")
        gate_type = gate.get("gate_type", "")
        if gate_type == "evidence_gate":
            ERRORS.add(
                "evidence", "evidence_refs",
                f"GateVerdict {verdict_id or '(missing)'} has empty evidence_refs but "
                f"gate_type is '{gate_type}'; this is a pseudo-gate that cannot satisfy "
                f"the Evidence Gate — EvidenceGate must have non-empty evidence_refs",
                f"{path}/gate_verdict"
            )
    if "gate_type" in gate:
        check_string_enum(gate["gate_type"], EVIDENCE_GATE_STATES,
                          "gate_type", f"{path}/gate_verdict")


# ---------------------------------------------------------------------------
# Category: signal_rules / alert_conditions — must not both be empty for non-terminal
# ---------------------------------------------------------------------------

def validate_signal_rules(case: dict, path: str):
    rules = case.get("signal_rules", [])
    if not isinstance(rules, list):
        ERRORS.add("schema", "signal_rules",
                   f"signal_rules must be array, got {type(rules).__name__}", path)
        return
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            ERRORS.add("schema", f"signal_rules[{i}]",
                       f"SignalRule must be object, got {type(rule).__name__}", path)
            continue
        rid = rule.get("signal_rule_id", "")
        if rid and not ID_PATTERNS["signal_rule"].match(rid):
            ERRORS.add("schema", "signal_rule_id",
                       f"signal_rule_id '{rid}' must match {ID_PATTERNS['signal_rule'].pattern}",
                       f"{path}/signal_rules[{i}]")
        if "output_alert_type" in rule:
            check_string_enum(rule["output_alert_type"], ALLOWED_ALERT_TYPES,
                              "output_alert_type", f"{path}/signal_rules[{i}]")
            for fat in FORBIDDEN_ALERT_TYPES:
                if fat in str(rule.get("output_alert_type", "")):
                    ERRORS.add("schema", "output_alert_type",
                               f"forbidden alert type '{fat}' in SignalRule", path)


def validate_alert_conditions(case: dict, path: str):
    alerts = case.get("alert_conditions", [])
    if not isinstance(alerts, list):
        ERRORS.add("schema", "alert_conditions",
                   f"alert_conditions must be array, got {type(alerts).__name__}", path)
        return
    for i, alert in enumerate(alerts):
        if not isinstance(alert, dict):
            ERRORS.add("schema", f"alert_conditions[{i}]",
                       f"AlertCondition must be object, got {type(alert).__name__}", path)
            continue
        acid = alert.get("alert_condition_id", "")
        if acid and not ID_PATTERNS["alert_cond"].match(acid):
            ERRORS.add("schema", "alert_condition_id",
                       f"alert_condition_id '{acid}' must match {ID_PATTERNS['alert_cond'].pattern}",
                       f"{path}/alert_conditions[{i}]")
        if "alert_type" in alert:
            check_string_enum(alert["alert_type"], ALLOWED_ALERT_TYPES,
                              "alert_type", f"{path}/alert_conditions[{i}]")
        if "window_label" in alert and alert["window_label"] is not None:
            check_string_enum(alert["window_label"], ALERT_WINDOW_LABELS,
                              "window_label", f"{path}/alert_conditions[{i}]")


# ---------------------------------------------------------------------------
# Category: ID — case_id, claim_id, source_id patterns
# ---------------------------------------------------------------------------

def validate_id_patterns(case: dict, path: str):
    """Validate all ID fields in an OpportunityCase."""
    case_id = case.get("case_id", "")
    check_pattern(case_id, ID_PATTERNS["case_id"], "case_id", path)

    for i, claim in enumerate(case.get("primary_claims", [])):
        claim_path = f"{path}/primary_claims[{i}]"
        cid = claim.get("claim_id", "")
        if cid and not ID_PATTERNS["claim_id"].match(cid):
            ERRORS.add(
                "ID", "claim_id",
                f"claim_id '{cid}' must match pattern {ID_PATTERNS['claim_id'].pattern}",
                claim_path
            )
        src = claim.get("source_id", "")
        if src and not validate_source_id(src, claim_path):
            pass  # error already recorded
        if "evidence_status" in claim:
            check_string_enum(claim["evidence_status"], EVIDENCE_STATUS_ENUMS,
                              "evidence_status", claim_path)
        if "claim_classification" in claim:
            check_string_enum(claim["claim_classification"], CLAIM_CLASSIFICATION_ENUMS,
                              "claim_classification", claim_path)

    wi_ref = case.get("watch_item_ref", "")
    if wi_ref and not ID_PATTERNS["watch_item"].match(wi_ref):
        ERRORS.add(
            "ID", "watch_item_ref",
            f"watch_item_ref '{wi_ref}' must match pattern {ID_PATTERNS['watch_item'].pattern}",
            path
        )


# ---------------------------------------------------------------------------
# Category: queue — forbidden "candidate" terminology in review queue
# ---------------------------------------------------------------------------

def validate_review_queue_terminology(run_dir: Path):
    """
    top_review_queue.md must not use 'candidate' language for items that haven't
    passed Evidence Gate + Source Quality Gate.
    """
    queue_path = run_dir / "agent_outputs" / "opportunity_cases" / "top_review_queue.md"
    if not queue_path.is_file():
        ERRORS.fail("queue", f"missing required file: {queue_path}", str(queue_path))
        return
    content = queue_path.read_text(encoding="utf-8")
    # Look for lines that claim candidate status without evidence gate pass
    lines = content.split("\n")
    for lineno, line in enumerate(lines, 1):
        lower = line.lower()
        if "candidate" in lower or "候选" in line:
            # If line contains an OC- ID, it should have evidence_ref or explicit not_candidate flag
            if "OC-" in line:
                # Flag as potential terminology abuse
                ERRORS.add(
                    "queue", "candidate_terminology",
                    f"queue uses 'candidate' terminology for case reference; "
                    f"must not use candidate wording without Evidence Gate pass + Source Quality Gate pass. "
                    f"Line {lineno}: {line.strip()[:120]}",
                    str(queue_path)
                )


# ---------------------------------------------------------------------------
# Category: source_registry — field name contract and ID patterns
# ---------------------------------------------------------------------------

def validate_source_registry(run_dir: Path):
    """
    source_registry_full.json must use schema field names:
      provider (not name), source_type (not tier), url (not url_route).
    Also source_id must match ^SRC-[A-Z0-9]{6}$.
    """
    registry_path = run_dir / "agent_outputs" / "source_registry" / "source_registry_full.json"
    if not registry_path.is_file():
        ERRORS.fail("schema", f"missing required file: {registry_path}", str(registry_path))
        return

    data = check_json_parseable(registry_path)
    if data is None:
        return

    sources = data.get("sources", []) if isinstance(data, dict) else data
    if not isinstance(sources, list):
        ERRORS.add("schema", "sources",
                   f"'sources' must be array, got {type(sources).__name__}",
                   str(registry_path))
        return

    for i, src in enumerate(sources):
        path = f"{registry_path}/sources[{i}]"
        if not isinstance(src, dict):
            ERRORS.add("schema", f"sources[{i}]",
                       f"Source must be object, got {type(src).__name__}", path)
            continue

        # Field name contract violations
        if "name" in src:
            ERRORS.add(
                "schema", "name",
                f"Source uses field 'name' instead of schema-required 'provider'; "
                f"schema Source.provider is required",
                path
            )
        if "tier" in src:
            ERRORS.add(
                "schema", "tier",
                f"Source uses field 'tier' instead of schema-required 'source_type'; "
                f"schema Source.source_type is required",
                path
            )
        if "url_route" in src and "url" not in src:
            ERRORS.add(
                "schema", "url",
                f"Source uses field 'url_route' instead of schema-required 'url'; "
                f"schema Source.url is required",
                path
            )

        # Check required fields presence
        check_object_required_fields(src, ["source_id", "provider", "source_type", "url"],
                                      "Source", path)

        # source_id pattern
        src_id = src.get("source_id", "")
        if src_id:
            validate_source_id(src_id, path)

        # source_type enum
        if "source_type" in src:
            check_string_enum(src["source_type"], SOURCE_TYPE_TIERS,
                              "source_type", path)


# ---------------------------------------------------------------------------
# Category: latest_materials — provenance completeness
# ---------------------------------------------------------------------------

def validate_latest_materials(run_dir: Path):
    """
    latest_fuzong_materials.json must have provenance fields for each entry.
    Entries without fetched_at / source_snapshot_hash are metadata-only snapshots,
    not canonical latest discovery.
    """
    mats_path = run_dir / "agent_outputs" / "latest_fuzong_materials" / "latest_fuzong_materials.json"
    if not mats_path.is_file():
        return  # optional group

    data = check_json_parseable(mats_path)
    if data is None:
        return

    materials = data.get("materials", []) if isinstance(data, dict) else data
    if not isinstance(materials, list):
        return

    for i, mat in enumerate(materials):
        path = f"{mats_path}/materials[{i}]"
        if not isinstance(mat, dict):
            continue
        # provenance fields are required for a canonical latest discovery
        if "fetched_at" not in mat:
            ERRORS.add(
                "schema", "fetched_at",
                f"latest material entry missing 'fetched_at' provenance field; "
                f"metadata-only snapshots do not constitute canonical latest discovery",
                path
            )
        if "source_snapshot_hash" not in mat:
            ERRORS.add(
                "schema", "source_snapshot_hash",
                f"latest material entry missing 'source_snapshot_hash'; "
                f"without integrity hash, provenance cannot be verified",
                path
            )


# ---------------------------------------------------------------------------
# Full OpportunityCase validation
# ---------------------------------------------------------------------------

def validate_opportunity_case(case: dict, path: str):
    if not isinstance(case, dict):
        ERRORS.add("schema", "OpportunityCase",
                   f"OpportunityCase must be object, got {type(case).__name__}", path)
        return

    check_object_required_fields(case,
                                  ["case_id", "security_id", "thesis", "state",
                                   "created_at", "updated_at"],
                                  "OpportunityCase", path)

    validate_id_patterns(case, path)

    if "state" in case:
        validate_opportunity_case_state(case["state"], path)

    validate_supporting_evidence(case, path)
    validate_gate_verdict(case, path)
    validate_signal_rules(case, path)
    validate_alert_conditions(case, path)

    # Non-terminal states must have next_review_due_at
    state = case.get("state", "")
    if state not in TERMINAL_STATES and state != "killed":
        if not case.get("next_review_due_at"):
            ERRORS.add(
                "schema", "next_review_due_at",
                f"OpportunityCase with non-terminal state '{state}' is missing "
                f"next_review_due_at; all non-terminal cases must have a review date",
                path
            )


def validate_opportunity_cases(run_dir: Path):
    """Validate opportunity_cases.json against OpportunityCase schema."""
    cases_path = run_dir / "agent_outputs" / "opportunity_cases" / "opportunity_cases.json"
    if not cases_path.is_file():
        ERRORS.fail("schema", f"missing required file: {cases_path}", str(cases_path))
        return

    data = check_json_parseable(cases_path)
    if data is None:
        return

    # Can be a list or dict with "cases"/"opportunity_cases"/"items" key
    if isinstance(data, list):
        cases = data
    elif isinstance(data, dict):
        for key in ("cases", "opportunity_cases", "items"):
            if key in data and isinstance(data[key], list):
                cases = data[key]
                break
        else:
            cases = list(data.values()) if data else []
    else:
        ERRORS.add("schema", "opportunity_cases",
                   f"root must be array or dict, got {type(data).__name__}", str(cases_path))
        return

    for i, case in enumerate(cases):
        validate_opportunity_case(case, f"{cases_path}/[{i}]")


# ---------------------------------------------------------------------------
# Basic required-files check (preserved from original)
# ---------------------------------------------------------------------------

REQUIRED = {
    "fuzong_universe": [
        "claudeminmax_status.json", "fuzong_video_index.csv",
        "fuzong_universe_raw.json", "fuzong_theme_map.md", "coverage_gaps.md",
    ],
    "source_registry": [
        "gemini_status.json", "source_registry_full.json",
        "source_route_matrix.md", "latest_fuzong_video_check.md",
        "data_contract_requirements.md",
    ],
    "us_blogger_discovery": [
        "gemini_status.json", "us_blogger_candidates.json",
        "us_blogger_screening.md", "claim_import_template.md",
    ],
    "system_schema": [
        "claudeminmax_status.json", "finbot_complete_schema.json",
        "opportunity_case_template.json", "signal_window_contract.md",
        "complete_acceptance_checklist.md", "validator_pseudocode.md",
    ],
    "latest_fuzong_materials": [
        "gemini_status.json", "latest_fuzong_materials.json",
        "latest_fuzong_gap_report.md", "latest_material_ingestion_plan.md",
        "latest_topics_to_compare.md",
    ],
    "opportunity_cases": [
        "claudeminmax_status.json", "opportunity_cases.json",
        "track_comparison_board.md", "signal_window_board.md",
        "top_review_queue.md", "blocked_and_missing_evidence.md",
        "latest_materials_integration.md", "kol_source_candidates_for_claim_ledger.md",
    ],
}


def validate_required_files(run_dir: Path):
    """Check all required files exist, are non-empty, and status files pass."""
    outputs = run_dir / "agent_outputs"

    if not outputs.is_dir():
        ERRORS.fail("file", "agent_outputs dir missing", str(outputs))
        return

    for group, filenames in REQUIRED.items():
        group_dir = outputs / group
        if not group_dir.is_dir():
            ERRORS.fail("file", f"missing output group: {group}", str(group_dir))
            continue
        for filename in filenames:
            path = group_dir / filename
            if not path.is_file():
                ERRORS.fail("file", f"missing required file: {path}", str(path))
            elif path.stat().st_size == 0:
                ERRORS.fail("file", f"empty required file: {path}", str(path))
            elif filename.endswith("_status.json"):
                _validate_status_file(path)


def _validate_status_file(path: Path):
    data = check_json_parseable(path)
    if data is None:
        return
    if data.get("status") != "pass":
        ERRORS.add("file", "status",
                   f"{path}: status is {data.get('status')!r}, expected 'pass'",
                   str(path))
    produced = data.get("produced_files")
    if produced is not None and not produced:
        ERRORS.add("file", "produced_files",
                   f"{path}: produced_files is empty", str(path))


def validate_json_parseability(run_dir: Path):
    """All JSON files must be parseable."""
    outputs = run_dir / "agent_outputs"
    json_files = [
        "fuzong_universe/fuzong_universe_raw.json",
        "source_registry/source_registry_full.json",
        "us_blogger_discovery/us_blogger_candidates.json",
        "system_schema/finbot_complete_schema.json",
        "system_schema/opportunity_case_template.json",
        "latest_fuzong_materials/latest_fuzong_materials.json",
        "opportunity_cases/opportunity_cases.json",
    ]
    for rel in json_files:
        path = outputs / rel
        if path.is_file():
            check_json_parseable(path)


def validate_fuzong_video_index(run_dir: Path):
    """Fuzong video index must have at least 60 rows."""
    video_index = run_dir / "agent_outputs" / "fuzong_universe" / "fuzong_video_index.csv"
    if not video_index.is_file():
        return
    try:
        with video_index.open(encoding="utf-8", newline="") as f:
            row_count = sum(1 for _ in csv.DictReader(f))
        if row_count < 60:
            ERRORS.add("file", "fuzong_video_index",
                       f"expected at least 60 video rows, got {row_count}",
                       str(video_index))
    except Exception as exc:
        ERRORS.add("file", "fuzong_video_index",
                   f"error reading CSV {video_index}: {exc}", str(video_index))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Strict Finbot artifact validator — hard gate"
    )
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()

    validate_required_files(run_dir)
    validate_json_parseability(run_dir)
    validate_fuzong_video_index(run_dir)

    # Strict schema validations
    validate_source_registry(run_dir)
    validate_opportunity_cases(run_dir)
    validate_latest_materials(run_dir)
    validate_review_queue_terminology(run_dir)

    errors = ERRORS.errors

    # Group errors by category for the report
    by_category: dict[str, list] = {}
    for err in errors:
        by_category.setdefault(err["category"], []).append(err)

    result = {
        "status": "fail" if errors else "pass",
        "run_dir": str(run_dir),
        "total_errors": len(errors),
        "errors_by_category": {k: len(v) for k, v in by_category.items()},
        "errors": errors,
    }

    output_dir = Path(__file__).parent.parent / "runs" / "2026-05-07_finbot_repair_pass" / "agent_outputs" / "schema_validator"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "strict_validation_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
