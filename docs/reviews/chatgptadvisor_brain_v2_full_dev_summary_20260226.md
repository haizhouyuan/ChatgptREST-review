# ChatGPTAdvisor Brain V2 全量开发记录、过程与最终效果（会话历史汇总）

日期：2026-02-26  
仓库：`/vol1/1000/projects/ChatgptREST`  
基线：`master@49864c8`（含 PR #20）

## 1. 结论先行

`chatgptadvisor brain` 已从 V1（wrapper 增强 + 一等入口）演进到 V2（orchestrate 控制面 + run/step/lease/event 状态机 + gate/retry/degrade + replay/takeover + OpenClaw 协议接入）。

当前最终形态（按已合并提交）是：

1. 提供完整顾问一等 API 与 MCP 入口。
2. 支持 `execute=true && orchestrate=true` 的控制平面运行。
3. 支持 run 级别可观测、可回放、可人工接管。
4. 对 crosscheck 路由、写操作门禁、参数安全做了生产化约束。
5. 关键回归测试覆盖已建立，并在本次复核中通过（55/55）。

## 2. V1 -> V2 边界定义

### V1（2026-02-24）

核心能力：

1. wrapper 层能力完善：`prompt_refine`、`question_gap_check`、`channel_strategy(_trace)`、`answer_contract`。
2. 建立一等入口：`POST /v1/advisor/advise` + MCP `chatgptrest_advisor_advise`。
3. 安全与语义加固：forbidden/unknown agent options、stateless plan、write guards、deterministic execute。

关键提交：

1. `bf028e1` `feat(ops): add wrapper v1 with dual-review hardening and tests`
2. `396ef0d` `fix(ops): harden advisor identity repair and followup turn guard`
3. `058d130` `feat(advisor): add first-class REST and MCP advisor entrypoints`
4. `e8d4023` `fix(advisor): enforce safe options and non-blocking stateless plan mode`
5. `ca0ad6a` `fix(api): unify write guards and make advisor execute deterministic`
6. `85abc2a` `feat(client): add action_hint, route trace, and timeout-cancel policy`

### V2（2026-02-25）

核心能力：

1. Orchestrate 控制面：新增 `kind=advisor.orchestrate`。
2. 状态存储模型：`advisor_runs / advisor_steps / advisor_leases / advisor_events`。
3. gate/retry/degrade 流程与事件化审计。
4. replay、takeover、artifacts 一整套 run 运维接口。
5. OpenClaw MCP 协议桥接（spawn/send/status）。

关键提交：

1. `867bb4a` `feat(advisor): add orchestrate run state and APIs`
2. `bf9a64e` `feat(advisor): complete issue16 orchestration gaps`
3. `add9a1c` `fix: close 24h advisor/worker issue gaps and harden retries`

## 3. 关键时间线（按提交）

| 时间 (CST) | 提交 | 主题 | 关键落地 |
|---|---|---|---|
| 2026-02-24 13:14 | `bf028e1` | Wrapper V1 | 新增 `ops/chatgpt_wrapper_v1.py` 与完整测试 |
| 2026-02-24 15:24 | `396ef0d` | 兼容/身份修复 | followup guard、identity repair 加固 |
| 2026-02-24 15:39 | `058d130` | 一等入口 | `routes_advisor.py` + MCP advisor 工具 |
| 2026-02-24 15:53 | `e8d4023` | 安全/无阻塞计划态 | safe options、plan mode stateless |
| 2026-02-24 23:21 | `ca0ad6a` | 写门禁统一 | write guards 统一，execute 语义确定化 |
| 2026-02-25 01:32 | `85abc2a` | 客户端体验 | `action_hint`、`route_decision`、timeout/cancel 策略 |
| 2026-02-25 12:03 | `867bb4a` | V2 核心上线 | run state + API + executor + DB schema |
| 2026-02-25 14:02 | `bf9a64e` | Issue16 闭环 | gates/openclaw/replay/takeover 完整闭环 |
| 2026-02-25 23:50 | `add9a1c` | 24h 缺口修复 | advisor/worker/MCP 兼容与重试加固 |

对应合并节点：

1. `9fa673e`（Merge PR #17）合入 orchestrate 主能力。
2. `49864c8`（Merge PR #20）合入 24h 缺口封口与稳态加固。

## 4. 代码层最终形态（V2）

### 4.1 API 与契约

`docs/contract_v1.md` 已覆盖以下能力：

1. `POST /v1/advisor/advise`
2. `GET /v1/advisor/runs/{run_id}`
3. `GET /v1/advisor/runs/{run_id}/events`
4. `GET /v1/advisor/runs/{run_id}/replay`
5. `POST /v1/advisor/runs/{run_id}/takeover`
6. `GET /v1/advisor/runs/{run_id}/artifacts`

核心语义：

1. `execute=false` 仅做顾问规划，不落下游作业。
2. `execute=true` 创建下游 ask 作业并快速返回。
3. `execute=true && orchestrate=true` 创建控制面作业并返回 `run_id + orchestrate_job_id`。

### 4.2 控制面执行链路

主要实现文件：

1. `chatgptrest/api/routes_advisor.py`
2. `chatgptrest/executors/advisor_orchestrate.py`
3. `chatgptrest/core/advisor_runs.py`
4. `chatgptrest/core/advisor_gates.py`
5. `chatgptrest/core/db.py`
6. `chatgptrest/integrations/openclaw_adapter.py`

执行路径：

1. `advisor_advise` 归一化请求并创建 orchestrate 父作业。
2. `AdvisorOrchestrateExecutor` 分发 ask 子作业，写 step/lease/event。
3. run reconcile 阶段按 gate 结果决定 `SUCCEEDED / RETRY / DEGRADED`。
4. 可通过 `replay` 重放事件重建快照。
5. 可通过 `takeover` 进入人工接管与补偿态。

### 4.3 OpenClaw 协议接入

`openclaw_adapter.py` 已接入：

1. `sessions_spawn`
2. `sessions_send`
3. `session_status`

策略：

1. `openclaw_required=false`：失败可降级继续。
2. `openclaw_required=true`：失败触发受控降级（不默默吞错）。

### 4.4 MCP 入口（当前）

`chatgptrest/mcp/server.py` 的 advisor 工具支持：

1. `mode / orchestrate / quality_threshold / crosscheck / max_retries`
2. `agent_options` 兼容桥（旧客户端可通过 `advisor_*` 键透传）
3. 字符串 JSON 的 `context/agent_options` 归一化

## 5. 开发过程与验证过程

### 5.1 外部双审驱动（V1 起点）

依据文档 `docs/reviews/wrapper_v1_dual_review_devlog_20260224.md`：

1. ChatGPT Pro 与 Gemini Deep Think 双审并行。
2. 建议吸收后落地到 wrapper 与测试。
3. 保持“最小侵入，不改核心架构”策略，先建立稳定入口。

### 5.2 契约化与可运维化（V2 主体）

依据以下文档完成演进：

1. `docs/reviews/advisor_orchestrate_shadow_rollout_report_20260225.md`
2. `docs/reviews/advisor_orchestrate_rollback_drill_report_20260225.md`

过程上采用了：

1. 默认 `orchestrate=false` 的灰度策略。
2. 显式 OpenClaw URL 才启用协议链路。
3. 回滚演练覆盖“请求级关闭、提交级拦截、版本回退”三级。

### 5.3 全路由 E2E 与客户端交互改进

相关文档：

1. `docs/reviews/antigravity_router_e2e_matrix_20260224.md`
2. `docs/reviews/router_e2e_full_matrix_investment_agents_20260224.md`
3. `docs/reviews/client_interaction_optimization_todo_20260224.md`

结论：

1. 路由矩阵与有界等待/cancel 的行为被纳入可重复实验脚本。
2. CLI 长轮询超时从“硬失败”提升为“可恢复状态回传”。

## 6. 最终效果（从客户端视角）

截至本次汇总，客户端可稳定获得的能力：

1. 顾问规划与执行分离（plan-only / execute）。
2. 可追踪 run 生命周期与 step 尝试历史。
3. gate 失败可自动重试，重试耗尽可受控降级。
4. 降级 run 可人工接管并保留补偿证据。
5. replay 可从事件流重建快照，支持审计与故障复盘。
6. MCP 侧可以携带更完整 advisor 参数（含兼容桥）。

## 7. 测试与复核结果（本次复核）

执行命令：

```bash
./.venv/bin/pytest -q \
  tests/test_advisor_api.py \
  tests/test_advisor_orchestrate_api.py \
  tests/test_advisor_runs_replay.py \
  tests/test_openclaw_adapter.py \
  tests/test_mcp_advisor_tool.py \
  tests/test_wrapper_v1.py
```

结果：通过（55/55）。

按模块统计（collect-only）：

1. `test_advisor_api.py`: 9
2. `test_advisor_orchestrate_api.py`: 5
3. `test_advisor_runs_replay.py`: 2
4. `test_mcp_advisor_tool.py`: 2
5. `test_openclaw_adapter.py`: 3
6. `test_wrapper_v1.py`: 34

## 8. 当前工作区状态（未提交改动）

复核时发现 `master` 上存在未提交改动（dirty WIP）：

1. `chatgptrest/api/routes_advisor.py`
2. `chatgptrest/mcp/server.py`
3. `ops/chatgpt_wrapper_v1.py`
4. `tests/test_advisor_api.py`
5. `tests/test_mcp_advisor_tool.py`
6. `tests/test_wrapper_v1.py`

WIP 方向（摘要）：

1. crosscheck 降级时 `ok` 从 `True` 改为 `False`，与 `degraded_job_created` 语义更一致。
2. MCP advisor 增强 `context/agent_options` 字符串 JSON 兼容与 `advisor_*` 桥接。
3. wrapper 追加“不要联网调研/不做调研”类中英文否定规则。

说明：这些变更已通过上述测试集，但尚未形成新的已合并提交，不属于“已发布版本事实”。

## 9. 关于“Gemini CLI MCP 是否属于本次工作”

结论：不属于 `chatgptadvisor brain V2` 主线交付。

1. V2 主线围绕 advisor 控制面、状态机、gate/replay/takeover、OpenClaw 适配。
2. 仓库中存在 Gemini Web 相关稳定性修复与路由验证，但“Gemini CLI MCP”不是本次 V2 命名范围内的主交付件。

## 10. 证据清单（可直接追溯）

### 提交与合并

1. `bf028e1`, `396ef0d`, `058d130`, `e8d4023`, `ca0ad6a`, `85abc2a`, `867bb4a`, `bf9a64e`, `add9a1c`
2. 合并节点：`9fa673e`（PR #17）, `49864c8`（PR #20）

### 文档

1. `docs/reviews/wrapper_v1_dual_review_devlog_20260224.md`
2. `docs/reviews/advisor_orchestrate_shadow_rollout_report_20260225.md`
3. `docs/reviews/advisor_orchestrate_rollback_drill_report_20260225.md`
4. `docs/reviews/antigravity_router_e2e_matrix_20260224.md`
5. `docs/reviews/router_e2e_full_matrix_investment_agents_20260224.md`
6. `docs/reviews/client_interaction_optimization_todo_20260224.md`
7. `docs/contract_v1.md`

### 关键实现

1. `chatgptrest/api/routes_advisor.py`
2. `chatgptrest/executors/advisor_orchestrate.py`
3. `chatgptrest/core/advisor_runs.py`
4. `chatgptrest/core/advisor_gates.py`
5. `chatgptrest/core/db.py`
6. `chatgptrest/integrations/openclaw_adapter.py`
7. `chatgptrest/mcp/server.py`
8. `chatgptrest/worker/worker.py`

---

本文件是“整个会话历史 + 仓库事实”的落盘汇总，后续若需可以再补一份“只含已合并版本、不含 dirty WIP”的发布口径版。
