# 2026-04-03 Planning Agent Total Plan Execution Master v21

## 1. v21 相比 v20 的关键变化

`v21` 不是新阶段，而是把 `v20` 里这批 session/job 对齐修复补到更完整。

新增成立的事实：

1. send-phase root Gemini URL 的误投影修复，已经从精确 `/app` 扩到 canonical Gemini base-app variants
2. 真实 Gemini thread URL 与已存在 `conversation_id` 的 cooldown 现在也有保护性测试
3. 这批 truthfulness 修复的口径已经和代码对齐，不再依赖说得过满的文档表述

## 2. 到 v21 为止的当前状态

### 2.1 已经被拿下的部分

当前 planning task plane 已经同时具备：

1. `OpenClawBot` 主链 acceptance 基线
2. owner guard / identity propagation
3. planning task list / task_get / session_get plugin surface
4. query surface 摘要化与 cross-session fail-closed
5. `cancelled` 映射补齐
6. live completion gate 的真实 fail-closed
7. send-phase Gemini base-app URL 的误投影修复
8. 对真实 Gemini thread 的非误伤验证

### 2.2 当前剩余主问题

到这一步之后，真正还没被拿下的是：

1. Gemini 上传 UI 路径：
   - `Gemini upload menu button not found`
2. `OpenClawBot live completion gate` 还没真正 green
3. `/v3/agent/session/{session_id}` 的更大 server-side boundary 仍偏宽
4. read-time refresh 仍是 phase-1 设计债

## 3. v21 的当前判断

到 `v21` 为止，我的独立判断仍然是：

1. 当前主链已经从“入口/query/gate 是否可信”推进到“provider send-phase 与 session truth 是否一致”
2. 这说明 phase-1 现在不该继续把主要精力投在：
   - 新 task type
   - 新 surface
   - 更多抽象计划
3. 当前最该投的是：
   - Gemini upload UI blocker
   - live green
   - 任务真相层与 session truth 的进一步对齐

## 4. v21 的 Next 3

### 4.1 Next 1

查并修 `Gemini upload menu button not found`

### 4.2 Next 2

重跑 `OpenClawBot live completion gate`，确认它不再因为 session 假进展而拖长

### 4.3 Next 3

在 live 绿之前，不继续扩 task type，转向：

1. `work memory ingress/writeback`
2. policy layer 的第一条真实接线

## 5. 一句话结论

`v21` 的核心变化是：

> planning task plane 当前已经把 send-phase Gemini base-app URL 的误投影修复补到 canonical 语义，并新增了真实 thread 非误伤验证；下一批的关键仍不是新规划，而是 Gemini 上传 UI 与 live green。
