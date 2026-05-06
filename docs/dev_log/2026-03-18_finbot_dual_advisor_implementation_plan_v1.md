---
title: "2026-03-18 finbot 双顾问实施计划 v1"
source: "ChatGPT Pro + Gemini Deep Think"
author:
  - "[[CODEX]]"
published:
  created: 2026-03-18
description: "把双顾问结果收敛成可直接交给 Claude Code 的施工单。"
tags:
  - "finbot"
  - "finbotfree"
  - "implementation-plan"
  - "dual-advisor"
---

# finbot 双顾问实施计划 v1

## 背景

本计划基于同一份 repo-grounded 提问得到的双顾问结果：

- ChatGPT Pro job: `21b48351298d4122a002886be77c6648`
- Gemini Deep Think job: `3ea2a253f63743c19ea880e924206703`

两边的有效共识不是“再发明一堆 finance skill 名字”，而是：

1. 继续坚持单入口、单 `finbot`、内部多 lane
2. 优先补一手证据、反证、政策闸门
3. `finbotfree` 必须收口成 promotion tier，而不是最终决策器
4. 暂缓组合优化、多人格 agent mesh、全网情绪流监听

## 本轮裁定

### 先做

1. claim exact evidence binding
2. skeptic counterevidence packet
3. posture guard + paid/free promotion gate
4. finbotfree promotion packet

### 延后

1. peer snapshot / valuation discipline
2. earnings call transcript provider
3. 更重的一手数据 vendor 接入

原因很简单：如果 claim 还没绑到原文片段、skeptic 还没拿到真正反证、free tier 还能凭 narrative 自升 paid，那么 expression 做得越漂亮，只会越像高质量噪音。

## 非目标

这轮明确不做：

1. `Portfolio Optimizer`
2. `Position Sizing`
3. 多常驻 agent 群聊
4. 7x24 社交媒体 / 新闻情绪全量监听
5. 再做一版更会写 narrative 的 markdown

## 实施范围

### 真实插点

本计划只围绕当前已存在的 seam 动手：

- `chatgptrest/finbot.py`
  - `_build_claim_lane_prompt()` at `1866`
  - `_build_skeptic_lane_prompt()` at `1901`
  - `_fetch_market_truth()` at `1194`
  - `_should_promote_research_package()` at `2150`
  - `opportunity_deepen()` at `2407`
  - `theme_batch_run()` at `2956`
  - `daily_work()` at `3072`
- `chatgptrest/finbot_modules/`
  - 现有：`claim_logic.py`, `market_truth.py`, `source_scoring.py`
  - 新增模块应继续放在这里，不要另起新目录

## 任务包

### WP1. Claim Evidence Binding

目标：把 claim 从“有 source name”提升到“有 exact excerpt + artifact binding”。

新增文件：

- `chatgptrest/finbot_modules/evidence_binding.py`

建议导出函数：

- `build_claim_evidence_bindings(...)`
- `bind_claims_to_artifacts(...)`

输入：

- `candidate_id`
- `claim_objects`
- `citation_objects`
- `related_sources`
- `source_scores`
- 已刷新 artifact 文本

输出 artifact：

- `claim_evidence_bindings.json`

最小 schema：

```json
{
  "generated_at": 0,
  "candidate_id": "xxx",
  "bindings": [
    {
      "claim_id": "claim_1",
      "source_id": "src_1",
      "artifact_id": "artifact_1",
      "excerpt": "exact source excerpt",
      "excerpt_hash": "sha256",
      "stance": "support|context|weaken",
      "primaryness": "primary|secondary",
      "missing_primary_evidence": false
    }
  ]
}
```

代码修改：

1. 在 `opportunity_deepen()` 中，`claim_result` 之后、`skeptic_result` 之前插入 evidence binding
2. `_build_claim_lane_prompt()` 要要求 top load-bearing claims 返回更稳定的 anchor 提示
3. `_enrich_claim_ledger_with_sources()` 不允许无 source 时静默伪装成“有锚点但只有 fallback narrative”

本轮要求：

- 只覆盖 top 3 load-bearing claims
- 找不到 exact excerpt 时，显式写 `missing_primary_evidence=true`
- 不为了“看起来完整”生成伪 binding

### WP2. Skeptic Counterevidence Packet

目标：让 skeptic 吃到真正的反证包，而不是 claim 的镜像推理。

新增文件：

- `chatgptrest/finbot_modules/negative_evidence.py`

建议导出函数：

- `build_counterevidence_packets(...)`

输入：

- `claim_objects`
- `claim_evidence_bindings`
- `kol_summary`
- `related_sources`
- 可用的一手 artifact 文本

输出 artifact：

- `counterevidence_packets.json`

最小 schema：

```json
{
  "generated_at": 0,
  "candidate_id": "xxx",
  "packets": [
    {
      "claim_id": "claim_1",
      "source_id": "src_2",
      "artifact_id": "artifact_2",
      "excerpt": "counter evidence excerpt",
      "stance": "refute|weaken|no_refute_found",
      "confidence": "low|medium|high"
    }
  ]
}
```

代码修改：

1. `_build_skeptic_lane_prompt()` 增加 `claim_evidence_bindings` 和 `counterevidence_packets` 上下文
2. `opportunity_deepen()` 中把 `_run_kol_suite()` 的产物真正喂给 skeptic 路径
3. skeptic lane 输出中的 `risk_register`、`disconfirming_signals` 要优先引用 packet，而不是重复概括 claim narrative

本轮要求：

- 先只做三类反证：方向相反、竞争替代、官方口径不支持
- 先覆盖 top 3 load-bearing claims
- `no_refute_found` 也要落盘，不能静默缺失

### WP3. Posture Guard

目标：把“能不能升级、能不能给积极 posture”改成 deterministic policy，不只看 LLM narrative。

新增文件：

- `chatgptrest/finbot_modules/posture_guard.py`

建议导出函数：

- `evaluate_posture_guard(...)`

输出 artifact：

- `policy_result.json`

最小 schema：

```json
{
  "generated_at": 0,
  "candidate_id": "xxx",
  "max_allowed_posture": "watch|prepare_candidate|deepen_now|starter",
  "promote_to_paid": false,
  "blocked_reasons": [],
  "missing_evidence": [],
  "missing_counterevidence": []
}
```

代码修改：

1. `package_payload` 组装完成后、artifact 写盘前，执行 posture guard
2. `_should_promote_research_package()` 不再只看 `current_decision in {"deepen_now", "prepare_candidate"}`
3. free tier 的 raw `current_decision` 不能直接触发 paid promotion

MVP 规则：

1. load-bearing claim 没一手证据，`max_allowed_posture <= watch`
2. 没显式 falsifier coverage，不能给 `starter`
3. free tier 默认最多到 `prepare_candidate`

### WP4. finbotfree Promotion Packet

目标：把 finbotfree 收口成 promotion tier，不再默认吐 full dossier。

新增文件：

- `chatgptrest/finbot_modules/promotion_packet.py`

建议导出函数：

- `build_promotion_packet(...)`

输出 artifact：

- `promotion_packet.json`

最小 schema：

```json
{
  "generated_at": 0,
  "candidate_id": "xxx",
  "why_now": "short summary",
  "first_hand_source_to_check": [],
  "novelty_hint": [],
  "promote_bool": false,
  "blocked_by": []
}
```

代码修改：

1. `daily_work()`
2. `theme_batch_run()`
3. 相关 watchlist / theme radar 入口
4. `_build_research_package_item()`

free tier 行为要求：

1. 默认不生成 final investment posture
2. 默认不驱动 paid promotion，除非 posture guard 放行
3. 默认输出 promotion packet，而不是完整 narrative dossier

## 暂缓包

### WP5. Peer Snapshot / Valuation Discipline

这项是下个 sprint，不是这轮。

原因：

1. 当前最短板是 evidence plumbing，不是表达排序
2. 没有 claim exact binding 和 counterevidence 之前，peer ranking 只能把 narrative 做漂亮

保留 seam：

- `_fetch_market_truth()`
- expression stage in `opportunity_deepen()`
- 可新增 `chatgptrest/finbot_modules/peer_snapshot.py`

### WP6. Earnings Call Transcript Provider

这项也延后到下一轮。

原因：

1. 需要外部 API key / cost 决策
2. 会引入长文本 ingestion 和新 vendor 依赖
3. 在前四项没落地前，接进来也很难被现有 schema 正确消费

先预留接口，不要求本轮真正接入 FMP 或别的 provider。

## 测试要求

本轮必须补测试，不能只做 happy path。

至少新增或扩展：

- `tests/test_finbot.py`
- `tests/test_finbot_dashboard_service_integration.py`
- 如有必要新增：
  - `tests/test_finbot_evidence_binding.py`
  - `tests/test_finbot_posture_guard.py`

必测场景：

1. claim 找不到 exact excerpt 时，显式标记 `missing_primary_evidence`
2. skeptical packet 为 `no_refute_found` 时仍正常落盘
3. posture guard 能把 raw `deepen_now` 降级
4. free tier 不再直接 promotion
5. dashboard / package payload 能看见 `blocked_reasons` 与 `missing_*`

## 验收标准

### 功能验收

1. `opportunity_deepen()` 跑完后稳定产出：
   - `claim_evidence_bindings.json`
   - `counterevidence_packets.json`
   - `policy_result.json`
2. `daily_work()` / `theme_batch_run()` 跑完后，free tier 默认产出：
   - `promotion_packet.json`
3. free tier 不再只靠 LLM narrative 自动升 paid
4. paid tier 的 posture 可以被 policy 降级

### 质量验收

1. top 3 load-bearing claims 每条都有 evidence 或显式 missing flag
2. skeptic 输出里能看到真正挂回 claim 的反证，而不是套话
3. dashboard 至少能展示：
   - `missing_primary_evidence`
   - `blocked_reasons`
   - `promote_to_paid`

### 回归验收

至少执行：

```bash
./.venv/bin/pytest -q \
  tests/test_finbot.py \
  tests/test_finbot_dashboard_service_integration.py
```

如果新增独立测试文件，也必须一起跑。

## 给 Claude Code 的执行提示词

把下面整段交给 CC：

```md
你要在当前 ChatgptREST 仓库内实现 finbot 下一轮最小可信升级。

不要发明新产品路线，不要改成多 agent，不要做 portfolio optimizer，不要接重型新 vendor。

本轮只做 4 个任务包：
1. claim_evidence_bindings.json
2. counterevidence_packets.json
3. policy_result.json
4. promotion_packet.json

真实插点：
- chatgptrest/finbot.py
  - _build_claim_lane_prompt
  - _build_skeptic_lane_prompt
  - _should_promote_research_package
  - opportunity_deepen
  - theme_batch_run
  - daily_work
- chatgptrest/finbot_modules/

要求：
- 新逻辑尽量模块化，新增到 finbot_modules，不要继续把所有逻辑塞回 finbot.py
- free tier 默认不再生成 final posture，也不再直接 promotion
- load-bearing claim 找不到一手证据时，必须显式 missing flag
- skeptical 反证必须挂回 claim_id
- policy guard 能降级 raw current_decision

本轮不做：
- peer snapshot / valuation discipline
- transcript provider 实接
- 大规模 UI 改造

必须补测试。

交付物：
1. 代码
2. 新 artifact schema
3. 测试
4. 一份 walkthrough 文档，解释为什么这么插、验收怎么跑

完成后给我：
- 改动摘要
- 跑过的测试
- 还有哪些被明确延后
```

## 我自己的验收重点

等 CC 做完后，我重点卡 6 件事：

1. 有没有真的新增 4 个 artifact，而不是只在 markdown 里提到
2. 有没有把 logic 拆进 `finbot_modules/`，而不是把 `finbot.py` 再膨胀一截
3. `missing_primary_evidence` 是否真能从 runtime 出现
4. free tier promotion 是否真被 policy guard 接管
5. 测试是不是覆盖了降级和 no-refute 路径
6. walkthrough 是否把 deferred scope 写清，避免下一轮又混进 peer snapshot / transcript provider
