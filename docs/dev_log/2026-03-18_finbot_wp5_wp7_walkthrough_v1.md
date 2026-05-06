---
title: "2026-03-18 finbot WP5-WP7 实施 Walkthrough"
source: "[[CLAUDE]]"
author:
  - "[[CLAUDE]]"
published:
  created: 2026-03-18
description: "WP5-WP7 剩余阶段实施说明：peer_snapshot, transcript_provider, primary_data_enrich"
tags:
  - "finbot"
  - "walkthrough"
  - "wp5"
  - "wp6"
  - "wp7"
---

# finbot WP5-WP7 实施 Walkthrough

**日期**: 2026-03-18
**分支**: `feature/finbot-remaining-phases-20260318`

---

## 概述

本阶段实施了三项延后的功能增强：

1. **WP5: Peer Snapshot / Valuation Discipline** — 同业对比与估值纪律
2. **WP6: Earnings Call Transcript Provider** — 财报电话会 transcript 提供
3. **WP7: Primary Data / Source Enrichment Seam** — 一手数据/源 enrichment

---

## 做了什么

### 1. 新增模块

| 文件 | 功能 |
|------|------|
| `chatgptrest/finbot_modules/peer_snapshot.py` | 同业对比快照，提取估值驱动因素，生成反向 DCF 提示 |
| `chatgptrest/finbot_modules/transcript_provider.py` | 财报电话会 transcript 获取，支持优雅降级 |
| `chatgptrest/finbot_modules/primary_data_enrich.py` | 一手数据 enrichment，反哺 claim bindings 和 promotion gate |

### 2. 集成到 opportunity_deapen()

- **Stage 3 后**：构建 `peer_snapshot`，传入 Decision lane
- **Stage 4 前**：构建 `transcript_packet` 和 `primary_data_packet`
- **package_payload**：包含所有三个新 artifact

### 3. 数据流

```
opportunity_deepen()
├── Stage 1-2: Claim + Skeptic lanes
├── Stage 3: Expression lane + Market Truth
│   └── 构建 peer_snapshot
├── Stage 4: Decision lane (含 peer_snapshot)
└── Stage 5: Package build
    ├── 构建 transcript_packet
    ├── 构建 primary_data_packet
    └── 输出 package_payload (含 peer_snapshot, transcript_packet, primary_data_packet)
```

---

## 外部 Provider 状态

### 已实现但需 API Key

| Provider | 环境变量 | 当前状态 |
|----------|----------|----------|
| FMP (SEC filings, earnings) | `FMP_API_KEY` | 已检测，未配置时 graceful fallback |
| Alpha Vantage | `ALPHA_VANTAGE_API_KEY` | 已检测，未配置时 graceful fallback |

### Graceful Fallback

所有新模块在无 API Key 时都会返回确定性的降级结果：

- `peer_snapshot`: 返回空的 peers 列表 + 可用的 valuation_driver 提取
- `transcript_packet`: `provider: "disabled"`, `available: false`, 含 disabled_reason
- `primary_data_packet`: `primary_sources_found: false`, 含 promotion_enrichment

---

## 验收命令

### 运行新模块测试

```bash
# WP5-7 模块测试
pytest tests/test_finbot_modules.py -v -k "PeerSnapshot or TranscriptProvider or PrimaryDataEnrich"

# 完整 finbot 测试
pytest tests/test_finbot.py -v
```

### 检查 artifact 生成

```bash
# 查看 opportunity_deepen 产出
ls -la artifacts/finbot/opportunities/<candidate_id>/
```

预期新增文件：
- `peer_snapshot.json` (在 latest.json 内)
- `transcript_packet.json` (在 latest.json 内)
- `primary_data_packet.json` (在 latest.json 内)

---

## 未完成项

1. **Dashboard 展示更新** — 尚未更新 `investor_opportunity_detail.html` 来展示新的 peer_snapshot / transcript 数据
2. **真实 API 集成** — 当前是 graceful fallback，需要真实配置 FMP_API_KEY 后才能获取实际数据
3. **Expression/Decision lane prompt 增强** — 虽然 peer_snapshot 已传入，但 lane prompt 还可以进一步利用这些数据

---

## 下一步建议

1. 配置 `FMP_API_KEY` 环境变量
2. 更新 dashboard 模板展示新 artifact
3. 增强 expression lane prompt 以利用 peer_snapshot 数据
