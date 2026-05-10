#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO.parent
RESEARCH_ROOT = PROJECT / "docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp"
DEFAULT_DOCS = PROJECT / "docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform"
NOW = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-root", default=str(DEFAULT_DOCS))
    args = parser.parse_args()
    docs_root = Path(args.docs_root)
    casebook = read_json(RESEARCH_ROOT / "69_alpha_quality_casebook.json")
    by_ticker = {case["ticker"]: case for case in casebook["cases"]}
    selected = ["YELP", "NKE"]
    entries = []
    scenarios = {
        "YELP": {
            "method": "local fixture relative multiple and margin-quality scenario; no live market data",
            "bear": {"metric": "ev_revenue_multiple_context", "range": [1.0, 1.3]},
            "base": {"metric": "ev_revenue_multiple_context", "range": [1.3, 1.8]},
            "bull": {"metric": "ev_revenue_multiple_context", "range": [1.8, 2.3]},
            "assumptions": ["customer-risk evidence remains unresolved", "profitability evidence is primary-bound", "no live market price workflow verified"],
        },
        "NKE": {
            "method": "brand-recovery operating margin scenario using research-only range buckets",
            "bear": {"metric": "operating_margin_recovery_context", "range": [8.0, 10.0]},
            "base": {"metric": "operating_margin_recovery_context", "range": [10.0, 12.5]},
            "bull": {"metric": "operating_margin_recovery_context", "range": [12.5, 15.0]},
            "assumptions": ["channel cleanup is not yet proven", "inventory and margin evidence must be refreshed", "range is not a per-share output"],
        },
    }
    for ticker in selected:
        case = by_ticker[ticker]
        scenario = scenarios[ticker]
        entries.append({
            "case_id": case["case_id"],
            "ticker": ticker,
            "range_type": "research_estimate_range",
            "research_only": True,
            "current_evidence_base": case["primary_evidence_ids"],
            "method": scenario["method"],
            "assumptions": scenario["assumptions"],
            "bear": scenario["bear"],
            "base": scenario["base"],
            "bull": scenario["bull"],
            "confidence": "low_to_medium",
            "missing_data": [case["next_evidence_action"], "live market data remains blocked unless watch-only connector is workflow verified"],
            "invalidation": [case["alpha_quality_gate"]["risk_reward_research_question"], "new primary evidence contradicts the range assumptions"],
            "evidence_ids": case["primary_evidence_ids"],
            "no_advice_label": "research estimate range only; not a target price, recommendation, trade signal, broker action or position-size input",
            "why_this_is_not_target_price": "The output is a scenario range for research context and cannot be converted into an action without human review and Governance-approved data workflows.",
        })
    payload = {
        "schema": "finbot.valuation_range_research_prototype.v1",
        "generated_at": NOW,
        "status": "research_only_pass",
        "live_market_data_status": "blocked_or_fixture_only",
        "entries": entries,
    }
    (docs_root / "08_valuation_range_research_prototype.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = [
        "# 08 Valuation Range Research Prototype",
        "",
        f"Generated: `{NOW}`",
        "",
        "Research-only scenario ranges. They are not target prices, recommendations, broker actions, trade signals or position-size inputs.",
        "",
        "| Ticker | Method | Bear | Base | Bull | Missing Data |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in entries:
        md.append(f"| {entry['ticker']} | {entry['method']} | {entry['bear']['range']} | {entry['base']['range']} | {entry['bull']['range']} | {'; '.join(entry['missing_data'])} |")
    (docs_root / "08_valuation_range_research_prototype.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "entries": len(entries)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
