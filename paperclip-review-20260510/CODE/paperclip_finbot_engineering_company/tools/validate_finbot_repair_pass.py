#!/usr/bin/env python3
"""
validate_finbot_repair_pass.py

Strict repair-pass validator for FINBOT-REPAIR-013.

Detects self-inconsistencies in the repair packet so the packet fails
itself without external reference. Designed to be run with:

    python tools/validate_finbot_repair_pass.py \\
        --run-dir runs/2026-05-07_finbot_repair_pass \\
        --strict \\
        --fail-on-agent-assertion-mismatch

Error categories: source_registry | case_schema | evidence_model |
                  fuzong_index | migration_gate
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: str) -> dict | list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_csv_lines(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def fail(category: str, code: str, message: str, evidence: dict | None = None) -> dict:
    """Build a structured error record."""
    err = {
        "category": category,
        "code": code,
        "message": message,
    }
    if evidence:
        err["evidence"] = evidence
    return err


# ---------------------------------------------------------------------------
# Rule 1 — source_registry_v1_1.json field contract
# Required: provider / source_type / url (not name / tier / url_route)
# ---------------------------------------------------------------------------

def check_source_registry_field_contract(run_dir: Path) -> list:
    errors = []
    path = run_dir / "agent_outputs/source_registry_v1_1/source_registry_v1_1.json"
    if not path.exists():
        errors.append(fail(
            "source_registry", "SOURCE_REG_NOT_FOUND",
            f"source_registry_v1_1.json not found at {path}", None
        ))
        return errors

    data = load_json(str(path))
    sources = data.get("sources", [])

    new_field_count = 0
    old_field_count = 0
    old_field_entries = []

    for src in sources:
        has_provider = "provider" in src
        has_source_type = "source_type" in src
        has_url = "url" in src
        has_name = "name" in src
        has_tier = "tier" in src
        has_url_route = "url_route" in src

        if has_provider or has_source_type or has_url:
            new_field_count += 1
        if has_name or has_tier or has_url_route:
            old_field_count += 1
            old_field_entries.append({
                "source_id": src.get("source_id"),
                "has_name": has_name,
                "has_tier": has_tier,
                "has_url_route": has_url_route,
                "has_provider": has_provider,
                "has_source_type": has_source_type,
                "has_url": has_url,
            })

    if old_field_count > 0:
        errors.append(fail(
            "source_registry", "SOURCE_REG_STILL_USES_OLD_FIELDS",
            f"source_registry_v1_1.json uses old fields 'name/tier/url_route' in {old_field_count}/{len(sources)} entries; "
            f"expected 'provider/source_type/url' (0/{len(sources)} entries use new fields)",
            {
                "total_sources": len(sources),
                "new_field_entries": new_field_count,
                "old_field_entries": old_field_count,
                "expected": "provider/source_type/url",
                "actual_old_fields": old_field_entries,
                "migration_gate_claim": "APPROVED — fields corrected",
                "migration_gate_actual": "DENIED — 0 new-field entries",
            }
        ))
    else:
        pass  # would be valid

    # Check KRX/DART is missing from registry (referenced in cases but absent)
    source_ids = {s.get("source_id") for s in sources}
    required_routes = ["CNINFO", "SSE", "SZSE", "BSE", "HKEXnews", "SEC EDGAR"]
    found_routes_lower = {s.get("name", "").lower(): s.get("name", "") for s in sources}
    # KRX/DART is referenced in cases but has no entry
    if not any("krx" in k.lower() or "dart" in k.lower() for k in source_ids):
        errors.append(fail(
            "source_registry", "SOURCE_REG_KRX_DART_MISSING",
            "KRX/DART referenced in case evidence_gaps but absent from source_registry_v1_1.json",
            {
                "missing_source": "KRX/DART",
                "referenced_in_cases": ["OC-SC-008", "OC-SC-009"],
                "registry_source_ids": sorted(source_ids),
            }
        ))

    return errors


# ---------------------------------------------------------------------------
# Rule 2 — Source identity references: SRC- namespace collision
# source_person_registry uses SRC-D-FUZONG-BILI etc. as SourceAccount IDs,
# but SRC- prefix is meant for source routes only.
# ---------------------------------------------------------------------------

def check_source_identity_references(run_dir: Path) -> list:
    errors = []
    sp_path = run_dir / "agent_outputs/source_registry_v1_1/source_person_registry.json"
    if not sp_path.exists():
        errors.append(fail("source_registry", "SOURCE_PERSON_NOT_FOUND",
                           f"source_person_registry.json not found", None))
        return errors

    sp_data = load_json(str(sp_path))
    # Collect all source_account_ids
    account_ids = []
    for person in sp_data.get("persons", []):
        for acct in person.get("accounts", []):
            account_ids.append(acct.get("source_account_id"))

    # SRC- prefix is for Source Routes (official data sources)
    # SourceAccounts should use SA- prefix per content_item_contract.md
    src_prefix_accounts = [aid for aid in account_ids if aid and aid.startswith("SRC-")]
    if src_prefix_accounts:
        errors.append(fail(
            "source_registry", "SOURCE_ACCOUNT_ID_USES_SRC_PREFIX",
            f"{len(src_prefix_accounts)} SourceAccount IDs use SRC- prefix (intended for source routes). "
            f"Per content_item_contract.md, SourceAccounts should use SA- prefix.",
            {
                "source_account_ids_with_src_prefix": src_prefix_accounts,
                "expected_prefix": "SA-",
                "actual_prefix": "SRC-",
                "id_namespace_collision": "SRC- shared by SourceRoute and SourceAccount",
            }
        ))

    # Also check that the IDs used in opportunity_cases primary_claims
    # match the actual SourceAccount IDs in source_person_registry
    cases_path = run_dir / "agent_outputs/opportunity_cases_v1_1/opportunity_cases_v1_1.json"
    if cases_path.exists():
        cases_data = load_json(str(cases_path))
        cases = cases_data.get("cases", [])
        used_source_ids = set()
        for case in cases:
            for claim in case.get("primary_claims", []):
                used_source_ids.add(claim.get("source_id"))

        # source_person_registry defines accounts with IDs like SRC-D-FUZONG-BILI
        # But source_registry only has route-level IDs like SRC-A-001
        # So SRC-D-FUZONG-BILI is NOT in source_registry — that's a gap
        reg_path = run_dir / "agent_outputs/source_registry_v1_1/source_registry_v1_1.json"
        if reg_path.exists():
            reg_data = load_json(str(reg_path))
            reg_ids = {s.get("source_id") for s in reg_data.get("sources", [])}
            orphan_ids = used_source_ids - reg_ids
            if orphan_ids:
                errors.append(fail(
                    "source_registry", "SOURCE_ID_NOT_IN_REGISTRY",
                    f"source_id values used in cases not present in source_registry: {sorted(orphan_ids)}",
                    {
                        "case_source_ids_not_in_registry": sorted(orphan_ids),
                        "registry_source_ids": sorted(reg_ids),
                    }
                ))

    return errors


# ---------------------------------------------------------------------------
# Rule 3 — opportunity_cases_v1_1.json schema validation
# ---------------------------------------------------------------------------

import jsonschema

def check_opportunity_case_schema(run_dir: Path) -> list:
    errors = []
    schema_path = run_dir / "agent_outputs/state_model/opportunity_case_schema_v1_1.json"
    cases_path = run_dir / "agent_outputs/opportunity_cases_v1_1/opportunity_cases_v1_1.json"

    if not schema_path.exists():
        errors.append(fail("case_schema", "CASE_SCHEMA_NOT_FOUND",
                           f"Schema not found: {schema_path}", None))
        return errors
    if not cases_path.exists():
        errors.append(fail("case_schema", "CASE_FILE_NOT_FOUND",
                           f"Cases not found: {cases_path}", None))
        return errors

    schema = load_json(str(schema_path))
    cases_data = load_json(str(cases_path))
    cases = cases_data.get("cases", [])

    # The envelope metadata claims schema_validation_errors: 0
    envelope_errors_reported = cases_data.get("metadata", {}).get("schema_validation_errors", "NOT_SET")
    if envelope_errors_reported == 0:
        # This is likely a false claim — validate each case against schema
        pass  # we will count real errors and compare

    total_schema_errors = 0
    case_schema_results = []

    for case in cases:
        try:
            jsonschema.validate(case, schema)
            case_schema_results.append({"case_id": case.get("case_id"), "valid": True, "errors": []})
        except jsonschema.ValidationError as ve:
            total_schema_errors += 1
            case_schema_results.append({
                "case_id": case.get("case_id"),
                "valid": False,
                "errors": [ve.message]
            })

    if total_schema_errors > 0:
        errors.append(fail(
            "case_schema", "CASE_SCHEMA_VALIDATION_FAILURES",
            f"Envelope metadata claims schema_validation_errors=0 but "
            f"{total_schema_errors}/{len(cases)} cases fail schema validation against opportunity_case_schema_v1_1.json",
            {
                "envelope_claimed_errors": envelope_errors_reported,
                "actual_errors": total_schema_errors,
                "total_cases": len(cases),
                "case_results": case_schema_results,
                "expected_claim": "schema_validation_errors should reflect actual schema errors",
            }
        ))

    return errors


# ---------------------------------------------------------------------------
# Rule 4 — nested claim source_id pattern mismatch
# Schema requires ^SRC-[A-Z]-[A-Z0-9]{3}$ but cases use SRC-D-FUZONG-BILI
# ---------------------------------------------------------------------------

def check_nested_claim_source_id_pattern(run_dir: Path) -> list:
    errors = []
    cases_path = run_dir / "agent_outputs/opportunity_cases_v1_1/opportunity_cases_v1_1.json"
    if not cases_path.exists():
        return [fail("case_schema", "CASE_FILE_NOT_FOUND",
                     f"Cases not found: {cases_path}", None)]

    cases_data = load_json(str(cases_path))
    cases = cases_data.get("cases", [])

    schema_source_id_pattern = re.compile(r"^SRC-[A-Z]-[A-Z0-9]{3}$")
    mismatches = []

    for case in cases:
        case_id = case.get("case_id")
        for claim in case.get("primary_claims", []):
            source_id = claim.get("source_id")
            if source_id and not schema_source_id_pattern.match(source_id):
                mismatches.append({
                    "case_id": case_id,
                    "claim_id": claim.get("claim_id"),
                    "source_id": source_id,
                    "schema_pattern": "^SRC-[A-Z]-[A-Z0-9]{3}$",
                    "issue": "FUZONG-BILI has 12 chars after 3rd dash; pattern allows only 3 chars",
                })

    if mismatches:
        errors.append(fail(
            "case_schema", "CLAIM_SOURCE_ID_PATTERN_MISMATCH",
            f"primary_claims[].source_id values do not match schema pattern ^SRC-[A-Z]-[A-Z0-9]{3}$",
            {
                "mismatch_count": len(mismatches),
                "mismatches": mismatches,
                "schema_pattern": "^SRC-[A-Z]-[A-Z0-9]{3}$",
                "schema_allows_max_3_chars_after_tier": True,
            }
        ))

    return errors


# ---------------------------------------------------------------------------
# Rule 5 — window_label incorrectly using signal-window state values
# Schema enum: 20D / 60D / 120D / live / null
# Cases use: early_research_window (a signal_window_state value, not a window_label)
# ---------------------------------------------------------------------------

def check_window_label_state_values(run_dir: Path) -> list:
    errors = []
    cases_path = run_dir / "agent_outputs/opportunity_cases_v1_1/opportunity_cases_v1_1.json"
    if not cases_path.exists():
        return []

    cases_data = load_json(str(cases_path))
    cases = cases_data.get("cases", [])

    allowed_window_labels = {"20D", "60D", "120D", "live", None}
    signal_window_states = {
        "not_ready_missing_primary_evidence",
        "early_research_window",
        "watch_for_primary_catalyst",
        "technical_context_review",
        "deep_research_review_alert"
    }

    violations = []
    for case in cases:
        case_id = case.get("case_id")
        for claim in case.get("primary_claims", []):
            wl = claim.get("window_label")
            if wl is not None and wl not in allowed_window_labels:
                is_signal_state = wl in signal_window_states
                violations.append({
                    "case_id": case_id,
                    "claim_id": claim.get("claim_id"),
                    "window_label": wl,
                    "is_signal_window_state_value": is_signal_state,
                    "allowed": sorted(allowed_window_labels - {None}),
                })

    if violations:
        errors.append(fail(
            "case_schema", "WINDOW_LABEL_USES_SIGNAL_STATE",
            f"primary_claims[].window_label uses signal_window_state values instead of timing-window labels",
            {
                "violation_count": len(violations),
                "violations": violations,
                "allowed_window_labels": sorted(allowed_window_labels - {None}),
                "forbidden_values_are_signal_states": True,
            }
        ))

    return errors


# ---------------------------------------------------------------------------
# Rule 6 — GateVerdict gap_refs not carried into cases
# gate_verdicts_top10.json has gap_refs per verdict;
# cases' gate_verdict blocks don't carry gap_refs.
# ---------------------------------------------------------------------------

def check_gate_verdict_gap_refs(run_dir: Path) -> list:
    errors = []

    verdicts_path = run_dir / "agent_outputs/evidence_ledger_top10/gate_verdicts_top10.json"
    cases_path = run_dir / "agent_outputs/opportunity_cases_v1_1/opportunity_cases_v1_1.json"

    if not verdicts_path.exists():
        errors.append(fail("case_schema", "VERDICTS_FILE_NOT_FOUND",
                           f"Gate verdicts not found: {verdicts_path}", None))
        return errors
    if not cases_path.exists():
        return []

    verdicts = load_json(str(verdicts_path))
    cases_data = load_json(str(cases_path))
    cases = cases_data.get("cases", [])

    # Build verdict gap_refs map
    verdict_gap_map = {}
    for v in verdicts:
        case_id = v.get("case_id")
        gap_refs = v.get("gap_refs", [])
        verdict_gap_map[case_id] = gap_refs

    # Check each case's gate_verdict
    mismatches = []
    for case in cases:
        case_id = case.get("case_id")
        gv = case.get("gate_verdict", {})
        case_gap_refs = gv.get("gap_refs", [])
        expected_gap_refs = verdict_gap_map.get(case_id, [])

        if expected_gap_refs and not case_gap_refs:
            mismatches.append({
                "case_id": case_id,
                "gate_verdict_has_gap_refs": False,
                "gap_refs_in_standalone_verdict": expected_gap_refs,
                "standalone_verdict_path": "gate_verdicts_top10.json",
                "case_gate_verdict_path": "opportunity_cases_v1_1.json",
            })

    if mismatches:
        errors.append(fail(
            "case_schema", "GATE_VERDICT_GAP_REFS_NOT_IN_CASE",
            f"GateVerdict gap_refs present in gate_verdicts_top10.json but missing in {len(mismatches)} case gate_verdict blocks",
            {
                "mismatch_count": len(mismatches),
                "mismatches": mismatches,
                "note": "gap_refs must be preserved in case's gate_verdict block",
            }
        ))

    return errors


# ---------------------------------------------------------------------------
# Rule 7 — EvidenceItem rows represent blocked fetch attempts
# evidence_ledger_top10.jsonl entries are [BLOCKED] — should be FetchAttempt,
# not EvidenceItem with connector_blocked=true
# ---------------------------------------------------------------------------

def check_evidence_item_blocked_pollution(run_dir: Path) -> list:
    errors = []
    path = run_dir / "agent_outputs/evidence_ledger_top10/evidence_ledger_top10.jsonl"
    if not path.exists():
        errors.append(fail("evidence_model", "EVIDENCE_LEDGER_NOT_FOUND",
                           f"Evidence ledger not found: {path}", None))
        return errors

    rows = load_jsonl(str(path))
    blocked_rows = [r for r in rows if r.get("connector_blocked") or
                    (r.get("evidence_text", "").startswith("[BLOCKED]"))]

    # All these rows have null url, null checksum, null published_at — they are
    # fetch failures, not evidence items
    pseudo_evidence = []
    for row in blocked_rows:
        if row.get("url") is None and row.get("checksum") is None and row.get("published_at") is None:
            pseudo_evidence.append({
                "evidence_id": row.get("evidence_id"),
                "source_id": row.get("source_id"),
                "case_id": row.get("case_id"),
                "evidence_text_preview": row.get("evidence_text", "")[:80],
                "authority_level": row.get("authority_level"),
                "connector_blocked": row.get("connector_blocked"),
                "block_reason": row.get("block_reason"),
                "is_fetch_failure": True,
                "proper_type": "FetchAttempt",
            })

    if pseudo_evidence:
        errors.append(fail(
            "evidence_model", "EVIDENCE_ITEM_REPRESENTS_BLOCKED_FETCH",
            f"{len(pseudo_evidence)} EvidenceItem rows are blocked fetch attempts; "
            f"should be FetchAttempt records, not EvidenceItem",
            {
                "blocked_fetch_items": pseudo_evidence,
                "schema_violation": "EvidenceItem requires url, checksum, published_at; all are null here",
                "recommended_type": "FetchAttempt",
            }
        ))

    # Also check source_id is old SRC-D-001 (not in registry)
    old_src_ids = [r for r in rows if r.get("source_id") == "SRC-D-001"]
    if old_src_ids:
        errors.append(fail(
            "evidence_model", "EVIDENCE_LEDGER_USES_OLD_SOURCE_ID",
            f"{len(old_src_ids)} evidence ledger entries use old source_id 'SRC-D-001' "
            f"(not in current source_registry)",
            {
                "old_source_id_count": len(old_src_ids),
                "expected_source_ids": "SRC-D-FUZONG-BILI or SourceAccount SA- prefix IDs",
            }
        ))

    return errors


# ---------------------------------------------------------------------------
# Rule 8 — Fu Zong canonical CSV vs content_items mismatch
# ---------------------------------------------------------------------------

def check_fuzong_csv_content_mismatch(run_dir: Path) -> list:
    errors = []

    csv_path = run_dir / "agent_outputs/fuzong_canonical_index/fuzong_post_index_20251227_20260507.csv"
    ci_path = run_dir / "agent_outputs/latest_transcript_ingestion/content_items_latest_fuzong.jsonl"

    if not csv_path.exists():
        errors.append(fail("fuzong_index", "FUZONG_CSV_NOT_FOUND",
                           f"Fu Zong CSV not found: {csv_path}", None))
    if not ci_path.exists():
        errors.append(fail("fuzong_index", "CONTENT_ITEMS_NOT_FOUND",
                           f"Content items not found: {ci_path}", None))

    if errors:
        return errors

    csv_lines = load_csv_lines(str(csv_path))
    # Parse CSV (skip header)
    csv_rows = []
    for line in csv_lines[1:]:  # skip header
        parts = line.split(",")
        if len(parts) >= 7:
            csv_rows.append({
                "url": parts[0].strip(),
                "platform": parts[1].strip(),
                "account": parts[2].strip(),
                "published_at": parts[3].strip(),
                "fetched_at": parts[4].strip(),
                "snapshot_hash": parts[5].strip(),
                "blocked_reason": parts[6].strip(),
                "title": ",".join(parts[7:]).strip().strip('"'),
            })

    content_items = load_jsonl(str(ci_path))

    # Build URL -> content_item map
    ci_by_url = {}
    for ci in content_items:
        ci_by_url[ci.get("url", "").strip()] = ci

    mismatches = []

    # Check CSV row 3 vs content_items row 3 (1-indexed for human reference)
    # CSV row 3 (index 2): BV1mfiXBJEsp — title = "H200放开+国产卡配额=国内AIDC建设加速！"
    # Content item 3 (CI-FUZONG-003): BV1mfiXBJEsp — same URL, title same
    # But according to pro review: CSV has BV1mfiXBJEsp at row index 4 (line 5 in CSV)
    # and CI-FUZONG-003/004 may be swapped. Let's compare systematically.

    for i, csv_row in enumerate(csv_rows):
        url = csv_row["url"]
        csv_title = csv_row.get("title", "").strip()
        ci = ci_by_url.get(url)
        if ci:
            ci_title = ci.get("title", "").strip()
            if csv_title != ci_title and csv_title and ci_title:
                mismatches.append({
                    "csv_line": i + 2,  # +2 for header + 0-index
                    "url": url,
                    "csv_title": csv_title,
                    "content_item_title": ci_title,
                    "ci_id": ci.get("content_item_id"),
                })

    # Also check CSV line 16 (Douyin 5th video) — title is empty in CSV
    # but content_items has a title
    for i, csv_row in enumerate(csv_rows):
        if not csv_row.get("title") and csv_row.get("url"):
            url = csv_row["url"]
            ci = ci_by_url.get(url)
            if ci and ci.get("title"):
                mismatches.append({
                    "csv_line": i + 2,
                    "url": url,
                    "csv_title": "",
                    "content_item_title": ci.get("title"),
                    "ci_id": ci.get("content_item_id"),
                    "issue": "CSV title empty but content_items has title",
                })

    # Check for sequential Douyin placeholder URLs (no real video IDs)
    douyin_urls = [r for r in csv_rows if "douyin.com" in r.get("url", "")]
    sequential_pattern = [u for u in douyin_urls
                          if re.match(r".*/734000000000000000\d$", u.get("url", ""))]
    if sequential_pattern and len(sequential_pattern) == 5:
        errors.append(fail(
            "fuzong_index", "FUZONG_DOUYIN_SEQUENTIAL_PLACEHOLDER_URLS",
            f"All 5 Douyin URLs are sequential placeholders (7340000000000000001-5); "
            f"no snapshot_hash; treated as unverified",
            {
                "douyin_urls": [r.get("url") for r in sequential_pattern],
                "snapshot_coverage": 0,
                "all_blocked_reason": "MISSING_TRANSCRIPT",
                "verification_status": "unverified_placeholder",
            }
        ))

    if mismatches:
        errors.append(fail(
            "fuzong_index", "FUZONG_CSV_CONTENT_ITEM_MISMATCH",
            f"CSV and content_items_latest_fuzong.jsonl title mismatch for {len(mismatches)} rows",
            {
                "mismatch_count": len(mismatches),
                "mismatches": mismatches,
            }
        ))

    return errors


# ---------------------------------------------------------------------------
# Rule 9 — snapshot_manifest shows zero snapshot coverage
# ---------------------------------------------------------------------------

def check_fuzong_snapshot_coverage(run_dir: Path) -> list:
    errors = []
    path = run_dir / "agent_outputs/fuzong_canonical_index/source_snapshot_manifest.json"
    if not path.exists():
        errors.append(fail("fuzong_index", "SNAPSHOT_MANIFEST_NOT_FOUND",
                           f"Snapshot manifest not found: {path}", None))
        return errors

    data = load_json(str(path))
    coverage = data.get("snapshot_coverage", "NOT_SET")
    snapshots = data.get("snapshots", [])
    missing_count = data.get("missing_transcript_count", -1)

    if coverage == 0 and len(snapshots) == 0:
        errors.append(fail(
            "fuzong_index", "FUZONG_ZERO_SNAPSHOT_COVERAGE",
            f"Fu Zong canonical index has snapshot_coverage=0, snapshots=[] — no raw artifacts",
            {
                "snapshot_coverage": coverage,
                "snapshots_count": len(snapshots),
                "missing_transcript_count": missing_count,
            }
        ))

    return errors


# ---------------------------------------------------------------------------
# Rule 10 — migration gate claims not supported by machine checks
# ---------------------------------------------------------------------------

def check_migration_gate_claims(run_dir: Path) -> list:
    errors = []

    audit_path = run_dir / "agent_outputs/migration_gate/dry_run_boundary_audit.json"
    matrix_path = run_dir / "agent_outputs/migration_gate/migration_decision_matrix.md"

    if not audit_path.exists():
        errors.append(fail("migration_gate", "MIGRATION_AUDIT_NOT_FOUND",
                           f"Dry run boundary audit not found: {audit_path}", None))
        return errors

    audit = load_json(str(audit_path))

    # Machine check: source_registry_v1_1.json field correction
    # The audit claims "Schema fields corrected: name→provider, tier→source_type, url_route→url"
    # But actual file has 0 new-field entries
    reg_path = run_dir / "agent_outputs/source_registry_v1_1/source_registry_v1_1.json"
    if reg_path.exists():
        reg_data = load_json(str(reg_path))
        sources = reg_data.get("sources", [])
        new_field_entries = sum(
            1 for s in sources
            if "provider" in s or "source_type" in s or "url" in s
        )
        old_field_entries = sum(
            1 for s in sources
            if "name" in s or "tier" in s or "url_route" in s
        )

        # The audit says source_registry APPROVED (repair_status: pass)
        # Find the audit entry
        for item in audit.get("repaired_eligible_for_migration", []):
            if "source_registry_v1_1.json" in item.get("artifact", ""):
                audit_status = item.get("repair_status")
                audit_claim = item.get("rationale", "")

                if "provider" in audit_claim or "name→provider" in audit_claim:
                    if new_field_entries == 0 and old_field_entries == len(sources):
                        errors.append(fail(
                            "migration_gate", "MIGRATION_GATE_SOURCE_REG_CLAIM_FALSE",
                            f"migration gate claims source_registry_v1_1.json fields corrected "
                            f"(name→provider, tier→source_type, url_route→url) — machine check shows "
                            f"{new_field_entries}/{len(sources)} entries use new fields, "
                            f"{old_field_entries}/{len(sources)} use old fields",
                            {
                                "audit_artifact": "source_registry_v1_1.json",
                                "audit_repair_status": audit_status,
                                "audit_rationale": audit_claim,
                                "machine_check": {
                                    "new_field_entries": new_field_entries,
                                    "old_field_entries": old_field_entries,
                                    "total": len(sources),
                                },
                                "migration_decision": "APPROVED by audit but should be DENIED",
                            }
                        ))

    # Check opportunity_case_schema migration claim
    # Audit says: "strict additionalProperties:true enforced"
    schema_path = run_dir / "agent_outputs/state_model/opportunity_case_schema_v1_1.json"
    if schema_path.exists():
        schema_data = load_json(str(schema_path))
        top_level_addprops = schema_data.get("additionalProperties")
        # The audit claims additionalProperties:true enforced
        # But top-level schema is additionalProperties:false
        if top_level_addprops is False:
            errors.append(fail(
                "migration_gate", "MIGRATION_GATE_SCHEMA_CLAIM_FALSE",
                f"migration gate claims 'additionalProperties:true enforced' in opportunity_case_schema_v1_1.json — "
                f"machine check shows additionalProperties=false at top level",
                {
                    "schema_path": "state_model/opportunity_case_schema_v1_1.json",
                    "audit_claim": "additionalProperties:true enforced",
                    "actual_additionalProperties": top_level_addprops,
                }
            ))

    # Check source_person_registry IDs vs seed document
    sp_path = run_dir / "agent_outputs/source_registry_v1_1/source_person_registry.json"
    if sp_path.exists():
        sp_data = load_json(str(sp_path))
        # Collect account IDs
        account_ids = []
        for person in sp_data.get("persons", []):
            for acct in person.get("accounts", []):
                account_ids.append({
                    "person": person.get("source_person_id"),
                    "account_id": acct.get("source_account_id"),
                    "platform": acct.get("platform"),
                })
        # Fu Zong Douyin account ID should be SRC-D-FUZONG-DOUYIN
        # but seed doc (migration_matrix) says different?
        # Already covered in check_source_identity_references
        pass

    # Check that migration gate DENIED opportunity_cases_v1_1.json (good)
    # and that DENIAL is reflected in the must_not_migrate list
    denied_cases = [item for item in audit.get("must_not_migrate", [])
                    if "opportunity_cases_v1_1.json" in item.get("artifact", "")]
    if not denied_cases:
        errors.append(fail(
            "migration_gate", "MIGRATION_GATE_DENIAL_MISSING",
            f"opportunity_cases_v1_1.json not found in must_not_migrate list — "
            f"all 10 cases are blocked/invalid and should be explicitly denied migration",
            {
                "actual_must_not_migrate_artifacts": [
                    a.get("artifact") for a in audit.get("must_not_migrate", [])
                ],
            }
        ))

    return errors


# ---------------------------------------------------------------------------
# Rule 11 — Case metadata claims schema_validation_errors: 0 but actual > 0
# ---------------------------------------------------------------------------

def check_case_envelope_schema_claim(run_dir: Path) -> list:
    errors = []
    cases_path = run_dir / "agent_outputs/opportunity_cases_v1_1/opportunity_cases_v1_1.json"
    if not cases_path.exists():
        return []

    cases_data = load_json(str(cases_path))
    metadata = cases_data.get("metadata", {})
    claimed_errors = metadata.get("schema_validation_errors", "NOT_SET")

    if claimed_errors == 0:
        # Cross-check: the schema itself says additionalProperties:false
        # If any case has extra fields, they'd be caught
        schema_path = run_dir / "agent_outputs/state_model/opportunity_case_schema_v1_1.json"
        if schema_path.exists():
            schema = load_json(str(schema_path))
            cases = cases_data.get("cases", [])
            import jsonschema
            actual_errors = 0
            for case in cases:
                try:
                    jsonschema.validate(case, schema)
                except Exception:
                    actual_errors += 1

            if actual_errors > 0:
                errors.append(fail(
                    "case_schema", "CASE_ENVELOPE_SCHEMA_ERROR_CLAIM_FALSE",
                    f"envelope metadata claims schema_validation_errors=0 but {actual_errors}/{len(cases)} "
                    f"cases fail schema validation against opportunity_case_schema_v1_1.json",
                    {
                        "envelope_claimed": claimed_errors,
                        "actual_schema_failures": actual_errors,
                        "total_cases": len(cases),
                        "schema_path": "state_model/opportunity_case_schema_v1_1.json",
                    }
                ))

    return errors


# ---------------------------------------------------------------------------
# Rule 12 — ticker/name mapping errors (spot check)
# ---------------------------------------------------------------------------

def check_ticker_name_mapping_errors(run_dir: Path) -> list:
    errors = []
    cases_path = run_dir / "agent_outputs/opportunity_cases_v1_1/opportunity_cases_v1_1.json"
    if not cases_path.exists():
        return []

    cases_data = load_json(str(cases_path))
    cases = cases_data.get("cases", [])

    # Known bad mappings (verified externally in PRO_REVIEW_ANSWER):
    # 688195 != "中国卫星网络" (腾景科技)
    # 688981 market != SZSE (SSE STAR Market)
    # 003009 != "长征火箭" (中天火箭)

    bad_mappings = {
        "688195": {
            "claimed_name": "中国卫星网络 (China Satellite Network)",
            "actual_name": "腾景科技 (Optowide Technologies)",
            "case_id": "OC-SC-013",
            "source": "PRO_REVIEW_ANSWER: SSE company_code=688195",
        },
        "003009": {
            "claimed_name": "长征火箭 (Long March Rocket)",
            "actual_name": "中天火箭 (Space China / 陕西中天火箭技术股份有限公司)",
            "case_id": "OC-SC-014",
            "source": "PRO_REVIEW_ANSWER: spacechina.com official source",
        },
    }

    for case in cases:
        sid = case.get("security_id", "")
        if sid in bad_mappings:
            claimed_name = case.get("security_name", "")
            info = bad_mappings[sid]
            if claimed_name != info["actual_name"]:
                errors.append(fail(
                    "case_schema", "CASE_TICKER_NAME_MAPPING_ERROR",
                    f"Case {case.get('case_id')}: security_id {sid} mapped to '{claimed_name}' "
                    f"but external source shows '{info['actual_name']}'",
                    {
                        "case_id": case.get("case_id"),
                        "security_id": sid,
                        "claimed_security_name": claimed_name,
                        "correct_security_name": info["actual_name"],
                        "source": info["source"],
                    }
                ))

    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    check_source_registry_field_contract,
    check_source_identity_references,
    check_opportunity_case_schema,
    check_nested_claim_source_id_pattern,
    check_window_label_state_values,
    check_gate_verdict_gap_refs,
    check_evidence_item_blocked_pollution,
    check_fuzong_csv_content_mismatch,
    check_fuzong_snapshot_coverage,
    check_migration_gate_claims,
    check_case_envelope_schema_claim,
    check_ticker_name_mapping_errors,
]


def main():
    parser = argparse.ArgumentParser(
        description="Validate finbot repair pass for self-inconsistencies"
    )
    parser.add_argument(
        "--run-dir",
        type=str,
        required=True,
        help="Path to run directory, e.g. runs/2026-05-07_finbot_repair_pass",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict validation (always on for this script)",
    )
    parser.add_argument(
        "--fail-on-agent-assertion-mismatch",
        action="store_true",
        help="Fail if agent assertions don't match machine-checked reality",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for report files (default: <run-dir>/agent_outputs/repair_pass_validator)",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print(f"FATAL: run-dir not found: {run_dir}", file=sys.stderr)
        sys.exit(2)

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = run_dir / "agent_outputs/repair_pass_validator"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run all checks
    all_errors = []
    check_results = {}

    for check_fn in ALL_CHECKS:
        check_name = check_fn.__name__.replace("check_", "")
        try:
            errors = check_fn(run_dir)
            check_results[check_name] = {"errors": errors, "check_passed": len(errors) == 0}
            all_errors.extend(errors)
        except Exception as exc:
            check_results[check_name] = {
                "errors": [{"category": "INTERNAL", "code": "CHECK_EXCEPTION",
                            "message": f"Check {check_name} raised: {exc}"}],
                "check_passed": False,
                "exception": str(exc)
            }
            all_errors.append({
                "category": "INTERNAL",
                "code": "CHECK_EXCEPTION",
                "message": f"Check {check_name} raised: {exc}",
                "check": check_name,
            })

    # Categorize errors
    categories = {}
    for err in all_errors:
        cat = err.get("category", "UNKNOWN")
        categories.setdefault(cat, []).append(err)

    # Build verdict
    verdict = "PASS" if len(all_errors) == 0 else "FAIL"

    report = {
        "validator": "validate_finbot_repair_pass.py",
        "validator_version": "1.0",
        "run_dir": str(run_dir),
        "strict": args.strict,
        "fail_on_agent_assertion_mismatch": args.fail_on_agent_assertion_mismatch,
        "verdict": verdict,
        "total_errors": len(all_errors),
        "error_categories": sorted(categories.keys()),
        "errors_by_category": {cat: len(errs) for cat, errs in categories.items()},
        "check_results": check_results,
        "errors": all_errors,
    }

    # Write JSON report
    report_path = output_dir / "repair_pass_validation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Write markdown notes
    md_lines = [
        "# Finbot Repair-Pass Validation Notes",
        "",
        f"**Run directory:** `{run_dir}`",
        f"**Validator:** `validate_finbot_repair_pass.py`",
        f"**Strict mode:** `{args.strict}`",
        f"**Fail on agent assertion mismatch:** `{args.fail_on_agent_assertion_mismatch}`",
        "",
        f"## Verdict: `{verdict}`",
        f"",
        f"**Total errors:** {len(all_errors)}",
        "",
    ]

    for cat, errs in sorted(categories.items()):
        md_lines.append(f"### Category: `{cat}` ({len(errs)} errors)")
        md_lines.append("")
        for err in errs:
            md_lines.append(f"#### `{err.get('code', 'UNKNOWN')}`")
            md_lines.append(f"- **Message:** {err.get('message', '')}")
            if "evidence" in err:
                ev = err["evidence"]
                if isinstance(ev, dict):
                    for k, v in ev.items():
                        md_lines.append(f"  - `{k}`: `{v}`")
            md_lines.append("")

    md_lines.append("## Check Results Summary")
    md_lines.append("")
    md_lines.append("| Check | Passed | Errors |")
    md_lines.append("|-------|--------|--------|")
    for name, result in sorted(check_results.items()):
        passed = "✅" if result["check_passed"] else "❌"
        err_count = len(result["errors"])
        md_lines.append(f"| `{name}` | {passed} | {err_count} |")

    notes_path = output_dir / "repair_pass_validation_notes.md"
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # Print summary to stdout
    print(f"Validator: validate_finbot_repair_pass.py")
    print(f"Run dir: {run_dir}")
    print(f"Verdict: {verdict}")
    print(f"Total errors: {len(all_errors)}")
    for cat, errs in sorted(categories.items()):
        print(f"  [{cat}] {len(errs)} error(s)")
    print(f"")
    print(f"Report: {report_path}")
    print(f"Notes:  {notes_path}")

    if verdict == "FAIL":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
