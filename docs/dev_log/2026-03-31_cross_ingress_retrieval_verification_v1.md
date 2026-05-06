---
title: cross ingress retrieval verification
version: v1
status: active
updated: 2026-03-31
owner: Codex
---

# Cross Ingress Retrieval Verification v1

## 1. 结论

`codex` 与 `claude_code` 两条 identity 已通过真实运行中的 `/v2/context/resolve` 验证，能跨 session 召回 imported `ready` seeds；`manual_review_required` 项不会误进 active context。

本轮用于稳定 live 召回窗口的代码提交是：

- `5d050d3` `Expand work memory query recall window`

## 2. 现场核验范围

- API target: `http://127.0.0.1:18713/v2/context/resolve`
- memory DB: `/home/yuanhaizhou/.openmind/memory.db`
- service state:
  - `chatgptrest-api.service = active`
  - `chatgptrest-worker-send.service = active`
  - `chatgptrest-worker-wait.service = active`

原始 artifact：

- `docs/dev_log/artifacts/cross_ingress_retrieval_verification_20260331/report_v1.json`
- `docs/dev_log/artifacts/cross_ingress_retrieval_verification_20260331/report_v1.md`

## 3. 关键检查

| check | identity | query | result |
| --- | --- | --- | --- |
| `codex_fz4_ready_seed_visible` | `codex` | `FZ4 当前唯一口径是最小投入方案吗？` | `ok` |
| `claude_code_104_ready_seed_visible` | `claude_code` | `104 模组代工当前应按什么状态推进？` | `ok` |
| `manual_review_items_stay_out_of_active_context` | `codex` | `九号软模合同谈判当前处于什么阶段？FZ4 仍处软模阶段吗？` | `ok` |
| `missing_thread_degrades_instead_of_silent_wrong_behavior` | `claude_code` | `FZ4 当前唯一口径是什么？` | `ok` |

## 4. 验证到的对象

`codex` 可见：

- `AP-002` `两轮车车身量产线规划（FZ4 最小投入）`
- `DCL-20260124-FZ4-MINCAPEX`

`claude_code` 可见：

- `AP-001` `104 模组代工执行准备`
- `DCL-20260121-104-STAGEGATE`

明确未进入 Active Context 的 manual-review 项：

- `PRJ-2026-007`
- `DCL-20260316-FZ4-SOFTMOULD`

## 5. 降级行为

当 `thread_id` 缺失时，系统返回的是可见降级，不是 silent wrong behavior：

- `degraded = true`
- `degraded_sources = ['work_memory_identity_partial']`
- `identity_gaps = ['missing_thread_id']`

## 6. 当前判断

cross-ingress retrieval 这一环已经达到 owner-side 闭环要求：

- imported `ready` seeds 可被真实入口召回
- explainability 清楚
- manual review 与 active context 已正确隔离
- identity 缺口会显式降级
