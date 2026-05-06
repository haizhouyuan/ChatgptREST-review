# OpenMind Production-Readiness Wave Independent Review v1

Date: 2026-04-09
Reviewer: Claude (GAC independent red-team)
Scope: Codex 的 PR-1 到 PR-8 全量执行 + gap analysis plan（commits 53812f9d 到 1cef7bf7，plan commit 1557ad2c）

## 1. 总体判断

用户的独立定性是准确的：

> contracted canary-readiness achieved; full go-live not achieved; standalone OpenMind runtime still not a fact

我的独立验证支持这个结论。Codex 这轮做了大量实质工作，但标题"production readiness full execution"确实叫大了。

验收结论：**canary-readiness 通过。production-grade 不通过。gap analysis plan 质量高，可以作为后续执行的 canonical 依据。**

## 2. 工程执行验证

### 2.1 提交链完整性

8 个 PR commit + 1 个 closeout commit + 1 个 gap analysis commit 全部存在于 git log 中：

```
53812f9d → fa728e86 → e43d59d9 → b2305fdc → e0d01a00 → aac5e952 → bb348ddb → 7628629e → 1cef7bf7 → 1557ad2c
```

每个 commit 都有对应的 artifact 和/或 contract 文档。

### 2.2 Canary scorecard 可复现性

用户独立复跑的 artifact（20260409T080849Z）与 Codex 原始 artifact（20260409T063012Z）结论一致：

- `decision = launch_canary_watch`
- `packet = pass, recall = pass, promotion = warn, crystal = pass`
- `fail_domains = [], warn_domains = ["promotion"]`
- `go_live_ready = false`

这证明 scorecard 不是一次性伪造，而是可复现的。

### 2.3 Release flags 验证

`routes_agent_v3.py:131-136` 确认两个 env flag 存在：

- `CHATGPTREST_ENABLE_WAKEUP_PACKET_PROJECTION`（default=True）
- `CHATGPTREST_ENABLE_CRYSTALLIZED_LEARNING_PACKET_PROJECTION`（default=True）

rollback 路径清晰：设为 0 → 重启服务 → packet receipt 反映 disabled 状态。这是正确的 feature flag 设计。

### 2.4 Regression bundle 验证

`openmind_production_regression_20260409T060408Z.json` 显示 3 个 bundle 全部 green：

- `public_agent_packet_plane`：125 tests, 15.3s
- `memory_bridge_and_plugin_surface`：13 tests, 4.8s
- `openclaw_business_flow`：16 tests, 5.1s

### 2.5 Operator tooling 验证

三个 ops runner 存在且有实质代码：

- `ops/report_openmind_production_health.py`（445 行）
- `ops/run_openmind_production_regression.py`（140 行）
- `ops/report_openmind_canary_scorecard.py`（229 行）

配合 `docs/runbook.md` 的更新，operator 确实可以不读代码执行健康检查。

## 3. 用户三条"不同意"的独立验证

### 3.1 "production readiness full execution" 标题过强

**同意用户判断。**

当前完成的是：
- scope freeze ✓
- packet/recall/crystal/promotion 的 contract + harness + rollup ✓
- canary watch launch ✓

当前没有完成的是：
- watch window 尚未经过（7 天窗口刚启动）
- go_live_ready = false
- OpenMind repo 仍然没有独立 runtime

正确口径应该是 `canary-readiness on ChatgptREST/OpenClaw substrate`。

### 3.2 packet=pass 不等于 packet completeness

**同意用户判断。**

我在前一轮 review 中已经指出 `degraded_ratio = 1.0`。health artifact 确认：

- `success_rate = 1.0`（编译成功率）
- `degraded_ratio = 1.0`（所有 packet 都有 degraded source）
- `adjusted_degraded_ratio = 0.0`（豁免已知外部 gap 后为 0）

已知外部 gap：
- `personal_graph_empty`
- `memory_identity_missing`
- `captured_memory_identity_missing`
- `work_memory_identity_partial`

这些不是 bug，但说明 packet 的 memory/identity 层还没有真正接入。pass 的含义是"在已知 gap 被豁免的前提下通过 canary contract"。

### 3.3 crystal=pass 不等于 live learning 已运行

**同意用户判断。**

用户引用的 governance artifact 显示：
- `records_scanned = 0`
- `active_crystal_count = 0`
- `projection_mode = shadow`

crystal=pass 证明的是治理边界安全，不是 live cross-session learning 已经产生价值。

## 4. 用户四条"范围边界"的独立验证

### 4.1 cohort-scoped，不是全域

**确认。** canary scorecard 的 cohort 定义：

```json
"projects": ["shortmobility", "prs"],
"surfaces": ["/v3/agent/turn", "openmind-advisor"]
```

只覆盖 2 个项目、2 个 surface。

### 4.2 recall benchmark 仍然很小

**确认。** health artifact 显示 `case_count = 3`。3 个 case 足够做 scoped regression，不足以代表全面稳定。

### 4.3 regression 是 focused pytest bundles

**确认。** regression runner 跑的是 3 组 pytest bundle（共 ~154 tests），不是 full live traffic soak。这对 canary 足够，对 production-grade 不够。

### 4.4 OpenMind repo 仍然不是 runtime owner

**确认。** 这一点在整个 review 系列中反复验证过。openmind 的 advisor/kb/evomap 包仍然是空的 `__init__.py`。

## 5. Promotion backlog 的独立分析

health artifact 中的 promotion 数据值得单独分析：

| 指标 | 值 |
|---|---|
| total atoms | 106,108 |
| active | 814 (0.77%) |
| candidate | 6,123 (5.77%) |
| staged | 96,170 (90.6%) |
| blank promotion reason ratio | 0.0 |

staged 占比 90.6% 是结构性问题。最大的 staged-without-active 来源：

- `antigravity`: 50,765 staged, 0 active
- `planning`: 12,982 staged, 0 active
- `evomap`: 4,490 staged, 0 active
- `agent_activity`: 4,489 staged, 0 active

这些不是 bug，而是这些 source family 的 promotion pipeline 还没有被配置或触发。blank reason ratio = 0.0 说明已经处理过的 atom 都有 reason，但大量 atom 根本还没进入 promotion 流程。

promotion=warn 是诚实的，而且是当前最大的 production-grade blocker。

## 6. Gap analysis plan 的质量评估

Codex 的 gap analysis plan（`1557ad2c`）质量高于前几轮的 closeout 文档。具体优点：

1. **诚实**：明确说"current state is not enough"，列出 5 个具体原因
2. **可操作**：G0-G6 每个 phase 都有 goal、work items、acceptance criteria
3. **有序**：明确了"不要在 G1/G2 之前扩大产品声明"的约束
4. **可验证**：hard acceptance checklist 是具体的、可机器检查的条件

保留意见：

- G2（packet completeness hardening）的工作量可能被低估。`personal_graph_empty` 和 `memory_identity_missing` 不是简单的 upstream fix，而是涉及 identity propagation 的架构问题。
- G5（promotion backlog reduction）没有给出具体的 target ratio。"materially shrink" 太模糊，应该冻结一个数字（比如 staged ratio < 70% for canary-critical families）。
- G6（graduation gate）依赖 G1-G5 全部完成，但没有定义 partial graduation 的可能性。如果 G3（live crystal evidence）在 watch window 内无法完成，是否可以在 crystal=shadow 的前提下 graduate？

## 7. 我的最终定性

与用户的定性一致：

> contracted canary-readiness achieved; full go-live not achieved; standalone OpenMind runtime still not a fact

补充：

- Codex 这轮的工程执行质量是整个系列中最高的。PR-1 到 PR-8 不是空文档，每个 PR 都有代码、runner、contract、artifact 配套。
- 用户的三条"不同意"全部成立，且都有 artifact 证据支持。
- gap analysis plan 是一份高质量的可执行计划，可以作为后续工作的 canonical 依据。
- 最大的 production-grade blocker 是 promotion backlog（90.6% staged）和 packet identity gaps（degraded_ratio = 1.0）。

## 8. 对 gap analysis plan 的补充建议

### 8.1 G5 需要冻结具体 target

建议在 G5 中增加：

- canary-critical families（shortmobility, prs）的 staged ratio target：< 70%
- 非 canary-critical families 可以保持 warn，但需要有 trendable 报告

### 8.2 G6 需要定义 partial graduation 路径

如果 watch window 结束时 G3（live crystal evidence）仍然是 `records_scanned = 0`，应该允许在 `crystal=shadow` 前提下 graduate，但需要在 graduation artifact 中明确标注 crystal 仍然是 shadow-only。

### 8.3 watch-window 自动化应该是 P0

G1（watch-window automation）应该在 watch window 期间就开始执行，不要等到 window 结束后才补。否则 7 天窗口内没有 daily artifact，graduation gate 就没有时间序列证据。

### 8.4 promotion backlog 的 antigravity source 需要单独决策

antigravity 贡献了 50,765 staged atoms（占总 staged 的 52.8%）。如果这个 source 的 promotion pipeline 不打算在近期启用，应该把它从 canary-critical scope 中显式排除，而不是让它持续拉高 staged ratio。
