# 2026-04-03 Planning Agent Total Plan Execution Master v25

## 1. v25 相比 v24 的关键变化

`v25` 的变化不是继续扩 task plane，而是把 live blocker 从“Gemini upload/menu/错答混杂”进一步切到更稳定的两层：

1. `Gemini wait/export thread contamination` 已经有代码级 fail-closed
2. 当前最新 live blocker 前移到 `OpenClaw dynamic replay harness fetch failed`

## 2. 到 v25 为止的当前状态

### 2.1 已经被拿下的部分

到 `v25` 为止，下列点已经成立：

1. `OpenClawBot planning task plane` 的 query surface 和 session truth 已完成多轮收口
2. `Gemini upload menu selector` 这层已经补过 resilience
3. `Gemini wait/export` 的错 thread 污染风险，在 `cid` 可解析的关键分支上，现在有明确代码级 fail-closed
4. base `/app + conversation_hint` 这条 lane 已优先锚到 sidebar row 的 `cid`，并修掉了 `_open_row()` 里导致 expected-thread 只写进 debug、未写回外层 guard 变量的作用域 bug；无 `cid` 时不会继承旧 stale thread，但还不是全域 fail-closed
5. `GeminiConversationThreadMismatch` 已能被 public session surface 投成 `needs_followup + same_session_repair`
6. direct `kind=job` session refresh 不再丢 repair payload

### 2.2 当前剩余主问题

当前剩下的 live blocker 不再是“脏答案被完成”，而是更前面的 bootstrap：

1. `OpenClaw dynamic replay harness`
2. `requestJson(...)`
3. `TypeError: fetch failed`

也就是说：

1. 现在的 completion gate 最新结果是 `ask_failed`
2. 现场还没重新恢复到能稳定进入 provider execution 的状态

## 3. v25 的当前判断

到 `v25` 为止，我的独立判断是：

1. 这轮代码修复方向是对的，而且已经把最危险的错答污染问题压到 fail-closed
2. 但当前主瓶颈已经不在 provider wait 结果解释层，而在 `OpenClaw` live bootstrap 传输层
3. 所以下一步不该继续扩 planning 功能，更不该再开新 task type
4. 下一步只该继续推进 live bootstrap / dynamic replay harness 这一层

## 4. v25 的 Next 3

### 4.1 Next 1

定位并修 `OpenClaw dynamic replay harness fetch failed`

### 4.2 Next 2

在 bootstrap 恢复后重跑 live completion gate，验证：

1. 不再错答完成
2. 如果仍失败，session surface 是否已经稳定落到 `same_session_repair`

### 4.3 Next 3

只有在 live bootstrap 恢复之后，才继续回到：

1. planning phase-1 acceptance
2. 更真实的 end-to-end task continuity acceptance

## 5. 一句话结论

`v25` 的核心变化是：

> 现在最危险的、`cid` 可解析的 Gemini 错 thread 污染已经被代码级 fail-closed 收紧；当前 live 主 blocker 已前移为 OpenClaw dynamic replay harness 的 bootstrap fetch failure。
