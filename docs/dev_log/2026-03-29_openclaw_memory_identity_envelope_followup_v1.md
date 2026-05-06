# 2026-03-29 OpenClaw Memory Identity Envelope Follow-up v1

## 背景

前一轮已经把 `memory.capture` 主链和 public agent surface 的 capture receipt 暴露出来，但四端联验里仍有一个前端侧 identity 缺口：

- OpenClaw 的 plugin hook context 没有稳定暴露 `sessionId / agentAccountId / threadId`
- `openmind-memory` 插件虽然读取了 `ctx.sessionId`，但 `thread_id` 仍用 `sessionId` 兜底，没有优先使用真实 thread

这会导致 owner-side capture API 已经可验，但前端上报的 identity lineage 仍可能退化成 partial。

## 本轮动作

### 1. OpenClaw 前端 identity envelope 补齐

单独在 OpenClaw 仓提交：

- commit: `d13e0c43f`

改动要点：

- `PluginHookAgentContext` 增加 `sessionId / threadId / agentAccountId`
- `OpenClawPluginToolContext` 增加 `sessionId / threadId`
- `runEmbeddedAttempt(...)` 的 `before_agent_start / agent_end` 改为复用统一 helper 构造 hook context
- `createOpenClawCodingTools(...)` / `createOpenClawTools(...)` 把 `agentSessionId / agentThreadId` 传入 plugin tool context

这样自动 recall/capture 和手动 recall/capture 都能拿到同一组 identity 字段。

### 2. ChatgptREST 插件端 `thread_id` 改为优先真实线程

本仓改动：

- `openclaw_extensions/openmind-memory/index.ts`

改动要点：

- `ResolveContextParams` 增加 `threadId`
- `captureTexts(...)` 增加 `threadId`
- `buildResolveContextRequest(...)` 与 `captureTexts(...)` 均改为：
  - 优先使用 `threadId`
  - 仅在缺失时回退到 `sessionId`
- 自动 hook 和手动 tool 两条路径都开始透传 `ctx.threadId`

## 结果

本轮之后，OpenClaw -> ChatgptREST 的 memory identity envelope 至少满足：

- `session_key`
- `session_id`（通过 ChatgptREST capture route 的 `session_key -> session_id` 映射）
- `account_id`
- `agent_id`
- `thread_id` 优先真实 thread

这不能单独宣布系统 complete，但确实收掉了之前最明显的“前端拿不到 / 插件不用真实 thread”两处缺口。

## 验证

### OpenClaw

```bash
./node_modules/.bin/vitest run \
  src/agents/pi-embedded-runner.run-hook-context.test.ts \
  src/agents/openclaw-tools.plugin-context.test.ts

./node_modules/.bin/vitest run \
  src/plugins/tools.optional.test.ts \
  src/agents/openclaw-tools.session-status.test.ts
```

### ChatgptREST

```bash
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_openclaw_cognitive_plugins.py

PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_routes_agent_v3.py -k 'memory_capture_receipt' \
  tests/test_agent_mcp.py -k 'memory_capture_request'
```

## 未完成

仍未完成的不是 owner-side capture API，而是 system-side 联验闭环：

- 需要前端真实终端再次产出 live capture receipt
- 需要四端联验板把 `memory_capture_status` 读成正式通过
- `partial provenance` 仍保留兼容模式，尚未全面切 strict-default
