---
title: "2026-03-18 finbot WP5-WP7 实施 Walkthrough v2"
source: "[[CODEX]]"
author:
  - "[[CODEX]]"
published:
  created: 2026-03-18
description: "WP5-WP7 补齐验收缺口：独立 artifact、prompt 消费 seam、dashboard 可见性、回归测试。"
tags:
  - "finbot"
  - "walkthrough"
  - "wp5"
  - "wp6"
  - "wp7"
  - "v2"
---

# finbot WP5-WP7 实施 Walkthrough v2

## 这次补齐了什么

相对 v1，这次补的不是新概念，而是把验收缺口补实：

1. `opportunity_deepen()` 现在会独立落盘：
   - `peer_snapshot.json`
   - `transcript_packet.json`
   - `primary_data_packet.json`
2. `claim lane` / `skeptic lane` 现在支持消费 `transcript_packet`
3. `expression lane` 现在支持消费已有 `peer_snapshot`
4. promotion gate 现在会读取 `primary_data_packet.promotion_enrichment`
5. investor opportunity dashboard 现在能直接看到：
   - peer / valuation discipline
   - transcript provider 状态
   - primary-data promotion recommendation

## 为什么要补这轮

v1 已经把 WP5-WP7 的模块和主流程接上，但还存在 4 个交付缺口：

1. 新 artifact 只嵌在 `research_package.json` 里，没有独立文件
2. `expression lane` 并没有真正消费 peer seam
3. `claim/skeptic lane` 没有消费 transcript seam
4. dashboard 没有展示 WP5-WP7 输出

这轮就是把这些 seam 从“字段存在”补到“产物可追溯、prompt 可消费、界面可见”。

## 代码落点

- `chatgptrest/finbot.py`
  - `_build_claim_lane_prompt()`
  - `_build_skeptic_lane_prompt()`
  - `_build_expression_lane_prompt()`
  - `opportunity_deepen()`
- `chatgptrest/dashboard/templates/investor_opportunity_detail.html`
- `tests/test_finbot.py`
- `tests/test_finbot_dashboard_service_integration.py`

## 当前 provider 状态

### Transcript / Primary Data

- 未配置 `FMP_API_KEY` / `ALPHA_VANTAGE_API_KEY` 时：
  - `transcript_packet.provider = "disabled"`
  - `transcript_packet.available = false`
  - `primary_data_packet.primary_sources_found = false`
  - `promotion_enrichment.promotion_recommendation = "no_primary_data"`

### Peer Snapshot

- 没有真实 peer quote 或 market truth 时：
  - `peers = []`
  - 但仍会保留 `leader_expression` 和 `valuation_driver`
  - 如存在显著目标价/现价差，会产出 `reverse_dcf_hint`

## 验收命令

```bash
cd /vol1/1000/projects/ChatgptREST
TMPDIR=/vol1/1000/projects/ChatgptREST/.codex_tmp/pytest-tmp \
  ./.venv/bin/pytest -q tests/test_finbot.py tests/test_finbot_modules.py tests/test_finbot_dashboard_service_integration.py
```

## 验收重点

1. `latest.json` / `research_package.json` 里存在 `peer_snapshot`、`transcript_packet`、`primary_data_packet`
2. `guardrail_artifacts` 里新增三条独立 artifact 路径
3. dashboard opportunity detail 能读到这三块结构
4. transcript / primary data provider 缺失时仍然 deterministic fallback，不会把 `opportunity_deepen()` 弄挂
