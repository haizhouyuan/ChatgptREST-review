#!/usr/bin/env python3
"""Finbot v2.1 collection-level validator v1.3.

This validator checks complete run bundles, not isolated happy-path files. It
adds the P0 Pro review requirements on top of the v1.2 record checks:

- unknown or missing record_type hard-fails;
- EvidenceItem raw files must exist and match sha256;
- Claim source spans are verified against transcript JSON;
- claim/evidence-gap/opportunity/signal cross references are checked;
- candidate/live-window states are blocked unless claim-level corroboration is
  present;
- forbidden investment language is field-aware;
- Chinese large-currency units are normalized.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

try:
    from validators.rules_v1_2 import load_records
except ModuleNotFoundError:  # direct script execution: python validators/collection_v1_3.py
    from rules_v1_2 import load_records


KNOWN_RECORD_TYPES = {
    "EvidenceItem",
    "FetchAttempt",
    "ContentItem",
    "Claim",
    "EvidenceGap",
    "OpportunityCase",
    "SignalWindow",
    "ReviewWindow",
    "SignalRule",
    "AlertCondition",
    "EvidenceGateVerdict",
}

CORROBORATED_GATE_STATES = {
    "corroborated",
    "claim_level_corroborated",
    "fully_corroborated",
    "corroborated_research_case",
}

CLAIM_EVIDENCE_USES = {
    "claim_corroboration",
    "primary_corroboration",
    "supporting_evidence",
}

STRUCTURAL_FORBIDDEN_TERMS = {
    "buy_signal",
    "sell_signal",
    "trade_signal",
    "position_signal",
    "target_price",
    "target-price",
    "position_sizing",
}

ACTION_FIELD_TERMS = {
    "buy",
    "sell",
    "long",
    "short",
    "position",
    "trade",
    "target price",
    "overweight",
    "underweight",
    "market order",
    "limit order",
    "stop-loss",
    "stop loss",
    "take-profit",
    "take profit",
    "add",
    "reduce",
    "exit",
    "买入",
    "卖出",
    "做多",
    "做空",
    "加仓",
    "减仓",
    "清仓",
    "仓位",
    "目标价",
    "止损",
    "止盈",
    "下单",
}

ACTION_FIELD_NAMES = {
    "action",
    "action_label",
    "alert_text",
    "decision",
    "decision_text",
    "recommendation",
    "recommendation_text",
    "signal_label",
    "signal_text",
    "thesis_action",
}

USD_YI_RE = re.compile(
    r"(?P<start>\d+(?:\.\d+)?)(?:\s*(?:到|-|至)\s*(?P<end>\d+(?:\.\d+)?))?\s*亿\s*美元"
)


@dataclass
class LoadedRecord:
    obj: dict[str, Any]
    path: Path
    index: int

    @property
    def record_type(self) -> str | None:
        value = self.obj.get("record_type") or self.obj.get("type")
        return value if isinstance(value, str) else None

    @property
    def label(self) -> str:
        return f"{self.path}:{self.index}"


@dataclass
class Issue:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def iter_json_paths(paths: Iterable[Path]) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        if path.is_dir():
            found.extend(sorted(p for p in path.rglob("*") if p.suffix in {".json", ".jsonl"}))
        elif path.suffix in {".json", ".jsonl"}:
            found.append(path)
    return found


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_collection(paths: Iterable[Path]) -> list[LoadedRecord]:
    loaded: list[LoadedRecord] = []
    for path in iter_json_paths(paths):
        for idx, record in enumerate(load_records(path)):
            if isinstance(record, dict):
                loaded.append(LoadedRecord(record, path, idx))
    return loaded


def iter_text(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from iter_text(child, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            yield from iter_text(child, f"{path}[{idx}]")


def resolve_path(raw: str, record_path: Path, repo_root: Path) -> Path | None:
    raw_path = Path(raw)
    if raw_path.is_absolute():
        return raw_path if raw_path.exists() else None
    candidates = [repo_root / raw_path, record_path.parent / raw_path]
    candidates.extend(parent / raw_path for parent in record_path.parents)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def record_id(record: dict[str, Any]) -> str | None:
    rtype = record.get("record_type") or record.get("type")
    type_key = {
        "EvidenceItem": "evidence_item_id",
        "FetchAttempt": "fetch_attempt_id",
        "ContentItem": "content_item_id",
        "Claim": "claim_id",
        "EvidenceGap": "evidence_gap_id",
        "OpportunityCase": "opportunity_case_id",
        "SignalWindow": "signal_window_id",
        "ReviewWindow": "review_window_id",
        "SignalRule": "signal_rule_id",
        "EvidenceGateVerdict": "verdict_id",
    }.get(str(rtype))
    if type_key:
        value = record.get(type_key)
        if isinstance(value, str):
            return value
    return None


def validate_collection(records: list[LoadedRecord], repo_root: Path) -> dict[str, Any]:
    issues: list[Issue] = []
    by_type: dict[str, list[LoadedRecord]] = {}
    by_id: dict[str, LoadedRecord] = {}

    for rec in records:
        rtype = rec.record_type
        if not rtype:
            issues.append(Issue("MISSING_RECORD_TYPE", rec.label, "record_type is required"))
            continue
        if rtype not in KNOWN_RECORD_TYPES:
            issues.append(Issue("UNKNOWN_RECORD_TYPE", rec.label, f"unknown record_type: {rtype}"))
            continue
        by_type.setdefault(rtype, []).append(rec)
        rid = record_id(rec.obj)
        if rid:
            by_id[rid] = rec

        _check_future_timestamps(rec, issues)
        _check_forbidden_language(rec, issues)

    content_by_id = {
        rec.obj["content_item_id"]: rec
        for rec in by_type.get("ContentItem", [])
        if rec.obj.get("content_item_id")
    }

    for rec in by_type.get("EvidenceItem", []):
        _validate_evidence_item(rec, issues, repo_root)
    for rec in by_type.get("FetchAttempt", []):
        _validate_fetch_attempt(rec, issues)
    for rec in by_type.get("Claim", []):
        _validate_claim(rec, issues, content_by_id, repo_root)
    for rec in by_type.get("EvidenceGap", []):
        _validate_evidence_gap(rec, issues, by_id)
    for rec in by_type.get("OpportunityCase", []):
        _validate_opportunity_case(rec, issues, by_id)
    for rec in by_type.get("SignalWindow", []):
        _validate_signal_window(rec, issues, by_id)
    for rec in by_type.get("ReviewWindow", []):
        _validate_review_window(rec, issues, by_id)

    return {
        "status": "pass" if not issues else "blocked",
        "record_count": len(records),
        "record_type_counts": {key: len(value) for key, value in sorted(by_type.items())},
        "issue_count": len(issues),
        "issues": [issue.to_dict() for issue in issues],
    }


def _check_future_timestamps(rec: LoadedRecord, issues: list[Issue]) -> None:
    now = datetime.now(timezone.utc)
    for key in ("published_at", "available_at", "fetched_at", "generated_at"):
        if key not in rec.obj:
            continue
        parsed = parse_iso(rec.obj[key])
        if not parsed:
            issues.append(Issue("BAD_TIMESTAMP", f"{rec.label}.{key}", f"{key} must be ISO timestamp"))
        elif parsed > now:
            issues.append(Issue("FUTURE_DATED_EVIDENCE", f"{rec.label}.{key}", f"{key} is in the future"))


def _check_forbidden_language(rec: LoadedRecord, issues: list[Issue]) -> None:
    for text_path, text in iter_text(rec.obj, rec.label):
        lowered = text.lower()
        for term in STRUCTURAL_FORBIDDEN_TERMS:
            if term in lowered:
                issues.append(Issue("FORBIDDEN_TRADING_LANGUAGE", text_path, f"forbidden structural term '{term}' found"))
        field_name = text_path.rsplit(".", 1)[-1]
        if field_name in ACTION_FIELD_NAMES:
            for term in ACTION_FIELD_TERMS:
                if term in lowered:
                    issues.append(Issue("FORBIDDEN_TRADING_LANGUAGE", text_path, f"forbidden action term '{term}' found"))


def _validate_evidence_item(rec: LoadedRecord, issues: list[Issue], repo_root: Path) -> None:
    obj = rec.obj
    for key in ("evidence_item_id", "source_route_id", "raw_path", "sha256", "fetched_at", "published_at", "available_at"):
        if not obj.get(key):
            issues.append(Issue("EV_MISSING_REQUIRED_FIELD", f"{rec.label}.{key}", f"EvidenceItem missing {key}"))
    if obj.get("source_account_id") or str(obj.get("source_type", "")).upper() == "D":
        issues.append(Issue("KOL_CLAIM_NOT_EVIDENCE_ITEM", rec.label, "D-tier material cannot emit EvidenceItem"))
    raw_path = obj.get("raw_path")
    sha = obj.get("sha256")
    if isinstance(raw_path, str) and isinstance(sha, str):
        resolved = resolve_path(raw_path, rec.path, repo_root)
        if not resolved:
            issues.append(Issue("EV_RAW_PATH_NOT_FOUND", f"{rec.label}.raw_path", f"raw_path not found: {raw_path}"))
        elif sha256_file(resolved).lower() != sha.lower():
            issues.append(Issue("EV_SHA256_MISMATCH", f"{rec.label}.sha256", f"sha256 does not match raw_path {raw_path}"))


def _validate_fetch_attempt(rec: LoadedRecord, issues: list[Issue]) -> None:
    obj = rec.obj
    if obj.get("status") == "blocked" and not obj.get("block_reason"):
        issues.append(Issue("BLOCKED_FETCH_MISSING_REASON", rec.label, "blocked FetchAttempt must include block_reason"))


def _validate_claim(
    rec: LoadedRecord,
    issues: list[Issue],
    content_by_id: dict[str, LoadedRecord],
    repo_root: Path,
) -> None:
    obj = rec.obj
    for key in ("claim_id", "content_item_id", "published_at", "available_at", "source_span", "claim_type", "claim_level"):
        if not obj.get(key):
            issues.append(Issue("CLAIM_MISSING_SOURCE_TRACE", f"{rec.label}.{key}", f"Claim missing {key}"))
    if str(obj.get("source_account_id", "")).startswith("SA-D-") and not obj.get("evidence_gap_ids"):
        issues.append(Issue("KOL_CLAIM_WITHOUT_EVIDENCE_GAP", rec.label, "KOL claim requires evidence_gap_ids"))

    content = content_by_id.get(obj.get("content_item_id", ""))
    if content:
        _validate_source_span(rec, content, issues, repo_root)
    else:
        issues.append(Issue("CLAIM_CONTENT_ITEM_NOT_FOUND", f"{rec.label}.content_item_id", "Claim content_item_id not found in collection"))

    _validate_numeric_money_units(rec, issues)


def _validate_source_span(
    claim: LoadedRecord,
    content: LoadedRecord,
    issues: list[Issue],
    repo_root: Path,
) -> None:
    span = claim.obj.get("source_span")
    if not isinstance(span, dict):
        return
    local = content.obj.get("local_transcript_json")
    if not isinstance(local, str):
        issues.append(Issue("CLAIM_TRANSCRIPT_NOT_AVAILABLE", claim.label, "ContentItem missing local_transcript_json"))
        return
    transcript_path = resolve_path(local, content.path, repo_root)
    if not transcript_path:
        issues.append(Issue("CLAIM_TRANSCRIPT_NOT_FOUND", claim.label, f"transcript not found: {local}"))
        return
    try:
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(Issue("CLAIM_TRANSCRIPT_BAD_JSON", claim.label, str(exc)))
        return
    start = span.get("json_index_start")
    end = span.get("json_index_end")
    if not isinstance(start, int) or not isinstance(end, int) or not (0 <= start <= end < len(transcript)):
        issues.append(Issue("CLAIM_SOURCE_SPAN_BAD_INDEX", claim.label, "source_span json_index range is invalid"))
        return
    joined = "".join(str(seg.get("text", "")) for seg in transcript[start : end + 1])
    expected = str(span.get("transcript_text", ""))
    if expected not in joined and joined not in expected:
        issues.append(Issue("CLAIM_SOURCE_SPAN_TEXT_MISMATCH", claim.label, "source_span transcript_text does not match transcript JSON"))
    if abs(float(transcript[start].get("start", 0)) - float(span.get("start_seconds", -1))) > 0.01:
        issues.append(Issue("CLAIM_SOURCE_SPAN_TIME_MISMATCH", claim.label, "source_span start_seconds does not match transcript JSON"))
    if abs(float(transcript[end].get("end", 0)) - float(span.get("end_seconds", -1))) > 0.01:
        issues.append(Issue("CLAIM_SOURCE_SPAN_TIME_MISMATCH", claim.label, "source_span end_seconds does not match transcript JSON"))


def _validate_numeric_money_units(rec: LoadedRecord, issues: list[Issue]) -> None:
    text = " ".join(
        str(part)
        for part in (
            rec.obj.get("claim_text", ""),
            rec.obj.get("source_span", {}).get("transcript_text", "")
            if isinstance(rec.obj.get("source_span"), dict)
            else "",
        )
    )
    matches = list(USD_YI_RE.finditer(text))
    if not matches:
        return
    values = rec.obj.get("numeric_values")
    if not isinstance(values, list) or not values:
        issues.append(Issue("NUMERIC_NORMALIZATION_MISSING", rec.label, "Chinese 亿美元 claim requires numeric_values normalization"))
        return
    for match in matches:
        raw_text = match.group(0)
        start = float(match.group("start"))
        end = float(match.group("end")) if match.group("end") else None
        found = False
        for value in values:
            if not isinstance(value, dict) or value.get("raw_text") != raw_text:
                continue
            if value.get("normalized_unit") != "billion_usd":
                continue
            if end is None:
                if abs(float(value.get("normalized_value", -999999)) - start * 0.1) < 1e-6:
                    found = True
            else:
                normalized_range = value.get("normalized_range")
                if (
                    isinstance(normalized_range, list)
                    and len(normalized_range) == 2
                    and abs(float(normalized_range[0]) - start * 0.1) < 1e-6
                    and abs(float(normalized_range[1]) - end * 0.1) < 1e-6
                ):
                    found = True
        if not found:
            issues.append(Issue("NUMERIC_NORMALIZATION_BAD", rec.label, f"missing or wrong normalization for {raw_text}"))


def _validate_evidence_gap(rec: LoadedRecord, issues: list[Issue], by_id: dict[str, LoadedRecord]) -> None:
    obj = rec.obj
    if not obj.get("evidence_gap_id"):
        issues.append(Issue("EVIDENCE_GAP_MISSING_ID", rec.label, "EvidenceGap missing evidence_gap_id"))
    claim_ids = obj.get("claim_ids")
    if not isinstance(claim_ids, list) or not claim_ids:
        issues.append(Issue("EVIDENCE_GAP_MISSING_CLAIMS", rec.label, "EvidenceGap requires claim_ids"))
        return
    for claim_id in claim_ids:
        target = by_id.get(str(claim_id))
        if not target or target.record_type != "Claim":
            issues.append(Issue("EVIDENCE_GAP_CLAIM_NOT_FOUND", rec.label, f"claim not found: {claim_id}"))


def _validate_opportunity_case(rec: LoadedRecord, issues: list[Issue], by_id: dict[str, LoadedRecord]) -> None:
    obj = rec.obj
    case_status = obj.get("case_status")
    gate = obj.get("evidence_gate_state")
    signal_state = obj.get("signal_window_state")
    if case_status == "candidate":
        if gate not in CORROBORATED_GATE_STATES:
            issues.append(Issue("CANDIDATE_WITHOUT_CORROBORATED_EVIDENCE", rec.label, "candidate requires corroborated evidence_gate_state"))
        if signal_state == "not_ready_missing_primary_evidence":
            issues.append(Issue("CANDIDATE_WITH_MISSING_PRIMARY_EVIDENCE", rec.label, "candidate cannot have missing-primary-evidence signal state"))
        if not _has_claim_corroboration_ref(obj):
            issues.append(Issue("CANDIDATE_WITHOUT_CLAIM_CORROBORATION", rec.label, "candidate requires claim-level corroborating EvidenceItem refs"))
    _check_refs(rec, issues, by_id, "claim_ids", "Claim")
    _check_refs(rec, issues, by_id, "evidence_gap_ids", "EvidenceGap")
    for ref in obj.get("evidence_item_refs", []):
        if not isinstance(ref, dict):
            continue
        evidence_id = ref.get("evidence_item_id")
        target = by_id.get(str(evidence_id))
        if not target or target.record_type != "EvidenceItem":
            issues.append(Issue("OC_EVIDENCE_ITEM_REF_NOT_FOUND", rec.label, f"EvidenceItem ref not found: {evidence_id}"))
        if ref.get("used_for") == "connector_capability_evidence" and ref.get("corroborates_claim_ids"):
            issues.append(Issue("CONNECTOR_CAPABILITY_USED_AS_CLAIM_EVIDENCE", rec.label, "connector capability evidence cannot corroborate claims"))


def _validate_signal_window(rec: LoadedRecord, issues: list[Issue], by_id: dict[str, LoadedRecord]) -> None:
    obj = rec.obj
    if obj.get("window_label") == "live":
        issues.append(Issue("LIVE_WINDOW_FORBIDDEN_IN_REPAIR_LANE", rec.label, "live window_label is forbidden in repair lane"))
    ref = obj.get("opportunity_case_ref")
    if isinstance(ref, dict):
        gate = ref.get("evidence_gate_state")
        case_status = ref.get("case_status")
        if case_status == "candidate" and gate not in CORROBORATED_GATE_STATES:
            issues.append(Issue("SIGNAL_WINDOW_CANDIDATE_WITHOUT_CORROBORATION", rec.label, "candidate SignalWindow ref requires corroborated evidence gate"))
    oc_id = obj.get("opportunity_case_id")
    if oc_id and oc_id in by_id and by_id[oc_id].record_type == "OpportunityCase":
        oc = by_id[oc_id].obj
        if oc.get("case_status") == "candidate" and oc.get("evidence_gate_state") not in CORROBORATED_GATE_STATES:
            issues.append(Issue("SIGNAL_WINDOW_LINKS_FAKE_CANDIDATE", rec.label, "SignalWindow links to uncorroborated candidate"))


def _validate_review_window(rec: LoadedRecord, issues: list[Issue], by_id: dict[str, LoadedRecord]) -> None:
    """ReviewWindow is a research-only semantic narrowing of SignalWindow.

    It represents disclosure-calendar / evidence-freshness review windows,
    not timing signals or trade recommendations.
    """
    obj = rec.obj
    # No live window label in review windows
    if obj.get("window_label") == "live":
        issues.append(Issue("LIVE_WINDOW_FORBIDDEN_IN_REPAIR_LANE", rec.label, "live window_label is forbidden in review window"))
    # ReviewWindow must have a review_trigger describing what disclosure/event triggered it
    if not obj.get("review_trigger"):
        issues.append(Issue("REVIEW_WINDOW_MISSING_TRIGGER", rec.label, "ReviewWindow requires review_trigger (disclosure calendar, earnings date, policy deadline, evidence refresh)"))
    # ReviewWindow must NOT have timing_for fields
    if obj.get("timing_for") or obj.get("expected_action"):
        issues.append(Issue("REVIEW_WINDOW_TIMING_FORBIDDEN", rec.label, "ReviewWindow must not contain timing_for or expected_action"))
    # Link validation against OpportunityCase
    oc_id = obj.get("opportunity_case_id")
    if oc_id and oc_id in by_id and by_id[oc_id].record_type == "OpportunityCase":
        oc = by_id[oc_id].obj
        if oc.get("case_status") == "candidate" and oc.get("evidence_gate_state") not in CORROBORATED_GATE_STATES:
            issues.append(Issue("REVIEW_WINDOW_LINKS_FAKE_CANDIDATE", rec.label, "ReviewWindow links to uncorroborated candidate"))
    ref = obj.get("opportunity_case_ref")
    if isinstance(ref, dict):
        gate = ref.get("evidence_gate_state")
        case_status = ref.get("case_status")
        if case_status == "candidate" and gate not in CORROBORATED_GATE_STATES:
            issues.append(Issue("REVIEW_WINDOW_CANDIDATE_WITHOUT_CORROBORATION", rec.label, "candidate ReviewWindow ref requires corroborated evidence gate"))


def _has_claim_corroboration_ref(obj: dict[str, Any]) -> bool:
    for ref in obj.get("evidence_item_refs", []):
        if not isinstance(ref, dict):
            continue
        if ref.get("used_for") in CLAIM_EVIDENCE_USES and ref.get("corroborates_claim_ids"):
            return True
    return False


def _check_refs(
    rec: LoadedRecord,
    issues: list[Issue],
    by_id: dict[str, LoadedRecord],
    field: str,
    expected_type: str,
) -> None:
    refs = rec.obj.get(field)
    if refs is None:
        return
    if not isinstance(refs, list):
        issues.append(Issue("BAD_REFERENCE_FIELD", f"{rec.label}.{field}", f"{field} must be list"))
        return
    for item in refs:
        target = by_id.get(str(item))
        if not target or target.record_type != expected_type:
            issues.append(Issue("REFERENCE_NOT_FOUND", f"{rec.label}.{field}", f"{expected_type} ref not found: {item}"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finbot collection-level validator v1.3")
    parser.add_argument("paths", nargs="+", help="JSON/JSONL files or directories")
    parser.add_argument("--repo-root", default=".", help="repository root for resolving artifact paths")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    records = load_collection([Path(p) for p in args.paths])
    result = validate_collection(records, repo_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
