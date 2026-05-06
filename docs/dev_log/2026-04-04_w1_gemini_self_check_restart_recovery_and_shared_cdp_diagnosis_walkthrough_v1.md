# 2026-04-04 W1 Gemini self-check restart recovery and shared CDP diagnosis walkthrough v1

## 做了什么

这一轮主要做了 3 件事：

1. 给 Gemini self-check 增加初始 prompt surface 丢失后的 reopen/restart 恢复
2. 给 MCP HTTP transport 增加一类真实出现过的 SSE/JSON-RPC 断裂 fresh-session retry
3. 把 live 现场重新核到 runtime/send path 层，确认当前主剩余 failure surface 已经不在 public session 层

## 为什么这样做

前一版 `W1` 已经证明：

1. public session surface 不再是当前主瓶颈
2. live completion gate 的失败面已经推进到 provider/bridge completion

因此这一轮不该再扩 surface，而应该把“Gemini 到底是 prompt surface 丢了、还是 runtime 自己不稳”这件事查硬。

## 现场核验摘要

### 1. systemd / env

确认了真实 env file 是：

- [`/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env`](/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env)

并确认 `chatgptrest-chrome.service` 与 `chatgptrest-driver.service` 都在加载它。

### 2. 端口

现场多次确认：

- `9226` = 实际 Chrome
- `9222` = 长期存活的 python listener
- `18701` = driver
- `18711` = API
- `18712` = public MCP
- `18713` = node

### 3. 现场症状

现场先后核到过：

1. `TargetClosedError`
2. `connect ECONNREFUSED 127.0.0.1:9226`
3. `gemini_web_self_check` 长等待/卡死型症状
4. send 侧 job 已收口为 `error + MaxAttemptsExceeded`，但底层 guard 文本仍指向 `UiTransientError: <TimeoutError: empty error>`

这说明问题已经不在单点 prompt box 查找层面，但还不能只凭这批证据就把根因冻结成单一的 shared-profile CDP 结论。

## 本轮结论

这轮没有把 `W1` 做成，但把 live 问题再往前推进了一层：

1. 测试层恢复逻辑已经补上
2. transport gap 已经缩小
3. 真正剩下的是 Gemini live runtime/send path 稳态化与 send 完成链

## 产物

- [review v1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-04_w1_gemini_self_check_restart_recovery_and_shared_cdp_diagnosis_v1.md)
- [master plan v48](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-04_planning_agent_total_plan_execution_master_v48.md)
