#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO.parent
RESEARCH_ROOT = PROJECT / "docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp"
DEFAULT_DOCS = PROJECT / "docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform"
NOW = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
GUARDED = ["Readwise", "Zotero", "Alpaca watch-only", "Daloopa", "Quartr", "Binance risk context"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pass_result(check_id: str, source_id: str, status: str, proof_level: str, artifact: Path, summary: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "source_id": source_id,
        "status": status,
        "proof_level": proof_level,
        "read_only": True,
        "secret_boundary": "no secrets read or emitted",
        "artifact_path": str(artifact),
        "summary": summary,
        "rollback_disable_note": "delete generated artifacts; no native config was changed",
    }


def run_smokes(docs_root: Path) -> dict[str, Any]:
    artifact_root = REPO / "artifacts/capability_platform_v1"
    artifact_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for ticker in ["TXN", "MU"]:
        fact_files = sorted((RESEARCH_ROOT / "primary_evidence/sec_companyfacts").glob(f"{ticker}_CIK*_companyfacts.json"))
        if not fact_files:
            raise RuntimeError(f"missing SEC companyfacts artifact for {ticker}")
        data = read_json(fact_files[0])
        if not data.get("facts"):
            raise RuntimeError(f"SEC companyfacts lacks facts for {ticker}")
        results.append(pass_result(
            f"sec_companyfacts_{ticker.lower()}",
            "sec_companyfacts",
            "pass",
            "workflow_verified",
            fact_files[0],
            f"Parsed SEC companyfacts for {ticker}; sha256={sha256(fact_files[0])[:16]}",
        ))

        sub_files = sorted((RESEARCH_ROOT / "primary_evidence/sec_submissions").glob(f"{ticker}_CIK*_submissions.json"))
        if not sub_files:
            raise RuntimeError(f"missing SEC submissions artifact for {ticker}")
        sub = read_json(sub_files[0])
        if not sub.get("filings", {}).get("recent"):
            raise RuntimeError(f"SEC submissions lacks recent filings for {ticker}")
        results.append(pass_result(
            f"sec_submissions_{ticker.lower()}",
            "sec_submissions",
            "pass",
            "workflow_verified",
            sub_files[0],
            f"Parsed SEC submissions for {ticker}; sha256={sha256(sub_files[0])[:16]}",
        ))

    local_docs = [
        PROJECT / "AGENTS.md",
        REPO / "README.md",
        Path("/vol1/maint/docs/个人投研助理方法.md"),
        Path("/vol1/maint/docs/profinbot批判.md"),
        RESEARCH_ROOT / "69_alpha_quality_casebook.json",
    ]
    for path in local_docs:
        if not path.exists():
            raise RuntimeError(f"missing local doc proof: {path}")
    local_manifest = artifact_root / "local_docs_manifest.json"
    local_manifest.write_text(json.dumps([
        {"path": str(path), "sha256": sha256(path), "size_bytes": path.stat().st_size}
        for path in local_docs
    ], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    results.append(pass_result(
        "local_docs_manifest",
        "google_drive_local_docs",
        "pass",
        "workflow_verified",
        local_manifest,
        "Verified local docs and Finbot alpha package by path, size and sha256.",
    ))

    filing_files = sorted((RESEARCH_ROOT / "primary_evidence/sec_filings").glob("TXN_10-Q_*.htm"))
    if not filing_files:
        raise RuntimeError("missing TXN local SEC filing HTML")
    html = filing_files[0].read_text(encoding="utf-8", errors="ignore")
    extracted_all = re.sub(r"<[^>]+>", " ", html)
    extracted_all = re.sub(r"\s+", " ", extracted_all).strip()
    extracted = extracted_all[:5000]
    extraction_path = artifact_root / "web_extraction_local_sec_filing_excerpt.txt"
    extraction_path.write_text(extracted + "\n", encoding="utf-8")
    if not any(token in extracted_all.upper() for token in ["TEXAS INSTRUMENTS", "10-Q", "0000097476", "TXN-20260331"]):
        raise RuntimeError("local HTML extraction did not capture expected SEC filing text")
    results.append(pass_result(
        "web_extraction_local_sec_filing",
        "web_extraction_local_html",
        "pass",
        "workflow_verified",
        extraction_path,
        "Extracted text from captured SEC filing HTML; no browser provider or quarantined search used.",
    ))

    price_fixture = REPO / "fixtures/capability_platform/local_price_context_fixture.csv"
    with price_fixture.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) < 2 or any(row.get("fixture_only") != "true" for row in rows):
        raise RuntimeError("local price fixture is malformed")
    results.append(pass_result(
        "local_price_fixture_parse",
        "local_price_fixture",
        "pass",
        "workflow_verified",
        price_fixture,
        "Parsed offline local price context fixture; explicitly not live market data.",
    ))

    for connector in GUARDED:
        results.append({
            "check_id": f"guarded_{connector.lower().replace(' ', '_').replace('-', '_')}",
            "source_id": connector,
            "status": "blocked_candidate",
            "proof_level": "not_verified",
            "read_only": True,
            "secret_boundary": "not touched; no secrets inspected",
            "artifact_path": str(docs_root / "02_data_source_readiness_matrix.json"),
            "summary": "Connector remains candidate_to_enable; no fake workflow verification.",
            "rollback_disable_note": "no native config changed",
        })

    report = {
        "schema": "finbot.capability_connector_smoke_results.v1",
        "generated_at": NOW,
        "status": "pass",
        "results": results,
        "notes": [
            "Endpoint-only checks are not counted as workflow verification.",
            "Guarded connectors remain blocked/candidate unless Governance approves a current-lane read-only workflow smoke.",
            "No native runtime/MCP/skill config was changed.",
        ],
    }
    out = artifact_root / "connector_smoke_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (docs_root / "03_connector_smoke_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-root", default=str(DEFAULT_DOCS))
    args = parser.parse_args()
    report = run_smokes(Path(args.docs_root))
    print(json.dumps({"status": report["status"], "checks": len(report["results"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
