# 2026-04-03 Planning Agent Total Plan Execution Master v19

## 1. v19 相比 v18 的关键变化

`v19` 不是把 live completion 做绿了，而是把这条线从“真假不明”推进到了“结果可信”。

新增成立的事实：

1. `openmind-advisor` plugin 的 planning query surfaces 已经过一轮真正收口。
2. `planning task` GET/list read refresh 已经从 blocking bug 收紧成带护栏的 phase-1 设计权衡。
3. `live completion gate` 不再假绿，现场失败会真实落成 fail-closed evidence。
4. `codex 5.4-xhigh` 红队已经从 `reject` 收敛到 `approve-with-fixes`。

## 2. 到 v19 为止的当前状态

### 2.1 已经被拿下的部分

当前 planning task plane 已经同时具备：

1. `OpenClawBot` 主链 acceptance
2. owner guard / identity propagation
3. planning task list / task_get / session_get plugin surface
4. query surface 摘要化与 cross-session fail-closed
5. `cancelled` 映射补齐
6. live completion gate 的真实 fail-closed

### 2.2 当前剩余主问题

到这一步之后，真正还没被拿下的是：

1. OpenClaw dynamic replay harness 的 live ask bootstrap `fetch failed`
2. `/v3/agent/session/{session_id}` 的 server-side boundary 仍偏宽
3. read-time refresh 仍是 stateful read，而不是最终形态

## 3. v19 的当前判断

到 `v19` 为止，我的独立判断是：

1. `continuity proof + query surface hardening + truthful gate` 这一层已经基本站住。
2. 当前主风险已经再次收缩到：
   - live bootstrap failure
   - session REST boundary
   - read-refresh 的最终归宿

也就是说，下一批不该继续主要投在：

1. 再加新的 planning task type
2. 再堆更多 acceptance 文档
3. 再扩 plugin surface

而该投在：

1. 查 `fetch failed`
2. 决定 session route 边界收口方案
3. 决定 read-refresh 是继续保留还是迁出

## 4. v19 的 Next 3

### 4.1 Next 1

做 `OpenClaw dynamic replay harness fetch failed` 的定向排障包：

1. 证明是 OpenClaw/harness 侧问题还是 18711 侧问题
2. 拿到最小可复现场景

### 4.2 Next 2

设计 `/v3/agent/session/{session_id}` 的 boundary 收口方案：

1. 只收 plugin path
2. 还是收整个 REST surface

### 4.3 Next 3

给 `planning task` read refresh 做 phase-2 决策：

1. 保留 stateful read
2. 迁成显式 refresh
3. 或迁成后台 reconcile

## 5. 一句话结论

`v19` 的核心变化是：

> planning task plane 现在不仅有 continuity proof，还有更可信的 query surface 和 truthful live gate；下一批真正该攻的是 live bootstrap `fetch failed` 与 session boundary，而不是继续假装 final-completion 已经成立。
