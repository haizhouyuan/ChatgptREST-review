# 2026-04-02 OpenClawBot Meeting Intake Smoke Test Spec v2

## 1. v2 相比 v1 改了什么

这一版不是改方向，而是把 `v1` 里两个说得偏轻的点收紧：

1. 不再把 `runtime identity` 写成“待 smoke 观察的中性未知项”
2. 不再把 `bridge 本体直调 smoke` 当成足以代表主链的验证

基于当前代码和红队交叉核验，`Step 0` 现在必须显式拆成：

1. `Smoke A`: transport smoke
2. `Smoke B1`: bridge 本体直调 smoke
3. `Smoke B2`: OpenClaw 主链 tool-execution smoke
4. `Smoke C`: optional natural-chain smoke

## 2. 当前代码事实

### 2.1 Feishu / OpenClaw transport 仍然能接住并落盘媒体

从 `openclaw/extensions/feishu/src/bot.ts` 可以确认：

1. inbound media 会被下载
2. 会落到本地磁盘
3. inbound context 里会写入：
   - `MediaPath / MediaPaths`
   - `MediaUrl / MediaUrls`
   - `MediaType / MediaTypes`

这条链说明：

> `Feishu -> OpenClawBot` 的 transport 半链成立概率仍然很高。

### 2.2 bridge 本体只认 `context.files / context.attachments`

`openmind-advisor` 当前提取附件的入口非常窄：

1. 只读 `context.files`
2. 只读 `context.attachments`
3. 然后把结果写入：
   - `task_intake.attachments`
   - `task_intake.available_inputs.files`
   - `body.attachments`

关键证据：

1. [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L253)
2. [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L305)

### 2.3 canonical plugin tool context 里没有 `files / attachments`

OpenClaw 当前 plugin tool context 的静态字段只有：

1. `config`
2. `workspaceDir`
3. `agentDir`
4. `agentId`
5. `sessionId`
6. `sessionKey`
7. `threadId`
8. `messageChannel`
9. `agentAccountId`
10. `sandboxed`

没有：

1. `files`
2. `attachments`

关键证据：

1. [types.ts](/vol1/1000/projects/openclaw/src/plugins/types.ts#L57)
2. [openclaw-tools.ts](/vol1/1000/projects/openclaw/src/agents/openclaw-tools.ts#L194)

### 2.4 current embedded tool path 会丢掉 `_ctx`

在 OpenClaw 的 current custom-tools path：

1. `splitSdkTools()` 把所有工具都放进 `customTools`
2. `customTools` 由 `toToolDefinitions(tools)` 生成
3. `toToolDefinitions()` 解析当前 execute args 时会读到 `_ctx`
4. 但最终实际调用是：
   - `tool.execute(toolCallId, params, signal, onUpdate)`

这意味着：

1. 插件 execute 第三个参数并不是可靠的 runtime ctx
2. 对于 `openmind-advisor` 这种把第三个参数当 ctx 用的实现，当前主链存在代码级错位风险

关键证据：

1. [tool-split.ts](/vol1/1000/projects/openclaw/src/agents/pi-embedded-runner/tool-split.ts#L4)
2. [pi-tool-definition-adapter.ts](/vol1/1000/projects/openclaw/src/agents/pi-tool-definition-adapter.ts#L57)
3. [pi-tool-definition-adapter.ts](/vol1/1000/projects/openclaw/src/agents/pi-tool-definition-adapter.ts#L81)

### 2.5 `runEmbeddedPiAgent()` 主链没有把 media 附件显式送进 plugin tools

从 `agent-runner-execution.ts` 当前主链可见：

1. 会传 `sessionId / sessionKey / agentId`
2. 会传 `messageProvider / agentAccountId / messageTo / messageThreadId`
3. 会传 threading tool context
4. 会传 `images` 与其他 agent runtime 参数

但没有看到：

1. `files`
2. `attachments`
3. 把 `MediaPaths / MediaUrls` 显式投影到 plugin tool execute 上下文

关键证据：

1. [agent-runner-execution.ts](/vol1/1000/projects/openclaw/src/auto-reply/reply/agent-runner-execution.ts#L258)

### 2.6 旧 replay gate 的 PASS 不能代表主链

旧的 dynamic replay gate 通过，是因为 harness 直接：

1. 注入 `context={"files":[...]}`
2. 注入 `runtime_ctx={sessionKey, sessionId, agentAccountId, agentId}`
3. 手工调用 plugin execute

这只能证明：

1. bridge 本体在受控直调下能组出对的 payload

不能证明：

1. OpenClaw 真正的 `auto-reply -> customTools` 主链会提供同样的上下文

关键证据：

1. [openclaw_dynamic_replay_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/openclaw_dynamic_replay_gate.py#L251)
2. [openclaw_dynamic_replay_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/openclaw_dynamic_replay_gate.py#L310)

## 3. 为什么 v2 不能只做一个“大一统 e2e”

如果直接做：

`Feishu 发消息 -> OpenClawBot -> agent 自己决定调 openmind_advisor_ask -> 看最后结果`

仍然会混进 4 类不同问题：

1. transport 是否接住材料
2. bridge 本体 payload 是否正确
3. canonical main path 是否真的把附件/identity 送到 bridge
4. agent 是否会正确选择工具

所以 `Step 0` 必须分层。

## 4. Step 0 的四段 smoke

### 4.1 Smoke A: Feishu intake transport smoke

只验证：

1. `Feishu -> OpenClawBot` 是否能接住会议沉淀消息
2. 音频 / 文件 / 富文本图片是否被下载并落盘
3. inbound context 中是否出现：
   - `MediaPath / MediaPaths`
   - `MediaType / MediaTypes`
4. 会话是否路由到预期 `sessionKey`

它不验证：

1. `/v3/agent/turn`
2. `task_intake.attachments`
3. bridge payload
4. tool selection

### 4.2 Smoke B1: bridge contract smoke

这一步故意绕开 OpenClaw 主链，只验证 bridge 本体。

方法：

1. 直接调用 `openmind_advisor_ask`
2. 手工提供 `context.files` 或 `context.attachments`
3. 把 endpoint 指向 capture stub
4. 检查 `/v3/agent/turn` 请求体

这一步的价值是：

1. 单独证明 bridge payload builder 是否正确

但它不能证明：

1. 主链会不会自动提供这些字段

### 4.3 Smoke B2: canonical OpenClaw main-path smoke

这是 `v2` 新增的 mandatory gate。

它必须验证：

1. 真实 `OpenClawBot -> auto-reply -> runEmbeddedPiAgent -> customTools` 路径里
2. `openmind_advisor_ask` 被触发时
3. 插件到底拿到了什么 execute 参数
4. `/v3/agent/turn` capture 里到底有没有：
   - `attachments`
   - `available_inputs.files`
   - `session_id / account_id / thread_id / agent_id`
5. tool caller / agent model 在调用 `openmind_advisor_ask` 时，是否真的把文件路径写进：
   - `params.context.files`
   - `params.context.attachments`

如果需要，可以在本地临时加 capture/instrumentation，但验证对象必须是：

> canonical main path，而不是手工直调 plugin。

### 4.4 Smoke C: optional natural-chain smoke

只有当 `A + B1 + B2` 都通过后，才做自然链 smoke：

`Feishu -> OpenClawBot -> 由 agent 自然选择 openmind_advisor_ask -> /v3/agent/turn`

它主要验证：

1. tool affordance
2. prompt / skill / trigger 是否足够

## 5. 当前最保守的预期结果

基于现在的代码，我对四段 smoke 的预期是：

1. `Smoke A` 大概率能过
2. `Smoke B1` 也大概率能过
3. `Smoke B2` 很可能暴露两类真实断点：
   - `MediaPaths` 没有进入 `context.files/attachments`
   - runtime identity 在 plugin execute 上错位
4. `Smoke B2` 还可能暴露第三类断点：
   - tool caller / agent model 从未把文件路径写进 `params.context`
5. `Smoke C` 只有在 `B2` 过后才有讨论价值

## 6. Step 0 的证据包要求

每次 smoke 至少保留：

1. 输入材料清单
2. OpenClawBot 关键日志
3. 已保存媒体路径
4. capture endpoint 记录的 `/v3/agent/turn` 请求体
5. 如果是 `B2`，还要保留主链 tool invocation 的参数证据
6. 最终失败分类或通过结论

## 7. Step 0 的出口条件

只有满足下面条件，才允许进入 phase-1 第一条实施规格：

1. `A` 证明 transport 成立
2. `B1` 证明 bridge 本体 contract 成立
3. `B2` 证明 canonical main path 也成立，或至少明确记录断点
4. `B2` 的断点记录里必须显式回答：
   - framework 有没有投影
   - tool caller / agent model 有没有把文件路径放进 `params.context`

如果 `B2` 没过，则下一步不是画 `task_id / checkpoint`，而是先修：

1. attachment projection
2. runtime identity handoff
3. tool caller / agent-model context forwarding

## 8. 与总计划的关系

这份 `v2` 不改总计划主方向。

它只把 `Step 0` 的 gate 从“材料链 smoke”升级成：

> `transport 成立`、`bridge 本体成立`、`canonical main path 成立` 三件事分开证明。
