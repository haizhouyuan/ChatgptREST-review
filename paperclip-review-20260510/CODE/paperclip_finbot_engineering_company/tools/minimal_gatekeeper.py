#!/usr/bin/env python3
"""Finbot v2.1 minimal hard-fail gatekeeper.

This is intentionally narrower than the full validator_rules_v1_2 suite. It
blocks the failure modes Pro identified as most dangerous before any connector,
material-recovery, claim-extraction, or replay artifact can be consumed by later
steps.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import sys
from pathlib import Path
from typing import Any


SOURCE_ROUTE_RE = re.compile(r"^SR-[A-Z]{2,4}-[A-Z0-9]{2,16}$")
SOURCE_ACCOUNT_RE = re.compile(r"^SA-[ABCDE]-[A-Z0-9]{3,24}$")
CONTENT_ITEM_RE = re.compile(r"^CI-[A-Z0-9]+-[A-Z0-9]+-[0-9]{6,8}-[A-Z0-9]{1,8}$")
EVIDENCE_ITEM_RE = re.compile(r"^EI-[A-Z0-9]+-[0-9]{8}-[A-Z0-9]{1,16}$")
CLAIM_RE = re.compile(r"^CLM-[A-Z0-9]+-[0-9]{8}-[A-Z0-9]{1,8}$")
FETCH_ATTEMPT_RE = re.compile(r"^FA-[A-Z0-9]+-[0-9]{8}-[A-Z0-9]{1,8}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

FORBIDDEN_LANGUAGE = [
    "buy",
    "sell",
    "long",
    "short",
    "position",
    "add",
    "reduce",
    "exit",
    "target price",
    "overweight",
    "underweight",
    "market order",
    "limit order",
    "stop-loss",
    "take-profit",
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
]

EVIDENCE_REQUIRED = ["evidence_item_id", "source_route_id", "raw_path", "sha256", "published_at", "available_at"]


@dataclass(frozen=True)
class GateIssue:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


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


def parse_time(value: Any) -> datetime | None:
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


def iter_text_values(value: Any, path: str = "$") -> list[tuple[str, str]]:
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


def contains_forbidden_language(text: str) -> str | None:
    lowered = text.lower()
    for term in FORBIDDEN_LANGUAGE:
        if term in lowered:
            return term
    return None


def _check_pattern(issues: list[GateIssue], value: Any, pattern: re.Pattern[str], code: str, path: str, message: str) -> None:
    if not isinstance(value, str) or not pattern.match(value):
        issues.append(GateIssue(code, path, message))


def validate_record(record: dict[str, Any], *, now: datetime | None = None, path: str = "$") -> list[GateIssue]:
    now = now or datetime.now(timezone.utc)
    issues: list[GateIssue] = []
    record_type = record.get("record_type") or record.get("type")

    for text_path, text in iter_text_values(record, path):
        term = contains_forbidden_language(text)
        if term:
            issues.append(GateIssue("FORBIDDEN_TRADING_LANGUAGE", text_path, f"forbidden term '{term}' found"))

    if record_type == "EvidenceItem":
        for field in EVIDENCE_REQUIRED:
            if not record.get(field):
                issues.append(GateIssue("EV_MISSING_REQUIRED", f"{path}.{field}", f"EvidenceItem missing required field '{field}'"))

        _check_pattern(
            issues,
            record.get("evidence_item_id"),
            EVIDENCE_ITEM_RE,
            "ID_NAMESPACE_MISMATCH",
            f"{path}.evidence_item_id",
            "EvidenceItem ID must use EI-* namespace",
        )
        _check_pattern(
            issues,
            record.get("source_route_id"),
            SOURCE_ROUTE_RE,
            "ID_NAMESPACE_MISMATCH",
            f"{path}.source_route_id",
            "EvidenceItem source_route_id must use SR-* SourceRoute namespace",
        )
        if record.get("source_account_id") or str(record.get("source_route_id", "")).startswith("SA-") or str(record.get("source_id", "")).startswith("SA-"):
            issues.append(GateIssue("KOL_AS_EVIDENCE", path, "SourceAccount/KOL material cannot be emitted as EvidenceItem"))
        if record.get("source_type") == "D" or str(record.get("source_id", "")).startswith("SRC-D-"):
            issues.append(GateIssue("KOL_AS_EVIDENCE", path, "D-tier/KOL material cannot be emitted as EvidenceItem"))
        if record.get("status") == "blocked" or record.get("fetch_status") == "blocked" or record.get("block_reason"):
            issues.append(GateIssue("BLOCKED_FETCH_AS_EVIDENCE", path, "blocked fetch must be FetchAttempt or EvidenceGap, not EvidenceItem"))
        if record.get("sha256") and not SHA256_RE.match(str(record["sha256"])):
            issues.append(GateIssue("EV_BAD_SHA256", f"{path}.sha256", "sha256 must be 64 hex characters"))

    if record_type == "ContentItem":
        _check_pattern(
            issues,
            record.get("content_item_id"),
            CONTENT_ITEM_RE,
            "ID_NAMESPACE_MISMATCH",
            f"{path}.content_item_id",
            "ContentItem ID must use CI-* namespace",
        )
        if record.get("source_account_id"):
            _check_pattern(
                issues,
                record.get("source_account_id"),
                SOURCE_ACCOUNT_RE,
                "ID_NAMESPACE_MISMATCH",
                f"{path}.source_account_id",
                "source_account_id must use SA-* SourceAccount namespace",
            )

    if record_type == "FetchAttempt":
        if record.get("fetch_attempt_id"):
            _check_pattern(
                issues,
                record.get("fetch_attempt_id"),
                FETCH_ATTEMPT_RE,
                "ID_NAMESPACE_MISMATCH",
                f"{path}.fetch_attempt_id",
                "FetchAttempt ID must use FA-* namespace",
            )
        if record.get("status") == "blocked" and not record.get("block_reason"):
            issues.append(GateIssue("BLOCKED_FETCH_MISSING_REASON", path, "blocked FetchAttempt must carry block_reason"))

    if record_type == "Claim":
        _check_pattern(
            issues,
            record.get("claim_id"),
            CLAIM_RE,
            "ID_NAMESPACE_MISMATCH",
            f"{path}.claim_id",
            "Claim ID must use CLM-* namespace",
        )

    for field in ["published_at", "available_at", "fetched_at"]:
        if field in record:
            dt = parse_time(record.get(field))
            if dt is None:
                issues.append(GateIssue("BAD_TIMESTAMP", f"{path}.{field}", f"{field} must be ISO timestamp"))
            elif dt > now:
                issues.append(GateIssue("FUTURE_DATED_EVIDENCE", f"{path}.{field}", f"{field} is in the future"))

    return issues


def validate_records(records: list[dict[str, Any]], *, now: datetime | None = None) -> dict[str, Any]:
    issues: list[GateIssue] = []
    for idx, record in enumerate(records):
        issues.extend(validate_record(record, now=now, path=f"$[{idx}]"))
    return {
        "status": "pass" if not issues else "blocked",
        "issue_count": len(issues),
        "issues": [issue.to_dict() for issue in issues],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Finbot v2.1 minimal hard-fail gatekeeper")
    parser.add_argument("paths", nargs="+", help="JSON or JSONL artifact paths to validate")
    args = parser.parse_args(argv)

    all_issues: list[dict[str, Any]] = []
    for raw_path in args.paths:
        path = Path(raw_path)
        records = load_records(path)
        result = validate_records(records)
        if result["status"] != "pass":
            all_issues.append({"path": str(path), "result": result})

    output = {
        "status": "pass" if not all_issues else "blocked",
        "checked_files": len(args.paths),
        "failures": all_issues,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
