# 2026-04-03 Planning Agent Total Plan Execution Master v20

## 1. v20 相比 v19 的关键变化

`v20` 的关键变化不是“把主链做绿了”，而是把当前 live 真实问题再次向前推进了一层。

新增成立的事实：

1. `fetch failed` 不再是当前唯一 mouthpiece。
2. 最新 live trace 已经能真实进入 `gemini_web.ask` send-phase。
3. 当前更靠前的真实 blocker 变成：
   - `Gemini upload menu button not found`
4. `job/session` 状态对齐被识别为新的 phase-1 真问题，并已做第一批窄修复：
   - 根页面 Gemini URL + 无 `conversation_id` 不再自动当成“已有可继续线程”的证据。

## 2. 到 v20 为止的当前状态

### 2.1 已经被拿下的部分

当前 planning task plane 已经同时具备：

1. `OpenClawBot` 主链 acceptance 基线
2. owner guard / identity propagation
3. planning task list / task_get / session_get plugin surface
4. query surface 摘要化与 cross-session fail-closed
5. `cancelled` 映射补齐
6. live completion gate 的真实 fail-closed
7. send-phase root Gemini URL 的误投影修复

### 2.2 当前剩余主问题

到这一步之后，真正还没被拿下的是：

1. Gemini 上传 UI 路径：
   - `Gemini upload menu button not found`
2. `OpenClawBot live completion gate` 还没真正 green
3. `/v3/agent/session/{session_id}` 的更大 server-side boundary 仍偏宽
4. read-time refresh 仍是 phase-1 设计债

## 3. v20 的当前判断

到 `v20` 为止，我的独立判断是：

1. 当前主链已经从“入口/query/gate 是否可信”推进到“provider send-phase 与 session truth 是否一致”。
2. 这说明 phase-1 现在不该继续把主要精力投在：
   - 新 task type
   - 新 surface
   - 更多抽象计划
3. 当前最该投的是：
   - Gemini upload UI blocker
   - live green
   - 任务真相层与 session truth 的进一步对齐

## 4. v20 的 Next 3

### 4.1 Next 1

查并修 `Gemini upload menu button not found`。

### 4.2 Next 2

重跑 `OpenClawBot live completion gate`，确认它不再因为 session 假进展而拖长。

### 4.3 Next 3

在 live 绿之前，不继续扩 task type，转向：

1. `work memory ingress/writeback`
2. policy layer 的第一条真实接线

## 5. 一句话结论

`v20` 的核心变化是：

> planning task plane 当前已经不仅是 “入口/query/gate 是否可信” 的问题，而是真正进入了 provider send-phase 和 session truth 对齐问题；下一批的关键不再是旧的 `fetch failed`，而是 Gemini 上传 UI 与 live green。
