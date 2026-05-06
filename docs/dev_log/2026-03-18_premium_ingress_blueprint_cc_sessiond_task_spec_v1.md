# Premium Ingress Blueprint cc-sessiond Task Spec v1

日期：2026-03-18

## 目标

在 `feat/premium-ingress-blueprint-implementation` 分支上，完整实现
[2026-03-17_premium_agent_ingress_and_execution_cabin_blueprint_v1.md](/vol1/1000/worktrees/chatgptrest-premium-ingress-20260318/docs/2026-03-17_premium_agent_ingress_and_execution_cabin_blueprint_v1.md)
中与 `public agent facade` 相关的全部主线能力，并补齐可回归测试与文档。

本任务不是继续做“更薄的 facade”，而是要把 premium ingress 变成：

1. `Ask Contract / Funnel` 前置层
2. 服务端 prompt assembly
3. post-ask review + EvoMap writeback

同时保持：

- 普通 premium ask 仍走 `/v3/agent/*`
- `cc-sessiond` 仍是 slow-path execution cabin，不接管普通 premium ask 主路径

## 现状判断

当前仓内已具备但未站上正门的部件：

- `chatgptrest/workflows/funnel.py`
- `chatgptrest/advisor/graph.py`
- `chatgptrest/advisor/dispatch.py`
- `chatgptrest/advisor/task_spec.py`
- `chatgptrest/advisor/standard_entry.py`
- `chatgptrest/advisor/qa_inspector.py`
- `chatgptrest/core/thinking_qa.py`
- `chatgptrest/workflows/evomap.py`

当前缺口：

- `/v3/agent/turn` 仍直接吃自由文本 `message`
- 没有显式 ask contract schema
- 没有入口级 requirement clarification / missing-info discipline
- prompt engineering 还没服务端化成稳定 contract-driven builder
- premium ask 完成后没有统一 post-ask review / EvoMap writeback

## 必做范围

### Batch A: Ask Contract + Funnel Front Gate

为 `public /v3/agent/*` 增加最小 ask contract 能力：

- 新增 request schema / normalization 层
- 支持最小 ask contract 字段：
  - `objective`
  - `decision_to_support`
  - `audience`
  - `constraints`
  - `available_inputs`
  - `missing_inputs`
  - `output_shape`
  - `risk_class`
  - `opportunity_cost`
  - `task_template`
- 当客户端只传自由文本 `message` 时：
  - 服务端必须先做 contract synthesis / funnelization
  - 不能直接跳过 requirement clarification
- 需要明确输出：
  - `contract`
  - `contract_completeness`
  - `contract_source` (`client` / `server_synthesized`)

必须把旧 funnel/requirement analysis 真正接到 `public agent ingress` 前面，而不是只保留 advisor 内部遗留实现。

### Batch B: Server-side Prompt Assembly

新增稳定的服务端 prompt builder / template registry：

- 按 task template 组装 prompt
- 按 provider/model 特性做 adapter
- 统一注入：
  - role/perspective
  - output rubric
  - uncertainty handling
  - evidence summary
  - formatting contract

要求：

- 客户端不再需要手写核心 prompt engineering
- `/v3/agent/turn` 应接收结构化 ingress 输入，再由服务端装 prompt
- route logic 必须消费 contract/template，不只是 `goal_hint`

### Batch C: Post-Ask Review + EvoMap Writeback

每次 premium ask 结束后，自动做 review：

- `question_quality`
- `contract_completeness`
- `missing_info_detected`
- `model_fit`
- `route_fit`
- `answer_quality`
- `actionability`
- `hallucination_risk`
- `prompt_improvement_hint`
- `template_improvement_hint`

要求：

- review 结果要进入 session payload / artifact
- 同时写回 EvoMap / review artifact
- 不能只做长度门槛；至少要有结构化 review discipline

### Batch D: Surface Contract And Client Compatibility

保证以下表面保持可用：

- `POST /v3/agent/turn`
- `GET /v3/agent/session/{session_id}`
- `GET /v3/agent/session/{session_id}/stream`
- MCP:
  - `advisor_agent_turn`
  - `advisor_agent_status`
  - `advisor_agent_cancel`
- OpenClaw `openmind-advisor`

兼容要求：

- 老客户端只传 `message` 仍可工作
- 但 server 返回中应能看到 synthesized contract / review metadata
- 不允许把普通 premium ask 错误路由到 `cc-sessiond`

### Batch E: Tests

至少新增并实际跑这些测试：

- ask contract synthesis / normalization tests
- funnel front gate tests
- prompt builder tests
- post-ask review / evomap writeback tests
- `/v3/agent/*` route tests covering:
  - free-text ask
  - structured contract ask
  - deferred + stream
  - completion payload contains contract/review fields
- `advisor_agent_turn` MCP tests
- OpenClaw plugin compatibility tests

最低实际测试命令：

```bash
./.venv/bin/pytest -q \
  tests/test_routes_agent_v3.py \
  tests/test_agent_v3_routes.py \
  tests/test_agent_mcp.py \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_bi14_fault_handling.py
```

并补跑与 review / advisor runtime 直接相关的新旧测试。

## 明确禁止

- 不要把普通 `/v3/agent/turn` 改成默认进入 `cc-sessiond`
- 不要只写蓝图/文档不落代码
- 不要只补 heuristics 而不形成 ask contract / review artifacts
- 不要删除 legacy funnel 逻辑后再重造一个完全平行的新系统

## 交付物

必须提交：

- 代码实现
- 新增/更新测试
- 新版本 walkthrough 文档（`_v1.md`）
- 如有新 contract，再补 contract 文档

## 完成标准

只有满足以下条件才算完成：

- premium ask 进入执行前已形成 contract
- funnel/requirement analysis 已真正在入口前生效
- prompt engineering 已服务端化
- 每次 premium ask 都有 post-ask review artifact
- EvoMap 或等价 writeback 已接收 review signal
- tests 真实通过
- branch 干净并准备好给 Codex 审核 / 合并
