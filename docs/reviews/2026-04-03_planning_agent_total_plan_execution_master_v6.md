# 2026-04-03 Planning Agent Total Plan Execution Master v6

## 1. v6 相比 v5 的关键变化

`v6` 的核心变化不是扩 scope，而是把 phase-1 第一条切片的 failure tail 补到了可用水平。

相比 `v5`，新增成立的是：

1. `meeting_sedimentation` continuity slice 已不只是 happy path 可用
2. 常见失败路径下的 `checkpoint + session` 收口也已经补硬

## 2. 到 v6 为止的总判断

当前最准确的总口径是：

1. `planning` 第一阶段主线不变
2. `会议沉淀` 仍然是 phase-1 第一条生产切片
3. `知识层` 继续并行补齐
4. `任务层` 已从“有 continuity slice”推进到“这条 slice 的 failure persistence 也可用”
5. `Feishu` 入口 owner 仍然是 `OpenClaw/OpenClawBot`
6. `Codex / Claude Code / Antigravity` 仍然是深度工作台
7. `publicagentmcp` 仍按 `ask wrapper` 收口

## 3. 已完成的阶段

### 3.1 Step 0

已完成：

1. `transport`
2. `bridge contract`
3. `canonical main path`

### 3.2 Step 1

已完成：

1. `meeting_sedimentation` 最小 continuity sidecar
2. 稳定 `task_id`
3. 最小 checkpoint
4. `new / continue` 最小规则
5. response / session surface 投影
6. failure tail hardening

## 4. v6 的当前最小能力

现在可以更准确地说：

1. 同一场会议补材料时，能继续同一 `task_id`
2. 一轮执行后能自动写回最小 checkpoint
3. 普通失败时会留下 `failed` checkpoint 和异常文本
4. 即使 checkpoint 写回本身抛错，session 也会尽量终态化为 `failed`

## 5. 当前还没完成的部分

当前仍未完成：

1. `OpenClawBot` 明确的 task continue / retrieve surface
2. 深度工作台侧显式 checkpoint writeback 命令面
3. phase-1 之外的其它 planning 任务类型推广
4. full task runtime integration
5. post-fix 的最终 Claude strict sign-off

## 6. Claude 红队状态

到 `v6` 为止，应诚实写成：

1. 多轮 `claudegac` 红队已经真实推动了这条切片的代码修正
2. 最新一次 post-fix strict review 因 `402 insufficient credits` 没拿到最终 verdict
3. 所以当前状态是：
   - `代码实现`：已继续推进
   - `本地验证`：已通过
   - `外部最终 sign-off`：待 Claude credits 恢复后补跑

## 7. v6 的 Next 3

### 7.1 Next 1

把 `OpenClawBot` 侧最小 continue / retrieve 使用面做出来，让这条 continuity slice 对真实 Feishu 入口可见。

### 7.2 Next 2

决定深度工作台是否需要独立 checkpoint writeback helper。

### 7.3 Next 3

在 Claude credits 恢复后，补跑一次 post-fix strict red-team sign-off。

## 8. 一句话结论

`v6` 的核心变化是：

> `meeting_sedimentation` phase-1 现在不只是有第一条 continuity slice，而且这条 slice 的常见失败收口也已经补到了 phase-1 可用。
