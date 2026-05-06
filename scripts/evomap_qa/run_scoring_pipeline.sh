#!/usr/bin/env bash
# run_scoring_pipeline.sh — 一键运行 Q&A 评分全流程
#
# 用法:
#   bash run_scoring_pipeline.sh          # 全量从头
#   bash run_scoring_pipeline.sh --collect  # 仅回收人工评分 + 推送
#
# 前提: planning_qa_all.jsonl 已生成过一次

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  EvoMap Q&A Scoring Pipeline"
echo "  $(date '+%Y-%m-%d %H:%M')"
echo "========================================"

if [[ "${1:-}" == "--collect" ]]; then
    echo ""
    echo ">>> Step 1: 回收人工评分..."
    python3 collect_scores.py

    echo ""
    echo ">>> Step 2: 推送到 EvoMap..."
    python3 push_evomap.py

    echo ""
    echo "✅ 评分回收 + EvoMap推送 完成！"
    exit 0
fi

echo ""
echo ">>> Step 1: 全量抽取 Q&A..."
python3 extract_qa.py

echo ""
echo ">>> Step 2: 机器自动初评..."
python3 auto_score.py

echo ""
echo ">>> Step 3: 生成人工评分表..."
python3 gen_review_sheet.py

echo ""
echo "========================================"
echo "  流水线完成！"
echo "========================================"
echo ""
echo "下一步:"
echo "  1. 打开 review_sheets/ 目录下的评分表"
echo "  2. 在黄色区域填入 1-5 分"
echo "  3. 填完后运行: bash run_scoring_pipeline.sh --collect"
echo ""
