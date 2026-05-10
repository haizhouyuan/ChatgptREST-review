#!/usr/bin/env python3
"""Finbot v2.1 executable validator rules_v1_2.

This module implements all 14 Pro-required hard-fail rules from the Day4 contract.
Each rule either hard-fails (issues are collected) or passes. The CLI reports
overall pass/blocked status.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Patterns — frozen namespaces from SOURCE_IDENTITY_MODEL_v1_3.md
# ---------------------------------------------------------------------------
SOURCE_ROUTE_RE = re.compile(r"^SR-[A-Z]{2}-[A-Z0-9]{2,16}$")
SOURCE_ACCOUNT_RE = re.compile(r"^SA-[A-Z]-[A-Z0-9]{2,24}$")
CONTENT_ITEM_RE = re.compile(r"^CI-[A-Z0-9]+-[A-Z0-9]+-[0-9]{6,8}-[A-Z0-9]{1,8}$")
EVIDENCE_ITEM_RE = re.compile(r"^EI-[A-Z0-9]+-[0-9]{8}-[A-Z0-9]{1,16}$")
CLAIM_RE = re.compile(r"^CLM-[A-Z0-9]+-[0-9]{8}-[A-Z0-9]{1,8}$")
FETCH_ATTEMPT_RE = re.compile(r"^FA-[A-Z0-9]+-[0-9]{8}-[A-Z0-9]{1,8}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

ALLOWED_WINDOW_LABELS = {"20D", "60D", "120D", "live", None}
ALLOWED_SIGNAL_WINDOW_STATES = {
    "not_ready_missing_primary_evidence",
    "early_research_window",
    "watch_for_primary_catalyst",
    "technical_context_review",
    "deep_research_review_alert",
}
ALLOWED_ALERT_TYPES = {"research_review_alert", "deep_research_review_alert", "technical_context_review"}
FORBIDDEN_ALERT_TYPES = {"buy_signal", "sell_signal", "trade_signal", "position_signal"}
FORBIDDEN_LANGUAGE = [
    "buy", "sell", "long", "short", "position", "trade",
    "target price", "target-price", "overweight", "underweight",
    "market order", "limit order", "stop-loss", "stop loss",
    "take-profit", "take profit", "add", "reduce", "exit",
    "买入", "卖出", "做多", "做空", "加仓", "减仓",
    "清仓", "仓位", "目标价", "止损", "止盈", "下单",
]


# ---------------------------------------------------------------------------
# Issue model
# ---------------------------------------------------------------------------
@dataclass
class Issue:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------
def load_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise ValueError(f"unsupported JSON root type in {path}: {type(data).__name__}")


def parse_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Text scanning helpers
# ---------------------------------------------------------------------------
def iter_text_values(
    value: Any, path: str = "$"
) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, str):
        found.append((path, value))
    elif isinstance(value, dict):
        for key, child in value.items():
            found.extend(iter_text_values(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            found.extend(iter_text_values(child, f"{path}[{idx}]"))
    return found


def contains_forbidden_language(text: str) -> Optional[str]:
    lowered = text.lower()
    for term in FORBIDDEN_LANGUAGE:
        if term in lowered:
            return term
    return None


# ---------------------------------------------------------------------------
# Per-record validators
# ---------------------------------------------------------------------------

def _check_pattern(
    issues: list[Issue],
    value: Any,
    pattern: re.Pattern[str],
    code: str,
    path: str,
    message: str,
) -> None:
    if not isinstance(value, str) or not pattern.match(value):
        issues.append(Issue(code, path, message))


def _check_future_date(
    issues: list[Issue],
    record: dict[str, Any],
    field: str,
    path: str,
    now: datetime,
) -> None:
    val = record.get(field)
    if val is None:
        return
    dt = parse_time(val)
    if dt is None:
        issues.append(Issue("BAD_TIMESTAMP", f"{path}.{field}", f"{field} must be ISO timestamp"))
    elif dt > now:
        issues.append(Issue("FUTURE_DATED_EVIDENCE", f"{path}.{field}", f"{field} is in the future"))


def validate_record(
    record: dict[str, Any],
    *,
    now: Optional[datetime] = None,
    path: str = "$",
) -> list[Issue]:
    now = now or datetime.now(timezone.utc)
    issues: list[Issue] = []
    record_type = record.get("record_type") or record.get("type")

    # --- FORBIDDEN TRADING LANGUAGE (all record types) -----------------
    for text_path, text in iter_text_values(record, path):
        term = contains_forbidden_language(text)
        if term:
            issues.append(Issue(
                "FORBIDDEN_TRADING_LANGUAGE",
                text_path,
                f"forbidden term '{term}' found",
            ))

    # --- FUTURE DATED EVIDENCE (timestamp fields) --------------------
    for fld in ["published_at", "available_at", "fetched_at"]:
        _check_future_date(issues, record, fld, path, now)

    # --- EvidenceItem ------------------------------------------------
    if record_type == "EvidenceItem":
        _validate_evidence_item(record, issues, path, now)

    # --- FetchAttempt -----------------------------------------------
    if record_type == "FetchAttempt":
        _validate_fetch_attempt(record, issues, path)

    # --- ContentItem -------------------------------------------------
    if record_type == "ContentItem":
        _validate_content_item(record, issues, path)

    # --- Claim -------------------------------------------------------
    if record_type == "Claim":
        _validate_claim(record, issues, path)

    # --- OpportunityCase --------------------------------------------
    if record_type in ("OpportunityCase", "OC"):
        _validate_opportunity_case(record, issues, path)

    # --- SignalWindow -----------------------------------------------
    if record_type == "SignalWindow":
        _validate_signal_window(record, issues, path)

    # --- SignalRule -------------------------------------------------
    if record_type == "SignalRule":
        _validate_signal_rule(record, issues, path)

    # --- AlertCondition ---------------------------------------------
    if record_type == "AlertCondition":
        _validate_alert_condition(record, issues, path)

    return issues


def _validate_evidence_item(
    record: dict[str, Any], issues: list[Issue], path: str, now: datetime
) -> None:
    # 1. EV_BLOCKED_EVIDENCE_PSEUDO: blocked fetch cannot be EvidenceItem
    status = record.get("status") or record.get("fetch_status")
    block_reason = record.get("block_reason")
    if status == "blocked" or block_reason:
        issues.append(Issue(
            "EV_BLOCKED_EVIDENCE_PSEUDO",
            path,
            "blocked fetch recorded as EvidenceItem; must be FetchAttempt",
        ))

    # fetched_at, checksum, raw_path — all must be present for a real EvidenceItem
    has_fetched = bool(record.get("fetched_at"))
    has_checksum = bool(record.get("checksum") or record.get("sha256"))
    has_raw_path = bool(record.get("raw_path"))
    if not has_fetched or not has_checksum or not has_raw_path:
        issues.append(Issue(
            "EV_BLOCKED_EVIDENCE_PSEUDO",
            path,
            "EvidenceItem missing fetched_at or checksum or raw_path — pseudo-EvidenceItem from failed fetch",
        ))

    # 2. KOL_CLAIM_NOT_EVIDENCE_ITEM: SA-D / D-tier / SourceAccount cannot emit EvidenceItem
    source_account_id = record.get("source_account_id", "") or ""
    source_id = record.get("source_id", "") or ""
    source_type = record.get("source_type", "") or ""
    tier = record.get("tier") or record.get("authority_level") or ""

    is_kol = (
        str(source_account_id).startswith("SA-D-")
        or str(source_id).startswith("SA-D-")
        or str(source_type).lower() == "d"
        or str(tier).upper() == "D"
        or source_account_id == "SA-D-FUZONG"
    )
    if is_kol:
        issues.append(Issue(
            "KOL_CLAIM_NOT_EVIDENCE_ITEM",
            path,
            "D-tier/SourceAccount material cannot be emitted as EvidenceItem",
        ))

    # 3. EV_MISSING_RAW_OR_SHA
    for fld in ["raw_path", "sha256", "published_at", "available_at"]:
        if not record.get(fld):
            issues.append(Issue(
                "EV_MISSING_RAW_OR_SHA",
                f"{path}.{fld}",
                f"EvidenceItem missing required field '{fld}'",
            ))

    # 4. EV_BAD_SHA256
    sha = record.get("sha256") or record.get("checksum") or ""
    if sha and not SHA256_RE.match(str(sha)):
        issues.append(Issue(
            "EV_BAD_SHA256",
            f"{path}.sha256",
            "sha256 must be 64 hex characters",
        ))

    # Namespace checks on IDs
    if record.get("evidence_item_id"):
        _check_pattern(
            issues, record["evidence_item_id"], EVIDENCE_ITEM_RE,
            "SOURCE_NAMESPACE_MISMATCH", f"{path}.evidence_item_id",
            "EvidenceItem ID must use EI-* namespace",
        )
    if record.get("source_route_id"):
        _check_pattern(
            issues, record["source_route_id"], SOURCE_ROUTE_RE,
            "SOURCE_NAMESPACE_MISMATCH", f"{path}.source_route_id",
            "source_route_id must use SR-* SourceRoute namespace",
        )


def _validate_fetch_attempt(
    record: dict[str, Any], issues: list[Issue], path: str
) -> None:
    if record.get("fetch_attempt_id"):
        _check_pattern(
            issues, record["fetch_attempt_id"], FETCH_ATTEMPT_RE,
            "SOURCE_NAMESPACE_MISMATCH", f"{path}.fetch_attempt_id",
            "FetchAttempt ID must use FA-* namespace",
        )
    if record.get("source_route_id"):
        _check_pattern(
            issues, record["source_route_id"], SOURCE_ROUTE_RE,
            "SOURCE_NAMESPACE_MISMATCH", f"{path}.source_route_id",
            "FetchAttempt source_route_id must use SR-* namespace",
        )
    # blocked FetchAttempt must have block_reason
    status = record.get("status")
    if status == "blocked" and not record.get("block_reason"):
        issues.append(Issue(
            "BLOCKED_FETCH_MISSING_REASON",
            path,
            "blocked FetchAttempt must carry block_reason",
        ))


def _validate_content_item(
    record: dict[str, Any], issues: list[Issue], path: str
) -> None:
    if record.get("content_item_id"):
        _check_pattern(
            issues, record["content_item_id"], CONTENT_ITEM_RE,
            "SOURCE_NAMESPACE_MISMATCH", f"{path}.content_item_id",
            "ContentItem ID must use CI-* namespace",
        )
    if record.get("source_account_id"):
        _check_pattern(
            issues, record["source_account_id"], SOURCE_ACCOUNT_RE,
            "SOURCE_NAMESPACE_MISMATCH", f"{path}.source_account_id",
            "source_account_id must use SA-* SourceAccount namespace",
        )


def _validate_claim(
    record: dict[str, Any], issues: list[Issue], path: str
) -> None:
    # Namespace check
    if record.get("claim_id"):
        _check_pattern(
            issues, record["claim_id"], CLAIM_RE,
            "SOURCE_NAMESPACE_MISMATCH", f"{path}.claim_id",
            "Claim ID must use CLM-* namespace",
        )

    # CLAIM_MISSING_SOURCE_TRACE: requires content_item_id,
    # source_account_id or source_route_id, published_at, available_at, source_span
    missing: list[str] = []
    if not record.get("content_item_id"):
        missing.append("content_item_id")
    has_source = bool(record.get("source_account_id") or record.get("source_route_id"))
    if not has_source:
        missing.append("source_account_id or source_route_id")
    for fld in ["published_at", "available_at", "source_span"]:
        if not record.get(fld):
            missing.append(fld)

    if missing:
        issues.append(Issue(
            "CLAIM_MISSING_SOURCE_TRACE",
            path,
            f"Claim missing required source-trace fields: {', '.join(missing)}",
        ))

    # KOL_CLAIM_WITHOUT_EVIDENCE_GAP: KOL claim must have evidence_gap_ids or evidence_status
    source_account_id = str(record.get("source_account_id", "") or "")
    tier = str(record.get("tier") or record.get("authority_level") or "")
    is_kol = source_account_id.startswith("SA-D-") or tier.upper() == "D"
    if is_kol:
        has_gap = bool(record.get("evidence_gap_ids"))
        has_status = bool(record.get("evidence_status"))
        if not has_gap and not has_status:
            issues.append(Issue(
                "KOL_CLAIM_WITHOUT_EVIDENCE_GAP",
                path,
                "KOL claim must have evidence_gap_ids or evidence_status explaining official corroboration need",
            ))


def _validate_opportunity_case(
    record: dict[str, Any], issues: list[Issue], path: str
) -> None:
    # D_ONLY_DEEP_REVIEW_FORBIDDEN: evidence_gate_state=D_only + deep_research_review
    evidence_gate = record.get("evidence_gate_state") or record.get("gate_state") or ""
    sw_state = record.get("signal_window_state") or ""

    if str(evidence_gate).lower() == "d_only":
        if sw_state == "deep_research_review_alert":
            issues.append(Issue(
                "D_ONLY_DEEP_REVIEW_FORBIDDEN",
                path,
                "D-only case cannot enter deep_research_review_alert",
            ))
        # Also check window_label — D-only cases shouldn't enter timing windows
        wl = record.get("window_label")
        if wl and wl not in ALLOWED_WINDOW_LABELS:
            issues.append(Issue(
                "BAD_WINDOW_LABEL",
                f"{path}.window_label",
                f"window_label '{wl}' not in allowed set {ALLOWED_WINDOW_LABELS}",
            ))

    # BAD_WINDOW_LABEL
    wl = record.get("window_label")
    if wl is not None and wl not in ALLOWED_WINDOW_LABELS:
        issues.append(Issue(
            "BAD_WINDOW_LABEL",
            f"{path}.window_label",
            f"window_label '{wl}' not in allowed set {sorted(str(x) for x in ALLOWED_WINDOW_LABELS)}",
        ))

    # BAD_SIGNAL_WINDOW_STATE
    sws = record.get("signal_window_state")
    if sws and sws not in ALLOWED_SIGNAL_WINDOW_STATES:
        issues.append(Issue(
            "BAD_SIGNAL_WINDOW_STATE",
            f"{path}.signal_window_state",
            f"signal_window_state '{sws}' not in allowed set",
        ))


def _validate_signal_window(
    record: dict[str, Any], issues: list[Issue], path: str
) -> None:
    # BAD_WINDOW_LABEL
    wl = record.get("window_label")
    if wl is not None and wl not in ALLOWED_WINDOW_LABELS:
        issues.append(Issue(
            "BAD_WINDOW_LABEL",
            f"{path}.window_label",
            f"window_label '{wl}' not in allowed set",
        ))

    # BAD_SIGNAL_WINDOW_STATE
    sws = record.get("signal_window_state")
    if sws and sws not in ALLOWED_SIGNAL_WINDOW_STATES:
        issues.append(Issue(
            "BAD_SIGNAL_WINDOW_STATE",
            f"{path}.signal_window_state",
            f"signal_window_state '{sws}' not in allowed set",
        ))

    # D_ONLY_DEEP_REVIEW_FORBIDDEN — SignalWindow from D-only case
    source_oc = record.get("opportunity_case_ref") or record.get("oc_ref") or {}
    if isinstance(source_oc, dict):
        eg = str(source_oc.get("evidence_gate_state") or source_oc.get("gate_state") or "")
        if eg.lower() == "d_only" and sws == "deep_research_review_alert":
            issues.append(Issue(
                "D_ONLY_DEEP_REVIEW_FORBIDDEN",
                path,
                "D-only case SignalWindow cannot use deep_research_review_alert",
            ))

    # SIGNAL_WINDOW_BUY_SIGNAL_FORBIDDEN
    at = record.get("alert_type")
    if at in FORBIDDEN_ALERT_TYPES:
        issues.append(Issue(
            "SIGNAL_WINDOW_BUY_SIGNAL_FORBIDDEN",
            f"{path}.alert_type",
            f"alert_type '{at}' is forbidden; use research_review_alert",
        ))


def _validate_signal_rule(
    record: dict[str, Any], issues: list[Issue], path: str
) -> None:
    # SIGNAL_WINDOW_BUY_SIGNAL_FORBIDDEN
    at = record.get("alert_type")
    if at in FORBIDDEN_ALERT_TYPES:
        issues.append(Issue(
            "SIGNAL_WINDOW_BUY_SIGNAL_FORBIDDEN",
            f"{path}.alert_type",
            f"alert_type '{at}' is forbidden",
        ))

    # BACKTEST_PIT_MISSING
    has_backtest_result = record.get("backtest_result") is not None
    backtest_validated = record.get("backtest_validated")
    not_backtest_safe = record.get("not_backtest_safe", False)

    if has_backtest_result:
        br = record["backtest_result"]
        # Must have point-in-time fields
        has_window_start = bool(br.get("backtest_window_start") or br.get("window_start"))
        has_window_end = bool(br.get("backtest_window_end") or br.get("window_end"))
        has_data_available = bool(br.get("data_available_at") or br.get("available_at"))
        if not (has_window_start and has_window_end) and not not_backtest_safe:
            issues.append(Issue(
                "BACKTEST_PIT_MISSING",
                f"{path}.backtest_result",
                "backtest_result missing point-in-time fields (backtest_window_start/end); mark not_backtest_safe=true if unavailable",
            ))
        if not has_data_available and not not_backtest_safe:
            issues.append(Issue(
                "BACKTEST_PIT_MISSING",
                f"{path}.backtest_result",
                "backtest_result missing data_available_at; mark not_backtest_safe=true if unavailable",
            ))
    elif backtest_validated is True and not has_backtest_result:
        issues.append(Issue(
            "BACKTEST_PIT_MISSING",
            path,
            "SignalRule claims backtest_validated=true but backtest_result is null",
        ))


def _validate_alert_condition(
    record: dict[str, Any], issues: list[Issue], path: str
) -> None:
    # SIGNAL_WINDOW_BUY_SIGNAL_FORBIDDEN
    at = record.get("alert_type")
    if at in FORBIDDEN_ALERT_TYPES:
        issues.append(Issue(
            "SIGNAL_WINDOW_BUY_SIGNAL_FORBIDDEN",
            f"{path}.alert_type",
            f"alert_type '{at}' is forbidden",
        ))


# ---------------------------------------------------------------------------
# Batch validation
# ---------------------------------------------------------------------------
def validate_records(
    records: list[dict[str, Any]], *, now: Optional[datetime] = None
) -> dict[str, Any]:
    all_issues: list[Issue] = []
    for idx, record in enumerate(records):
        all_issues.extend(validate_record(record, now=now, path=f"$[{idx}]"))
    return {
        "status": "pass" if not all_issues else "blocked",
        "issue_count": len(all_issues),
        "issues": [issue.to_dict() for issue in all_issues],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Finbot v2.1 executable validator — rules_v1_2"
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="JSON or JSONL artifact paths to validate",
    )
    args = parser.parse_args(argv)

    all_issues: list[dict[str, Any]] = []
    total_checked = 0

    for raw_path in args.paths:
        path = Path(raw_path)
        if not path.exists():
            print(
                json.dumps(
                    {"status": "blocked", "checked_files": 0, "issue_count": 1,
                     "issues": [{"code": "FILE_NOT_FOUND", "path": raw_path,
                                 "message": f"file not found: {raw_path}"}]},
                    ensure_ascii=False, indent=2,
                ),
                file=sys.stderr,
            )
            return 1

        records = load_records(path)
        total_checked += 1
        result = validate_records(records)
        if result["status"] != "pass":
            all_issues.append({"path": str(path), "result": result})

    output = {
        "status": "pass" if not all_issues else "blocked",
        "checked_files": total_checked,
        "issue_count": sum(len(f["result"]["issues"]) for f in all_issues),
        "issues": [
            {**iss, "file": f["path"]}
            for f in all_issues
            for iss in f["result"]["issues"]
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
