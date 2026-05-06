# 2026-04-03 Planning Agent 未完成部分全量实施计划 Walkthrough v3

## 为什么从 v2 改到 v3

`v2` 的总方向还是对的，但最前断点又往后推进了一步。

`v2` 里 `W1-S1` 还带着比较泛的 provider blocker 口径。

到这轮结束，现场已经证明：

1. 不是还没进入 provider
2. 不是还没拿到 concrete thread URL
3. 甚至不是 direct goto 本身失败
4. 而是 Gemini live 页面在 wait 周期里没能稳定留在该 thread

所以 `v3` 主要就是把 `W1-S1` 改写成：

- `Gemini live thread reopen / retention hardening`

## v3 具体改了什么

### 1. 把最前 blocker 改成 thread retention

不再把 prompt / scenario pack 放在主位置，而是把它们降成次级因素。

### 2. 提升 same-session repair 候选地位

因为当前 live fail-closed 已经会落到 `needs_followup`，所以后续如果继续推进，就必须考虑一条受控 repair 路径，而不是反复手工解释。

### 3. 保留 fail-closed，不追求假绿

`v3` 明确要求继续保持：

1. 错线程不算成功
2. root fallback 不算成功
3. live gate 必须靠 evidence 过，不靠解释过
