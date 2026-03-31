"""
S10 Integration Test: Feishu → Advisor → Funnel → ProjectCard

Runs the 3 real requirements from the user's Feishu session through
the full pipeline.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chatgptrest.contracts.event_log import EventLogStore
from chatgptrest.contracts.schemas import IntentSignals, KBProbeResult, Route
from chatgptrest.advisor import route_request
from chatgptrest.workflows.funnel import FunnelEngine, extract_intent_from_text, classify_request_type


# ---------------------------------------------------------------------------
# Real Feishu requirements extracted from feishu-intake session 8d2cfd8d
# ---------------------------------------------------------------------------

FEISHU_REQUIREMENTS = [
    {
        "id": "feishu_req_01",
        "title": "积分奖励系统设计",
        "timestamp": "2026-02-28 02:05:41 GMT+8",
        "raw_text": (
            "我要开发一个给我儿子用的积分奖励的这样的一个系统，"
            "它既是一个系统，也是个应用，就是要承载内部的一个算法。"
            "就干什么事情获得多少奖励，然后里面也有游戏系统的设计思路，"
            "儿童心理发展学的设计思路，包括成就系统。"
            "是一个系统的完善的一种小应用。"
        ),
    },
    {
        "id": "feishu_req_02",
        "title": "行星滚柱丝杠产品规划",
        "timestamp": "2026-02-28 02:07:32 GMT+8",
        "raw_text": (
            "把我关于行星滚柱丝杠的一些研究，还有跟就是跟别人的沟通交流，"
            "还有做的一些调研工作都梳理整理一下，然后跟顾问交流，"
            "把现状先理清楚，我都有哪些资产，都有哪些产物。"
            "然后这块的工作呢，是我想要开始组建团队来开发产品。"
        ),
    },
    {
        "id": "feishu_req_03",
        "title": "投研框架重构",
        "timestamp": "2026-02-28 02:08:20 GMT+8",
        "raw_text": (
            "现在我要做关于投研助手的相关工作的一些需求，"
            "我之前都做过的工作基本上都在codex目录里面，"
            "所以我之前做的工作可能先要做一个总结梳理，把以前做过的事情汇总。"
            "重构并优化个人投研框架，覆盖A股和美股市场。"
            "恢复对特定财经博主视频的分析工作流，"
            "为美股市场建立一套新的研究体系，"
            "重点关注AI、智能机器人、商业航天及Web3等前沿赛道。"
        ),
    },
]


def run_feishu_pipeline():
    """Run all 3 Feishu requirements through the full pipeline."""
    store = EventLogStore(":memory:")
    funnel = FunnelEngine(event_log=store)

    results = []

    for req in FEISHU_REQUIREMENTS:
        print(f"\n{'='*60}")
        print(f"📨 Feishu Requirement: {req['title']}")
        print(f"   Time: {req['timestamp']}")
        print(f"{'='*60}")

        # Step 1: Analyze intent
        intent = extract_intent_from_text(req["raw_text"])
        req_type = classify_request_type(req["raw_text"])
        print(f"\n  [1] Intent Analysis:")
        print(f"      Type: {req_type}")
        print(f"      Explicit requests: {intent['explicit_requests'][:3]}")
        print(f"      Emotions: {intent['emotions']}")

        # Step 2: Route through Advisor
        ctx = route_request(
            req["raw_text"],
            intent=IntentSignals(
                intent_confidence=0.75,
                multi_intent="系统" in req["raw_text"] or "框架" in req["raw_text"],
                step_count_est=8 if req_type in ("project", "planning") else 5,
                verification_need=True,
            ),
            kb_probe=KBProbeResult(answerability=0.2),
            trace_id=req["id"],
        )
        print(f"\n  [2] Advisor Routing:")
        print(f"      Route: {ctx.selected_route}")
        print(f"      Scores: I={ctx.scores.intent_certainty}, "
              f"C={ctx.scores.complexity}, K={ctx.scores.kb_score}")

        # Step 3: Run through Funnel
        state = funnel.run(req["raw_text"], trace_id=req["id"])
        card = state.project_card

        print(f"\n  [3] Funnel Output:")
        print(f"      Stages completed: {len(state.stage_history)}")
        print(f"      Rubric: {card.rubric_snapshot.total} (Gate {card.rubric_snapshot.gate})")
        print(f"      Title: {card.title[:60]}")
        print(f"      Tasks: {len(card.tasks)}")
        print(f"      Risks: {len(card.risks)}")

        # Prepare result summary
        result = {
            "id": req["id"],
            "title": req["title"],
            "route": ctx.selected_route,
            "rubric": card.rubric_snapshot.total,
            "gate": card.rubric_snapshot.gate,
            "tasks": [t.title for t in card.tasks],
            "risks": len(card.risks),
            "trace_events": store.count(trace_id=req["id"]),
        }
        results.append(result)

        print(f"\n  [4] Trace: {result['trace_events']} events recorded")
        print(f"  ✅ Pipeline complete for: {req['title']}")

    # Summary
    print(f"\n\n{'='*60}")
    print(f"📊 Summary: All {len(results)} Feishu requirements processed")
    print(f"{'='*60}")
    for r in results:
        print(f"  [{r['id']}] {r['title']}")
        print(f"    route={r['route']}  rubric={r['rubric']}  "
              f"gate={r['gate']}  tasks={len(r['tasks'])}  "
              f"risks={r['risks']}  events={r['trace_events']}")

    # Verify all passed
    all_ok = all(r["rubric"] > 0 and r["tasks"] for r in results)
    assert all_ok, "Some requirements failed to produce valid ProjectCards"
    print(f"\n🎉 All {len(results)} requirements processed successfully!")
    return results


if __name__ == "__main__":
    run_feishu_pipeline()
