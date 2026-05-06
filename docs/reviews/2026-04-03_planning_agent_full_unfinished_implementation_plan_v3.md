# 2026-04-03 Planning Agent 未完成部分全量实施计划 v3

## 1. v3 相比 v2 的收紧点

`v3` 不重写全盘计划，只把当前最前面的 live 断点改对。

相对 `v2`，本版新增 4 个收紧点：

1. 不再把 `W1-S1` 写成泛化的 `provider blocker`，改成 `Gemini live thread reopen / retention`。
2. 不再把 `scenario pack / prompt` 当 `W1` 的主攻方向，它们退到次级。
3. 明确：当前剩余问题不是 query/session/checkpoint 主线崩了，而是 provider live thread 站不住。
4. `same-session repair` 被提升为 `W1` 的候选建设项，而不是事后补丁。

## 2. 当前状态冻结

### 2.1 已经完成到什么程度

现在已经完成并可信的部分：

1. `OpenClawBot` 已能把 planning 任务送进 canonical agent path。
2. `gemini_web.ask` 已能真实创建 concrete conversation URL。
3. 本地 `wait` 逻辑已经做到了：
   - exact cid first
   - direct goto requested thread
   - wrong-thread fail-closed
4. `wrong answer from old thread` 已被消掉。
5. `planning task plane` 的 query/session/checkpoint sidecar 仍成立。

### 2.2 仍未完成的最前断点

最前断点现在是：

1. `Gemini live page` 在 wait 周期中仍可能从 requested thread 回退到 `/app`
2. 因此 live gate 仍然 `needs_followup`
3. 这意味着 phase-1 还不能宣称 live green

## 3. 第一阶段完成定义不变，但 gate 解释要改

第一阶段完成定义不变，仍然是：

> 至少一类高频 planning 任务能从 `OpenClawBot` 稳定进入主链、跨端继续、写回 checkpoint，并通过真实验收。

但当前 `W1` gate 的解释要改成：

1. `Drive attach` 已不再是最前 gate
2. `wrong-thread answer` 已不再是最前 gate
3. 当前最前 gate 是 `Gemini live thread retention`

## 4. 工作包更新

## W1. Live 主链打通

### 当前最新目标效果

不是抽象地“让 OpenClawBot 更稳”，而是：

> 让 `OpenClawBot -> gemini_web.ask` 在已有 concrete thread URL 的情况下，wait 周期仍能稳定留在该 thread 上并拿到最终 answer。

### W1-S1. Gemini live thread retention hardening

做什么：

1. 冻结最新 blocker 口径：
   - `requested_cid_direct_goto_succeeded=true`
   - 但最终 `observed_conversation_url=/app`
2. 设计并实现最多一层受控的 reopen retention 策略：
   - direct goto 后二次确认
   - root fallback 时单次 retry
   - 或受控 same-session repair handoff
3. 保持 fail-closed，不放开错线程 completion

验收：

1. live gate 至少有一轮从 `needs_followup` 推进到 `completed`
2. `run_meta.json` 不再出现 `requested thread -> /app` 的最终漂移
3. 如仍失败，失败 evidence 依然结构化且口径稳定

### W1-S2. session/status 真实性

做什么：

1. provider 失败或 `needs_followup` 时，session / task / checkpoint 的状态解释保持一致
2. `same_session_repair` 若进入主链，要定义清楚何时触发、何时终止

验收：

1. `job/session/checkpoint` 不再互相打架
2. `needs_followup` 的 next action 对人工和后续 agent 都可执行

### W1-S3. live green 后再回到 task acceptance

只有 `W1-S1` 站住后，才继续：

1. `meeting_sedimentation`
2. `workforce_planning`
3. `implementation_plan`

这三类真实 task 的 live acceptance 扩面。

## W2. 统一任务线程收口

`W2` 的大方向不变，但当前不再是最前 blocker。

现在的推进原则：

1. 不停做 `W2` 的本地/离线能力
2. 但 live 主优先级让位给 `W1-S1`

## W3. Planning 知识与记忆主线

这条线的口径不变：

1. `reviewed runtime pack`
2. `planning-priority context`
3. `active_project / decision_ledger / handoff` work memory

但当前它不是最前 live blocker。

## 5. 当前最应该做的事

1. 把当前批次代码和 evidence 收口提交
2. 用红队复核这批“本地已改善、live 仍被 Gemini thread retention 卡住”的判断是否有夸大
3. 在此基础上继续推进 `W1-S1`

## 6. 一句话结论

> `v3` 的核心变化是：第一阶段未完成部分的最前断点，已经从“进入 provider”和“附件上传”收缩为 `Gemini live thread retention`；接下来应围绕它继续做真实 live 打通，而不是重新摊大饼。
