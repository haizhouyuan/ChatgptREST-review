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
    cases = {case["ticker"]: case for case in read_json(RESEARCH_ROOT / "69_alpha_quality_casebook.json")["cases"]}
    alert_specs = [
        ("YELP", "evidence_refresh", "Authority complaint/regulatory records remain missing for the customer-risk angle."),
        ("TXN", "catalyst", "MoFCOM and geographic exposure evidence are required before policy catalyst can be upgraded."),
        ("MU", "stale_evidence", "HBM, inventory and gross-margin commentary must be refreshed from latest filings/transcripts."),
    ]
    alerts = []
    for idx, (ticker, alert_type, reason) in enumerate(alert_specs, start=1):
        case = cases[ticker]
        alerts.append({
            "alert_id": f"alert-cap-v1-{idx:03d}",
            "case_id": case["case_id"],
            "ticker": ticker,
            "alert_scope": "human_review_alert",
            "alert_type": alert_type,
            "trigger_reason": reason,
            "evidence_ids": case["primary_evidence_ids"],
            "human_review_question": case["alpha_quality_gate"]["risk_reward_research_question"],
            "next_action": case["next_evidence_action"],
            "forbidden_use": ["production watchlist", "trade signal", "broker action", "position sizing", "investment advice"],
            "status": "needs_human_review",
        })
    payload = {
        "schema": "finbot.alert_monitoring_prototype.v1",
        "generated_at": NOW,
        "status": "human_review_alerts_only",
        "alerts": alerts,
    }
    (docs_root / "09_alert_monitoring_prototype.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = [
        "# 09 Alert Monitoring Prototype",
        "",
        f"Generated: `{NOW}`",
        "",
        "All alerts are human-review alerts. No production watchlist, trade signal, broker action, position sizing or investment advice.",
        "",
        "| Alert | Ticker | Type | Reason | Human Review Question |",
        "| --- | --- | --- | --- | --- |",
    ]
    for alert in alerts:
        md.append(f"| {alert['alert_id']} | {alert['ticker']} | {alert['alert_type']} | {alert['trigger_reason']} | {alert['human_review_question']} |")
    (docs_root / "09_alert_monitoring_prototype.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "alerts": len(alerts)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
