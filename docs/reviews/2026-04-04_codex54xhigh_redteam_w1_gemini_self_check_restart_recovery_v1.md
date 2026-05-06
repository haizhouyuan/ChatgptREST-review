# 2026-04-04 Codex 5.4 xhigh redteam W1 Gemini self-check restart recovery v1

## Redteam verdict

`approve-with-scope-tightening`

## Findings

### 1. High: 主结论文档引用了过时的 live job 事实

红队指出：

- [`artifacts/jobs/5b5f493c46a840feb1c55c2f70c3b824/result.json`](/vol1/1000/projects/ChatgptREST/artifacts/jobs/5b5f493c46a840feb1c55c2f70c3b824/result.json)
  当前已经是：
  - `status=error`
  - `error_type=MaxAttemptsExceeded`

因此不能继续把它写成：

- `status=cooldown`
- `error_type=UiTransientError`

这个 finding 我接受，并已修正文档。

### 2. High: blocker 口径说重了

红队指出：

- `self_check` 变慢/卡住，本身可能只是 reopen + restart + sleep 恢复链拉长了耗时
- 这还不足以把 blocker 冻结成“shared-profile CDP runtime instability”

这个 finding 我接受，并已把 authoritative diagnosis 收窄成：

- 剩余 failure surface 在 Gemini live runtime/send path
- 还不能进一步冻结成更窄的单一句根因

### 3. Medium: `GEMINI_REUSE_EXISTING_CDP_PAGE=1` 不能当成正式诊断依据

红队指出这个 flag 会改 Gemini lane 的 tab 复用策略，本身是混淆变量。

这条我接受，并已把它改写成：

- 运行时实验
- 不是 authoritative diagnosis 的证据来源

## What still holds up

红队没有推翻这几条：

1. 这批代码是有效的 resilience/projection 收窄补丁
2. public session ambiguity 已经不是主 blocker
3. `W1` 仍未过线，下一批必须继续打 live runtime/send path

## Independent judgment after redteam

我的独立判断是：

1. 红队这次指出的是口径问题，不是代码补丁方向错了。
2. 代码本身仍值得提交，因为：
   - self-check 恢复面更接近现场
   - MCP transport gap 的 fresh-session retry 是合理的
   - session projection 收窄方向正确
3. 但文档和主计划必须按更保守的口径冻结，不能把根因说得比证据更硬。
