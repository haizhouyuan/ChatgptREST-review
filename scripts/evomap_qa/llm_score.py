#!/usr/bin/env python3
"""llm_score.py — LLM 辅助批量评分.

将 Q&A 对批量发送给 LLM (ChatGPT / Gemini) 评分。
输出评分结果到 planning_qa_scored.jsonl。

用法:
    python3 llm_score.py --test             # 测试模式: 只评5条, 打印prompt
    python3 llm_score.py --batch 10         # 每批10条
    python3 llm_score.py --domain AIOS架构   # 只评指定域
    python3 llm_score.py --dry-run          # 只生成prompt不调用

注意: 需要先确认评分prompt效果后再批量运行。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCORED_FILE = Path("/vol1/1000/projects/ChatgptREST/scripts/evomap_qa/planning_qa_scored.jsonl")
PROMPT_OUTPUT = Path("/vol1/1000/projects/ChatgptREST/scripts/evomap_qa/llm_scoring_prompts")

# ---------------------------------------------------------------------------
# Domain-Specific Rubrics (核心设计)
# ---------------------------------------------------------------------------

DOMAIN_RUBRICS: dict[str, dict[str, str]] = {
    # === 技术调研类 ===
    "研究调研": {
        "clarity": "问题是否有明确的调研目标和范围？答案是否有清晰的结构（摘要→证据→结论→待验证项）？",
        "correctness": "调研结论是否事实正确？数据引用是否准确？是否有明显的事实错误？",
        "evidence": "是否引用了可核验的证据（专利/标准/论文/官方文件）？证据分级是否合理？",
        "actionability": "调研结论是否可指导实际决策？建议是否具有可操作性？",
        "risk": "是否识别了信息缺口和不确定性？是否给出了验证方法？",
        "alignment": "答案是否回答了原始调研问题？有无跑题或过度发散？",
        "completeness": "调研覆盖面是否完整？是否有遗漏的关键维度（技术/商业/合规/供应链）？",
    },
    # === 方案规划类 ===
    "方案规划": {
        "clarity": "方案目标是否明确？路线图/里程碑是否有时间线？",
        "correctness": "方案假设是否正确？资源/时间估算是否合理？",
        "evidence": "关键假设是否有数据支撑？投入产出是否有量化分析？",
        "actionability": "是否有分阶段实施路径？负责人/时间线/交付物是否明确？",
        "risk": "是否有风险评估和缓解措施？是否有回滚/降级方案？",
        "alignment": "方案是否对齐业务目标和战略方向？",
        "completeness": "是否覆盖了利益相关方、资源计划、验收标准？",
    },
    # === 工程实施类 ===
    "工程实施": {
        "clarity": "代码/脚本的功能是否有清晰文档？接口/输入输出是否明确？",
        "correctness": "实现是否正确？逻辑是否有bug？边界条件是否处理？",
        "evidence": "是否有测试覆盖？是否有性能验证数据？",
        "actionability": "是否可直接运行/部署？依赖和环境要求是否明确？",
        "risk": "是否考虑了并发、安全、性能？是否有已知限制说明？",
        "alignment": "实现是否符合原始需求/设计文档？",
        "completeness": "功能是否完整？是否有遗漏的 edge case？",
    },
    # === 制造与工艺类 ===
    "制造工艺": {
        "clarity": "工艺流程是否有清晰的步骤描述？关键参数是否定义？",
        "correctness": "工艺参数是否正确？材料选型是否合适？计算是否准确？",
        "evidence": "工艺参数是否有实验/试产数据支撑？是否引用了标准（ISO/GB）？",
        "actionability": "工艺是否可量产？设备和工装要求是否合理？成本是否可控？",
        "risk": "是否识别了工艺风险点（良率、一致性、设备可靠性）？DFMEA/PFMEA是否覆盖？",
        "alignment": "工艺设计是否满足产品设计要求和质量标准？",
        "completeness": "是否覆盖了来料→加工→装配→测试→包装全流程？控制计划是否完整？",
    },
    # === 商务与管理类 ===
    "商务管理": {
        "clarity": "信息传达是否清晰简洁？关键结论是否突出？",
        "correctness": "财务数据/业务指标是否准确？合规信息是否正确？",
        "evidence": "数据引用是否准确？市场/财务/合规依据是否可靠？",
        "actionability": "建议是否考虑了组织现实和执行约束？后续行动项是否明确？",
        "risk": "商业风险和合规风险是否识别？",
        "alignment": "是否对齐公司战略和当前优先事项？",
        "completeness": "利益相关方视角是否覆盖？后续行动项是否明确？",
    },
    # === 默认通用 ===
    "通用": {
        "clarity": "问题和答案是否清晰、有逻辑？",
        "correctness": "事实和技术内容是否正确？",
        "evidence": "结论是否有证据支撑？",
        "actionability": "方案/建议是否可落地？",
        "risk": "风险是否识别并有缓解措施？",
        "alignment": "答案是否回答了问题？",
        "completeness": "覆盖面是否充分？",
    },
}

# Map Q&A domain to rubric category
DOMAIN_TO_RUBRIC: dict[str, str] = {
    "机器人代工业务": "制造工艺",
    "减速器开发": "制造工艺",
    "两轮车车身业务": "制造工艺",
    "AIOS架构": "工程实施",
    "工具链与文档": "工程实施",
    "脚本工具": "工程实施",
    "预算与财务": "商务管理",
    "人员与绩效": "商务管理",
    "业务演示": "商务管理",
    "十五五规划": "方案规划",
    "入口与索引": "通用",
    "KB知识底座": "通用",
    "模板": "通用",
    "受控资料": "商务管理",
    "外来文件管理": "通用",
    "多Agent评审KB": "工程实施",
    "仓库根目录": "通用",
}


def get_rubric_for_record(rec: dict) -> tuple[str, dict[str, str]]:
    """Get the appropriate rubric for a Q&A record."""
    domain = rec.get("domain", "")
    source_type = rec.get("source_type", "")

    # Source type can override domain-based rubric
    if source_type == "research_report":
        cat = "研究调研"
    elif source_type == "tool_script":
        cat = "工程实施"
    else:
        cat = DOMAIN_TO_RUBRIC.get(domain, "通用")

    return cat, DOMAIN_RUBRICS[cat]


# ---------------------------------------------------------------------------
# Prompt Generation
# ---------------------------------------------------------------------------

def build_scoring_prompt(batch: list[dict], batch_id: int = 0) -> str:
    """Build a structured scoring prompt for LLM evaluation."""
    # Determine rubric categories in this batch
    rubric_sections = {}
    for rec in batch:
        cat, rubric = get_rubric_for_record(rec)
        if cat not in rubric_sections:
            rubric_sections[cat] = rubric

    prompt = f"""# Q&A 质量评分任务

你是一位严格的质量评审专家。请对以下 {len(batch)} 条 Q&A 对进行质量评分。

## 评分标尺 (所有维度统一使用 1-5 分)

| 分值 | 含义 | 标准 |
|---|---|---|
| 5 | 优秀 | 可直接作为标准知识库条目，无需修改 |
| 4 | 良好 | 核心正确，小修即可使用 |
| 3 | 及格 | 方向正确但有明显缺漏 |
| 2 | 不及格 | 有重大错误或关键遗漏 |
| 1 | 无效 | 答非所问或完全错误 |

## 评分维度说明 (按场景差异化)

"""
    for cat, rubric in rubric_sections.items():
        prompt += f"### 「{cat}」类评分要点\n\n"
        for dim, desc in rubric.items():
            prompt += f"- **{dim}**: {desc}\n"
        prompt += "\n"

    prompt += """## 输出格式要求

请严格按以下 JSON 数组格式输出，不要添加其他文字：

```json
[
  {
    "qa_id": "pqa_xxxx",
    "clarity": 4,
    "correctness": 3,
    "evidence": 4,
    "actionability": 3,
    "risk": 3,
    "alignment": 5,
    "completeness": 4,
    "overall": 4,
    "comment": "简短评语(1-2句)"
  }
]
```

## 待评分的 Q&A 对

"""
    for i, rec in enumerate(batch, 1):
        cat, _ = get_rubric_for_record(rec)
        q = rec.get("question", "")[:500]
        a = rec.get("answer_summary", "")[:1500]
        prompt += f"""---
### Q&A #{i} | ID: {rec.get('qa_id', '')} | 域: {rec.get('domain', '')} | 类型: {cat}

**问题:**
{q}

**答案:**
{a}

"""

    prompt += "---\n\n请开始评分。输出 JSON 数组，每条包含 qa_id 和 7 个维度分数(clarity/correctness/evidence/actionability/risk/alignment/completeness) + overall + comment。"
    return prompt


# ---------------------------------------------------------------------------
# Batch Processing
# ---------------------------------------------------------------------------

def generate_prompt_files(records: list[dict], batch_size: int = 10,
                          domain_filter: str = "", max_batches: int = 0) -> list[Path]:
    """Generate prompt files for LLM scoring."""
    # Filter to unscored records
    candidates = [
        r for r in records
        if r.get("scores_human", {}).get("overall") is None
        and (not domain_filter or r.get("domain", "") == domain_filter)
    ]

    if not candidates:
        print("No unscored records to process.")
        return []

    PROMPT_OUTPUT.mkdir(parents=True, exist_ok=True)
    output_files = []
    total_batches = (len(candidates) + batch_size - 1) // batch_size
    if max_batches > 0:
        total_batches = min(total_batches, max_batches)

    for batch_idx in range(total_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(candidates))
        batch = candidates[start:end]

        prompt = build_scoring_prompt(batch, batch_idx + 1)
        out_path = PROMPT_OUTPUT / f"batch_{batch_idx+1:03d}_prompt.md"
        out_path.write_text(prompt, encoding="utf-8")
        output_files.append(out_path)

        # Also save the batch record IDs for later matching
        ids_path = PROMPT_OUTPUT / f"batch_{batch_idx+1:03d}_ids.json"
        ids_path.write_text(
            json.dumps([r["qa_id"] for r in batch], ensure_ascii=False),
            encoding="utf-8"
        )

    return output_files


def parse_llm_response(response_text: str) -> list[dict]:
    """Parse LLM response JSON array."""
    # Extract JSON from markdown code blocks if present
    import re
    json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
    if json_match:
        response_text = json_match.group(1)

    # Try to parse
    try:
        result = json.loads(response_text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Try line-by-line
    results = []
    for line in response_text.strip().split("\n"):
        line = line.strip().rstrip(",")
        if line.startswith("{"):
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return results


def import_llm_scores(response_file: Path, scorer: str = "llm") -> int:
    """Import LLM scores from a response file into the scored JSONL."""
    text = response_file.read_text("utf-8")
    scores = parse_llm_response(text)

    if not scores:
        print(f"ERROR: Could not parse scores from {response_file}")
        return 0

    # Load current records
    records = []
    index = {}
    for line in SCORED_FILE.read_text("utf-8").strip().split("\n"):
        if line.strip():
            try:
                rec = json.loads(line)
                index[rec["qa_id"]] = len(records)
                records.append(rec)
            except (json.JSONDecodeError, KeyError):
                pass

    updated = 0
    for s in scores:
        qa_id = s.get("qa_id", "")
        if qa_id not in index:
            continue
        idx = index[qa_id]
        records[idx]["scores_human"] = {
            "clarity": s.get("clarity"),
            "correctness": s.get("correctness"),
            "evidence": s.get("evidence"),
            "actionability": s.get("actionability"),
            "risk": s.get("risk"),
            "alignment": s.get("alignment"),
            "completeness": s.get("completeness"),
            "overall": s.get("overall"),
            "comment": s.get("comment", ""),
        }
        records[idx]["human_scorer"] = scorer
        records[idx]["human_scored_at"] = datetime.now(timezone.utc).isoformat()
        records[idx]["status"] = "scored" if s.get("overall") else "pending_human_review"
        updated += 1

    with open(SCORED_FILE, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return updated


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LLM-assisted Q&A scoring")
    parser.add_argument("--test", action="store_true", help="Test mode: 5条, print prompt")
    parser.add_argument("--batch", type=int, default=10, help="Batch size")
    parser.add_argument("--domain", type=str, default="")
    parser.add_argument("--max-batches", type=int, default=0, help="Max batches to generate (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Only generate prompts")
    parser.add_argument("--import-response", type=str, default="",
                        help="Import LLM response file")
    parser.add_argument("--scorer", type=str, default="llm_chatgpt")
    args = parser.parse_args()

    if args.import_response:
        resp_path = Path(args.import_response)
        updated = import_llm_scores(resp_path, scorer=args.scorer)
        print(f"Imported {updated} scores from {resp_path}")
        return

    # Load records
    records = []
    for line in SCORED_FILE.read_text("utf-8").strip().split("\n"):
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    if args.test:
        # Test mode: generate 1 batch of 5
        candidates = [r for r in records if r.get("scores_human", {}).get("overall") is None]
        if args.domain:
            candidates = [r for r in candidates if r.get("domain", "") == args.domain]
        batch = candidates[:5]
        prompt = build_scoring_prompt(batch)
        print(prompt)
        print(f"\n\n{'='*60}")
        print(f"Prompt length: {len(prompt)} chars (~{len(prompt)//4} tokens)")
        print(f"{'='*60}")
        return

    # Generate prompt files
    files = generate_prompt_files(
        records, batch_size=args.batch,
        domain_filter=args.domain,
        max_batches=args.max_batches or 999999,
    )

    print(f"\n{'='*60}")
    print(f"LLM Scoring Prompts Generated")
    print(f"{'='*60}")
    print(f"Batch size: {args.batch}")
    print(f"Generated: {len(files)} prompt files")
    print(f"Output dir: {PROMPT_OUTPUT}/")
    print(f"\n下一步:")
    print(f"  1. 将 prompt 文件内容粘贴到 ChatGPT Pro / Gemini Pro")
    print(f"  2. 复制 LLM 返回的 JSON 到 response 文件")
    print(f"  3. 运行: python3 llm_score.py --import-response <response_file>")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
