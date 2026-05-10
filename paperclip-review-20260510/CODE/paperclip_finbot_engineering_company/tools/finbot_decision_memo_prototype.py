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
ALLOWED = ["continue_research", "park", "reject", "needs_user_review"]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-root", default=str(DEFAULT_DOCS))
    args = parser.parse_args()
    docs_root = Path(args.docs_root)
    cases = {case["ticker"]: case for case in read_json(RESEARCH_ROOT / "69_alpha_quality_casebook.json")["cases"]}
    valuation = read_json(docs_root / "08_valuation_range_research_prototype.json")
    valuation_by_case = {entry["case_id"]: entry for entry in valuation["entries"]}
    specs = [("YELP", "needs_user_review"), ("NKE", "continue_research")]
    memos = []
    for ticker, status in specs:
        case = cases[ticker]
        memos.append({
            "memo_id": f"memo-cap-v1-{ticker.lower()}",
            "case_id": case["case_id"],
            "ticker": ticker,
            "research_only": True,
            "thesis": case["variant_thesis"],
            "source_alpha_rationale": case["source_alpha_rationale"],
            "primary_evidence": case["primary_evidence_ids"],
            "counter_evidence": [case["risk_qa_summary"], "No stronger conclusion until next evidence action is completed."],
            "valuation_research_range": valuation_by_case.get(case["case_id"]),
            "catalysts": [case["alpha_quality_gate"]["catalyst_path"]],
            "invalidation": [case["alpha_quality_gate"]["risk_reward_research_question"]],
            "open_questions": [case["next_evidence_action"]],
            "decision_status": status,
            "allowed_decision_status": ALLOWED,
            "no_advice_label": "Decision memo status is a research workflow state only; it is not buy/sell/hold, broker action, trade signal or position sizing.",
        })
    payload = {
        "schema": "finbot.decision_memo_prototype.v1",
        "generated_at": NOW,
        "status": "research_decision_memos_only",
        "memos": memos,
    }
    (docs_root / "10_decision_memo_prototype.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = [
        "# 10 Decision Memo Prototype",
        "",
        f"Generated: `{NOW}`",
        "",
        "Decision statuses are limited to continue_research, park, reject, needs_user_review. No buy/sell/hold recommendation.",
        "",
        "| Memo | Ticker | Decision Status | Open Questions |",
        "| --- | --- | --- | --- |",
    ]
    for memo in memos:
        md.append(f"| {memo['memo_id']} | {memo['ticker']} | {memo['decision_status']} | {'; '.join(memo['open_questions'])} |")
    (docs_root / "10_decision_memo_prototype.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "memos": len(memos)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
