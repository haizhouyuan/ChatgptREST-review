# 2026-04-03 Planning Agent Total Plan Execution Master v24

## 1. v24 相比 v23 的关键变化

`v24` 的变化不是新增功能，而是把 upload-menu 这批修复的证据链补硬，并把口径降到更稳。

新增成立的事实：

1. `Gemini upload menu button not found` 的当前现场更像 selector-level 漂移
2. provider 侧已经补上 current exact label 优先的 selector resilience
3. 这一层现在有更真实的 unit evidence，但仍未被新的 live gate 验成“已经越过 upload-menu 阶段”

## 2. 到 v24 为止的当前状态

### 2.1 已经被拿下的部分

当前 planning task plane 已经同时具备：

1. `OpenClawBot` 主链 acceptance 基线
2. owner guard / identity propagation
3. planning task list / task_get / session_get plugin surface 的第一批收口
4. query surface 摘要化与 cross-session fail-closed
5. `cancelled` 映射补齐
6. live completion gate 的真实 fail-closed
7. send-phase Gemini base-app URL 的误投影修复
8. 真实 Gemini thread 的 route-level 非误伤验证
9. Gemini upload menu selector resilience 的第一批补齐

### 2.2 当前剩余主问题

到这一步之后，真正还没被拿下的是：

1. 需要重跑 live gate，确认 blocker 是否已经越过 upload-menu 阶段
2. 如果继续失败，下一层很可能是：
   - Drive picker modal / search / insert
3. `/v3/agent/session/{session_id}` 的更大 server-side boundary 仍偏宽
4. read-time refresh 仍是 phase-1 设计债

## 3. v24 的当前判断

到 `v24` 为止，我的独立判断是：

1. 当前 live blocker 已经被切成更细的层次：
   - session truthfulness
   - upload-menu selector
   - 后续可能的 picker 阶段
2. 其中 upload-menu selector 这一层，已经有较强证据支持“值得先这样修”
3. 但在新的 live gate 之前，这一层仍只能说“已补 selector resilience”，不能说“已现场验真完成”

## 4. v24 的 Next 3

### 4.1 Next 1

重启相关 Gemini 执行面并重跑 live completion gate

### 4.2 Next 2

如果 blocker 前移到 picker 阶段，收：

1. modal open
2. search
3. insert

### 4.3 Next 3

在 live 绿之前，不继续扩 task type，仍只做：

1. live blocker 向后推进
2. 任务真相层与 session truth 对齐

## 5. 一句话结论

`v24` 的核心变化是：

> 当前 live blocker 已经进一步缩小到 Gemini upload menu 的 selector 漂移，这一层已补上更稳的 selector resilience；下一步仍必须用 live gate 验证问题是否继续向后移动。
