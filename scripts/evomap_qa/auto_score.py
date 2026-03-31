#!/usr/bin/env python3
"""auto_score.py — 基于 OpenMind v3 规则的机器自动初评 (v2: 7维+Gate).

读取 planning_qa_all.jsonl，为每条 Q&A 对计算:
  1. Value Gate: is_valid_qa + has_reuse_value
  2. 路由评分 (I/C/K/U/R)
  3. Rubric 7维评分 (clarity/correctness/evidence/actionability/risk/alignment/completeness)
  4. 路由判定

输出: planning_qa_scored.jsonl (覆盖写入)

用法:
    python3 auto_score.py
    python3 auto_score.py --input path/to/qa.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

INPUT_DEFAULT = Path("/vol1/1000/projects/ChatgptREST/scripts/evomap_qa/planning_qa_all.jsonl")
OUTPUT_DEFAULT = Path("/vol1/1000/projects/ChatgptREST/scripts/evomap_qa/planning_qa_scored.jsonl")

# 7 rubric dimensions (equal weight for v1)
RUBRIC_DIMS = ("clarity", "correctness", "evidence", "actionability",
               "risk", "alignment", "completeness")


# ---------------------------------------------------------------------------
# Layer 0: Value Gate
# ---------------------------------------------------------------------------

def gate_is_valid_qa(q: str, a: str) -> bool:
    """Is this a valid Q&A pair (not noise/fragment)?"""
    if len(q.strip()) < 10:
        return False
    if len(a.strip()) < 50:
        return False
    # Pure file listings, directory trees, etc.
    if a.count("/") > 20 and len(a) < 500:
        return False
    # All whitespace or repeated chars
    if len(set(a.strip())) < 10:
        return False
    return True


def gate_has_reuse_value(q: str, a: str, source_type: str) -> bool:
    """Does this Q&A have reuse value for KB/EvoMap?"""
    # Index/TOC files have low reuse value
    if source_type == "index" and len(a) < 300:
        return False
    # Very short answers rarely have KB value
    if len(a) < 100:
        return False
    # Template-only files
    if source_type == "template" and "{{" in a:
        return False
    return True


# ---------------------------------------------------------------------------
# Route Scores (OpenMind v3 I/C/K/U/R) — unchanged
# ---------------------------------------------------------------------------

def score_intent_certainty(q: str) -> float:
    score = 50.0
    if q.endswith("？") or q.endswith("?"):
        score += 15
    if any(kw in q for kw in ["如何", "怎么", "什么", "哪些", "是否", "为什么"]):
        score += 10
    if any(kw in q for kw in ["请", "要求", "必须", "输出"]):
        score += 10
    if len(q) < 20:
        score -= 15
    elif len(q) > 100:
        score += 10
    return min(100.0, max(0.0, round(score, 1)))


def score_complexity(q: str, a_len: int) -> float:
    score = 30.0
    numbered_items = len(re.findall(r'[1-9][）\)\.]\s', q))
    score += min(30, numbered_items * 8)
    if any(kw in q for kw in ["全流程", "全链路", "全面", "体系", "系统"]):
        score += 15
    if any(kw in q for kw in ["对比", "方案", "规划", "路线图"]):
        score += 10
    if a_len > 5000:
        score += 15
    elif a_len > 2000:
        score += 10
    elif a_len > 500:
        score += 5
    return min(100.0, max(0.0, round(score, 1)))


def score_kb(source_type: str, q: str) -> float:
    if source_type == "research_report":
        return 25.0
    if source_type == "conversational":
        return 30.0
    if source_type == "tool_script":
        return 60.0
    if source_type == "index":
        return 80.0
    if any(kw in q for kw in ["调研", "研究", "分析", "评审"]):
        return 25.0
    return 45.0


def score_urgency(q: str) -> float:
    if any(kw in q for kw in ["紧急", "立即", "马上", "今天"]):
        return 90.0
    if any(kw in q for kw in ["尽快", "优先"]):
        return 70.0
    return 30.0


def score_risk_route(q: str, source_type: str) -> float:
    score = 20.0
    if any(kw in q for kw in ["合同", "法律", "认证", "安全", "合规"]):
        score += 30
    if any(kw in q for kw in ["预算", "成本", "投资", "报价"]):
        score += 20
    if any(kw in q for kw in ["人员", "绩效", "薪资"]):
        score += 15
    if source_type == "research_report":
        score += 10
    return min(100.0, max(0.0, round(score, 1)))


def determine_route(scores: dict[str, float]) -> str:
    I = scores["intent_certainty"]
    C = scores["complexity"]
    K = scores["kb_score"]
    U = scores["urgency"]
    if I < 55:
        return "clarify"
    if U > 80 and C < 40 and K > 50:
        return "kb_answer"
    if C > 70 or K < 40:
        return "deep_research"
    if C > 60:
        return "funnel"
    if K > 60:
        return "kb_answer"
    return "hybrid"


# ---------------------------------------------------------------------------
# Layer 1: 7-Dimension Rubric Scoring (0-1 scale, maps to 1-5 for display)
# ---------------------------------------------------------------------------

def rubric_clarity(q: str, a: str) -> float:
    """Q clarity + A structure + logical flow."""
    score = 0.5
    if len(q) > 30 and any(kw in q for kw in ["如何", "什么", "请", "具体"]):
        score += 0.15
    if "## " in a or "### " in a:
        score += 0.1
    if "| " in a:
        score += 0.1
    if len(a) > 200:
        score += 0.05
    return min(1.0, round(score, 2))


def rubric_correctness(q: str, a: str, source_type: str) -> float:
    """Factual/technical correctness heuristic."""
    score = 0.5
    # Structured answers tend to be more correct
    if source_type in ("research_report", "plan_document"):
        score += 0.1
    # Self-consistency signals
    if any(kw in a for kw in ["验证", "确认", "已测试", "实测"]):
        score += 0.1
    # Hedging = honest about uncertainty
    if any(kw in a for kw in ["待验证", "需确认", "不确定", "初步"]):
        score += 0.05
    # Length suggests depth (weak signal)
    if len(a) > 1000:
        score += 0.05
    return min(1.0, round(score, 2))


def rubric_evidence(a: str) -> float:
    """Data/references/standards support."""
    score = 0.3
    if any(kw in a for kw in ["来源", "证据", "参考", "引用", "数据"]):
        score += 0.15
    if "http" in a or ".com" in a or ".cn" in a:
        score += 0.1
    if any(kw in a for kw in ["置信度", "可信度", "证据级别"]):
        score += 0.15
    if any(kw in a for kw in ["GB", "ISO", "标准"]):
        score += 0.1
    return min(1.0, round(score, 2))


def rubric_actionability(a: str, source_type: str) -> float:
    """Can the recommendation be directly executed?"""
    score = 0.4
    if any(kw in a for kw in ["步骤", "阶段", "Phase", "操作"]):
        score += 0.15
    if any(kw in a for kw in ["验收", "交付物", "输出", "产出"]):
        score += 0.1
    if any(kw in a for kw in ["负责人", "时间线", "deadline", "节点"]):
        score += 0.1
    if source_type == "tool_script":
        score += 0.15  # scripts are inherently actionable
    if any(kw in a for kw in ["建议", "方案", "措施", "对策"]):
        score += 0.05
    return min(1.0, round(score, 2))


def rubric_risk(a: str) -> float:
    """Risk identification + mitigation."""
    score = 0.3
    if any(kw in a for kw in ["风险", "risk"]):
        score += 0.2
    if any(kw in a for kw in ["缓解", "规避", "对策", "预案"]):
        score += 0.15
    if any(kw in a for kw in ["不确定性", "缺口", "待验证"]):
        score += 0.1
    return min(1.0, round(score, 2))


def rubric_alignment(q: str, a: str) -> float:
    """Does the answer address the question?"""
    score = 0.5
    q_words = set(re.findall(r'[\u4e00-\u9fff]+', q))
    a_words = set(re.findall(r'[\u4e00-\u9fff]+', a[:500]))
    if q_words:
        overlap = len(q_words & a_words) / len(q_words)
        score += overlap * 0.3
    if len(a) > len(q) * 3:
        score += 0.1
    return min(1.0, round(score, 2))


def rubric_completeness(a: str) -> float:
    """Coverage breadth."""
    score = 0.4
    section_count = len(re.findall(r'^#{1,3}\s', a, re.MULTILINE))
    if section_count >= 5:
        score += 0.2
    elif section_count >= 2:
        score += 0.1
    if len(a) > 3000:
        score += 0.15
    elif len(a) > 1000:
        score += 0.1
    if any(kw in a for kw in ["结论", "总结", "建议", "小结"]):
        score += 0.1
    return min(1.0, round(score, 2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Auto-score Q&A pairs (v2: 7-dim + Gate)")
    parser.add_argument("--input", type=str, default=str(INPUT_DEFAULT))
    parser.add_argument("--output", type=str, default=str(OUTPUT_DEFAULT))
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        return

    records = []
    for line in input_path.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    print(f"Scoring {len(records)} Q&A pairs (v2: 7-dim + Gate)...")

    gate_stats = {"valid": 0, "invalid": 0, "no_reuse": 0}

    for rec in records:
        q = rec.get("question", "")
        a = rec.get("answer_summary", "")
        source_type = rec.get("source_type", "")
        a_len = len(a)

        # --- Layer 0: Value Gate ---
        valid = gate_is_valid_qa(q, a)
        reuse = gate_has_reuse_value(q, a, source_type) if valid else False
        rec["gate"] = {
            "is_valid_qa": valid,
            "has_reuse_value": reuse,
        }
        if not valid:
            gate_stats["invalid"] += 1
            rec["status"] = "rejected"
            rec["rubric_auto"] = {d: 0.0 for d in RUBRIC_DIMS}
            rec["scores_auto"] = {}
            rec["route_auto"] = "reject"
            continue
        if not reuse:
            gate_stats["no_reuse"] += 1
            rec["status"] = "archived"
        else:
            gate_stats["valid"] += 1

        # --- Route scores ---
        scores_auto = {
            "intent_certainty": score_intent_certainty(q),
            "complexity": score_complexity(q, a_len),
            "kb_score": score_kb(source_type, q),
            "urgency": score_urgency(q),
            "risk": score_risk_route(q, source_type),
        }

        # --- Layer 1: 7-Dimension Rubric ---
        rubric_auto = {
            "clarity": rubric_clarity(q, a),
            "correctness": rubric_correctness(q, a, source_type),
            "evidence": rubric_evidence(a),
            "actionability": rubric_actionability(a, source_type),
            "risk": rubric_risk(a),
            "alignment": rubric_alignment(q, a),
            "completeness": rubric_completeness(a),
        }

        rec["scores_auto"] = scores_auto
        rec["rubric_auto"] = rubric_auto
        rec["route_auto"] = determine_route(scores_auto)

        if rec.get("status") in ("extracted", "pending_extraction"):
            rec["status"] = "auto_scored"

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Stats
    routes = {}
    avg_rubric = {k: 0.0 for k in RUBRIC_DIMS}
    scored_count = 0
    for rec in records:
        if rec.get("status") == "rejected":
            continue
        route = rec.get("route_auto", "?")
        routes[route] = routes.get(route, 0) + 1
        scored_count += 1
        for k in avg_rubric:
            avg_rubric[k] += rec.get("rubric_auto", {}).get(k, 0)

    n = max(scored_count, 1)
    for k in avg_rubric:
        avg_rubric[k] = round(avg_rubric[k] / n, 3)

    print(f"\n{'='*60}")
    print(f"Auto-Scoring Complete (v2: 7-dim + Gate)")
    print(f"{'='*60}")
    print(f"Total records:    {len(records)}")
    print(f"  ✅ Valid+Reuse:  {gate_stats['valid']}")
    print(f"  📦 Archived:    {gate_stats['no_reuse']}")
    print(f"  ❌ Rejected:    {gate_stats['invalid']}")
    print(f"Output: {output_path}")
    print(f"\nRoute distribution (valid only):")
    for route, count in sorted(routes.items(), key=lambda x: -x[1]):
        print(f"  {route:18s} {count:4d}")
    print(f"\nAvg rubric (7-dim, valid only):")
    for k, v in avg_rubric.items():
        bar = "█" * int(v * 20) + "░" * (20 - int(v * 20))
        print(f"  {k:16s} {bar} {v:.3f}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
