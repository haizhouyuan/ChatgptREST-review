# 2026-04-06 OpenClaw ChatGPT Send Timeout Fail-Closed Walkthrough v1

## 做了什么

补了一处只会在真实 `OpenClaw` 正式入口下暴露出来的 session 投影漏口：

1. `chatgpt_web.ask` 在 `send` 阶段没有 thread 证据时，
   命中 `ToolCallError + SSE stream timeout/stream ended`，
   现在会投影成 `needs_followup + same_session_repair`。
2. 同一类问题后来如果升级成 `MaxAttemptsExceeded`，
   仍然保持同样的 repair 语义。
3. 加了新的 ChatGPT send-timeout 路由回归测试，
   锁住 `cooldown` 和 `error` 两条 public session 投影。
4. 用真实正式入口又打了一轮 `OpenClaw -> openmind_advisor_ask ->
   openmind_advisor_session_get` 来复核。

## 为什么做

前一轮 Claude 评审已经认为代码层基本闭环。

但在真正用正式 `OpenClaw` 主路径发起一条 planning 工作后，
现场暴露了一个更窄但更真实的问题：

- child job 已经是 send-phase timeout / no-thread blocker
- formal `openmind_advisor_session_get` 却还在显示
  `running + await_job_completion`

这会误导用户继续空等，而不是在同一个 session 上做 repair。

## 现场结果

新一轮正式入口真实任务：

- session: `openclaw-real-user-check-session-d88f72fa`
- task: `pln_ca3716760df3`
- child job: `32317fbaf2a04dbca483e48c26e4d0e5`

这轮 child job 的现场轨迹是：

1. 先在 `send` 阶段反复命中 `ToolCallError + SSE stream timeout`
2. 没有 `conversation_id`，也没有 thread URL 证据
3. 后续重试里又冷却成 `Blocked: verification_pending`

但正式 `openmind_advisor_session_get` 对外已经收口成：

- `status = needs_followup`
- `next_action.type = same_session_repair`

所以用户面现在看到的是“需要继续修同一个 session”，
而不是“还在跑”或者“泛化失败请自查”。

## 结果

当前 `planning` 主线在正式 `OpenClaw` 入口上又收掉了一处真实产品面漏口：

- 正式入口 ask 可见
- task/session surfaces 可见
- plugin 出口是人话
- ChatGPT send-phase no-thread blocker 也能正确 fail-close

剩余缺口已经继续收敛到产品验证层：

- 真实用户有没有用这条入口做成一件 planning 工作
- 产出有没有真的被拿去推进工作
