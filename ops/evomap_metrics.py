#!/usr/bin/env python3
"""EvoMap Evolution Metrics — measures self-evolution effectiveness.

Compares before/after metrics to show improvement from actuator layer.

Usage:
    python3 ops/evomap_metrics.py
"""

import os
import sys
import json
import sqlite3
from pathlib import Path

EVOMAP_DB = Path(os.path.expanduser("~/.openmind/evomap.db"))
EVENTS_DB = Path(os.path.expanduser("~/.openmind/events.db"))
KB_REG_DB = Path(os.path.expanduser("~/.openmind/kb_registry.db"))
MEMORY_DB = Path(os.path.expanduser("~/.openmind/memory.db"))


def _query(db_path: Path, sql: str, params=()) -> list:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def main():
    print("=" * 60)
    print("  EvoMap 进化度量报告")
    print("=" * 60)

    # 1. Signal counts
    print("\n📊 信号总量:")
    if EVOMAP_DB.exists():
        rows = _query(EVOMAP_DB,
            "SELECT signal_type, COUNT(*) as cnt FROM signals "
            "GROUP BY signal_type ORDER BY cnt DESC"
        )
        total = sum(r["cnt"] for r in rows)
        print(f"  总计: {total}")
        for r in rows:
            print(f"    {r['signal_type']:35s} {r['cnt']:>5d}")
    else:
        print("  ⚠️  evomap.db 不存在")

    # 2. LLM failure rate
    print("\n🔴 LLM 可靠性:")
    completed = sum(r["cnt"] for r in _query(EVOMAP_DB,
        "SELECT COUNT(*) as cnt FROM signals WHERE signal_type='llm.call_completed'"))
    failed = sum(r["cnt"] for r in _query(EVOMAP_DB,
        "SELECT COUNT(*) as cnt FROM signals WHERE signal_type='llm.call_failed'"))
    total_llm = completed + failed
    fail_rate = (failed / total_llm * 100) if total_llm > 0 else 0
    print(f"  成功: {completed}    失败: {failed}    总计: {total_llm}")
    print(f"  失败率: {fail_rate:.1f}%")

    # 3. Circuit breaker activity
    print("\n⚡ 熔断器活动:")
    cb_signals = _query(EVOMAP_DB,
        "SELECT COUNT(*) as cnt FROM signals WHERE signal_type='actuator.circuit_break'")
    cb_count = cb_signals[0]["cnt"] if cb_signals else 0
    print(f"  熔断器触发次数: {cb_count}")

    # 4. KB metrics
    print("\n📚 知识库质量:")
    if KB_REG_DB.exists():
        artifacts = _query(KB_REG_DB,
            "SELECT artifact_id, quality_score, stability, file_size FROM artifacts "
            "ORDER BY quality_score DESC")
        total_kb = len(artifacts)
        scored = len([a for a in artifacts if a["quality_score"] > 0])
        avg_size = sum(a["file_size"] for a in artifacts) / max(total_kb, 1)
        print(f"  制品总数: {total_kb}")
        print(f"  score > 0: {scored}/{total_kb}")
        print(f"  平均大小: {avg_size:.0f} bytes")
        for a in artifacts[:5]:
            print(f"    {a['artifact_id'][:20]:20s}  score={a['quality_score']:.2f}  "
                  f"stability={a['stability']}  size={a['file_size']}")
    else:
        print("  ⚠️  kb_registry.db 不存在")

    # 5. KB scoring activity
    print("\n📈 KB 评分闭环:")
    kb_helpful = _query(EVOMAP_DB,
        "SELECT COUNT(*) as cnt FROM signals WHERE signal_type='kb.artifact_helpful'")
    kb_pruned = _query(EVOMAP_DB,
        "SELECT COUNT(*) as cnt FROM signals WHERE signal_type='kb.artifact_pruned'")
    print(f"  kb.artifact_helpful: {kb_helpful[0]['cnt'] if kb_helpful else 0}")
    print(f"  kb.artifact_pruned:  {kb_pruned[0]['cnt'] if kb_pruned else 0}")

    # 6. Gate tuner activity
    print("\n🚪 门禁自调:")
    gt_signals = _query(EVOMAP_DB,
        "SELECT COUNT(*) as cnt FROM signals WHERE signal_type='actuator.gate_tuned'")
    gt_count = gt_signals[0]["cnt"] if gt_signals else 0
    print(f"  门禁调整次数: {gt_count}")

    # Gate pass/fail ratio
    gate_passed = sum(r["cnt"] for r in _query(EVOMAP_DB,
        "SELECT COUNT(*) as cnt FROM signals WHERE signal_type='gate.passed'"))
    gate_failed = sum(r["cnt"] for r in _query(EVOMAP_DB,
        "SELECT COUNT(*) as cnt FROM signals WHERE signal_type='gate.failed'"))
    gate_total = gate_passed + gate_failed
    if gate_total > 0:
        print(f"  通过率: {gate_passed}/{gate_total} ({gate_passed/gate_total*100:.0f}%)")

    # 7. Memory records
    print("\n🧠 记忆系统:")
    if MEMORY_DB.exists():
        mem_rows = _query(MEMORY_DB, "SELECT COUNT(*) as cnt FROM memory_records")
        print(f"  记忆记录: {mem_rows[0]['cnt'] if mem_rows else 0}")
    else:
        print("  ⚠️  memory.db 不存在")

    # 8. Signal naming check
    print("\n🏷️  信号命名一致性:")
    legacy = _query(EVOMAP_DB,
        "SELECT COUNT(*) as cnt FROM signals WHERE signal_type LIKE '%route_selected%'")
    canonical = _query(EVOMAP_DB,
        "SELECT COUNT(*) as cnt FROM signals WHERE signal_type = 'route.selected'")
    legacy_cnt = legacy[0]["cnt"] if legacy else 0
    canonical_cnt = canonical[0]["cnt"] if canonical else 0
    print(f"  旧格式 (route_selected): {legacy_cnt}")
    print(f"  新格式 (route.selected):  {canonical_cnt}")
    if legacy_cnt == 0:
        print("  ✅ 命名统一完成")
    else:
        print(f"  ⚠️  仍有 {legacy_cnt} 条旧格式记录")

    # 9. Error categorization
    print("\n🔍 错误分类:")
    error_cats = _query(EVOMAP_DB,
        "SELECT json_extract(data, '$.error_category') as cat, COUNT(*) as cnt "
        "FROM signals WHERE signal_type='llm.call_failed' "
        "AND json_extract(data, '$.error_category') IS NOT NULL "
        "GROUP BY cat ORDER BY cnt DESC")
    if error_cats:
        for r in error_cats:
            print(f"    {r['cat'] or 'unknown':20s} {r['cnt']:>5d}")
    else:
        print("  ⚠️  无错误分类数据（新数据还未产生）")

    # 10. Evolution maturity score
    print("\n" + "=" * 60)
    print("  进化成熟度评分")
    print("=" * 60)
    scores = {
        "信号收集": min(10, total_llm // 50) if EVOMAP_DB.exists() else 0,
        "熔断器": min(10, cb_count * 2) if cb_count > 0 else 0,
        "KB评分": min(10, scored * 2) if KB_REG_DB.exists() else 0,
        "门禁自调": min(10, gt_count * 3) if gt_count > 0 else 0,
        "命名统一": 10 if legacy_cnt == 0 else max(0, 10 - legacy_cnt),
    }
    for name, score in scores.items():
        bar = "█" * score + "░" * (10 - score)
        print(f"  {name:10s}: {bar} {score}/10")

    total_score = sum(scores.values())
    print(f"\n  总分: {total_score}/50")
    print("=" * 60)


if __name__ == "__main__":
    main()
