# 2026-04-02 ClaudeGAC OpenClawBot Meeting Intake Smoke Redteam Review v1

## 1. 范围

这轮红队审核的对象是：

1. [2026-04-02_openclawbot_meeting_intake_smoke_test_spec_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_openclawbot_meeting_intake_smoke_test_spec_v1.md)
2. [2026-04-02_planning_agent_total_plan_execution_master_v2.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_agent_total_plan_execution_master_v2.md)
3. `openmind-advisor` bridge 与 OpenClaw `auto-reply / embedded tools` 主链代码

红队运行：

- `run_id`: `ccjob_20260402T155831Z_b3ef7e6d`
- `run_dir`: `/vol1/1000/home-yuanhaizhou/.claude-gac/skills/claudecode-agent-runner/runs/ccjob_20260402T155831Z_b3ef7e6d`
- 关键原始证据：
  - `result/claude_result.json`
  - `logs/stdout.log`

说明：

1. 这次 runner 中途一度只产出 `stdout.log` 子结论，随后才正常补齐 `claude_result.json`
2. 我没有机械顺从红队，而是把其结论与本地代码核验交叉比对后才收口

## 2. 红队提出的关键问题

### 2.1 High: `MediaPaths` 到 `context.files/attachments` 的自动投影并不存在

红队与本地核验一致确认：

1. Feishu / OpenClaw transport 层写入的是 `MediaPath / MediaPaths / MediaUrls / MediaTypes`
2. `openmind-advisor` bridge 只消费 `context.files / context.attachments`
3. OpenClaw plugin tool context 类型里没有 `files / attachments`
4. 在 canonical embedded tool path 中，没有看到任何把 `MediaPaths / MediaUrls` 自动投影为 `context.files / context.attachments` 的逻辑

关键证据：

1. [types.ts](/vol1/1000/projects/openclaw/src/plugins/types.ts#L57)
2. [openclaw-tools.ts](/vol1/1000/projects/openclaw/src/agents/openclaw-tools.ts#L194)
3. [agent-runner-execution.ts](/vol1/1000/projects/openclaw/src/auto-reply/reply/agent-runner-execution.ts#L258)
4. [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L253)

### 2.2 High: `openmind-advisor` 当前对 execute 第三个参数的假设，在主链上很可能是错位的

红队指出的核心点成立，而且我接受。

在 OpenClaw 的 common custom-tools path：

1. 所有工具都会通过 `customTools -> toToolDefinitions()` 进入 embedded runner
2. `toToolDefinitions()` 会在当前签名里解析出 `_ctx`
3. 但它最终调用的是 `tool.execute(toolCallId, params, signal, onUpdate)`
4. 这意味着插件工具如果把第三个参数当 runtime ctx 使用，在主链上拿到的更像是 `AbortSignal`

关键证据：

1. [tool-split.ts](/vol1/1000/projects/openclaw/src/agents/pi-embedded-runner/tool-split.ts#L4)
2. [pi-tool-definition-adapter.ts](/vol1/1000/projects/openclaw/src/agents/pi-tool-definition-adapter.ts#L57)
3. [pi-tool-definition-adapter.ts](/vol1/1000/projects/openclaw/src/agents/pi-tool-definition-adapter.ts#L81)
4. [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L384)

这条我不再保守表述成“还没证明稳定成立”，而改成：

> 在 OpenClaw canonical embedded tool path 上，`openmind-advisor` 当前 runtime ctx 读取方式存在代码级已确认风险。

### 2.3 High: 真实断点不只在 framework 投影，还在 tool caller / agent-model 是否会把文件路径写进 `params.context`

这是 `claude_result.json` 里最值钱的新收紧点，我接受。

即便后面修好了 framework 层的 context/identity 传递，真实链路仍然要回答：

1. 调用 `openmind_advisor_ask` 的一方是谁
2. 它会不会把文件路径放进 `params.context.files`
3. 它会不会把文件路径放进 `params.context.attachments`

也就是说，当前真实风险至少分成两半：

1. framework 没有自动投影
2. tool caller / agent model 也没有被证明会显式补这个字段

这就是为什么 `Smoke B1` 不能代表真实链路。`B1` 里手工喂 `context.files` 很容易通过，但真实 main path 仍可能因为 caller 从未填写这些字段而失败。

### 2.4 Medium: 旧的 dynamic replay gate PASS 不是主链证明

这条红队没有直接写成最终 finding，但它在调查路径里已经把问题挖出来了，我也接受。

旧的 phase20 replay gate 之所以能得到带 identity 的正确 payload，是因为它的 harness 直接这样调用：

1. 手工注入 `context={"files":[...]}`
2. 手工注入 `runtime_ctx={sessionKey, sessionId, agentAccountId, agentId}`
3. 直接执行 `tool.spec.execute(..., runtimeCtx)`

这能证明：

1. bridge 本体在“受控直调”条件下能组出正确请求

但不能证明：

1. OpenClaw `auto-reply -> runEmbeddedPiAgent -> customTools` 主链能提供同样的上下文

关键证据：

1. [openclaw_dynamic_replay_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/openclaw_dynamic_replay_gate.py#L251)
2. [openclaw_dynamic_replay_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/openclaw_dynamic_replay_gate.py#L310)

### 2.5 Medium: 现有测试多数是 source assertion，不是行为证明

这条也是我接受的收紧项。

例如：

1. [test_openclaw_cognitive_plugins.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py#L56)

它能证明：

1. `openmind-advisor` 源码里写了 `ctx?.sessionKey`
2. 源码里写了 `buildTaskIntakePayload(...)`

但它不能证明：

1. 主链真实运行时真的能把这些值送到插件

### 2.6 Low: identity 风险存在，但更准确的说法是“依赖 real invocation path”，不是“bridge 代码本身完全不会写”

这条我部分接受。

更准确的说法是：

1. bridge builder 本体会尝试读取 identity
2. 真问题在于 canonical invocation path 没有证明会把 bridge 期望的 runtime ctx 传进去

所以我保留“代码级风险”这个结论，但不把它扩大成“bridge 本体不支持 identity”。

## 3. 我的独立判断

### 3.1 我接受红队的核心反对

我接受下面四点，而且会直接改写总计划口径：

1. `Step 0` 不能只做“bridge 本体直调 smoke”
2. `MediaPaths -> context.files/attachments` 当前没有主链证据，按代码现实更接近不存在
3. runtime identity 在 `openmind-advisor` 主链里不是“尚未证明”，而是“存在明确错位风险”
4. 即便 framework 修通了，也还要验证 tool caller / agent model 会不会把文件路径放进 `params.context`

### 3.2 我不把红队结论扩大成“整条链已经彻底失败”

我不接受把当前结论写成：

1. `OpenClawBot -> openmind-advisor` 整条链完全不可用

更准确的说法是：

1. `Feishu -> OpenClawBot transport` 仍然大概率成立
2. `bridge 本体直调` 仍然是有价值的，因为它能单独验证 payload 组装
3. 但主链里“材料投影”“runtime identity 注入”“tool caller 是否补 `params.context.files`”三件事目前都不能视为成立

### 3.3 Step 0 必须升成双层验证

因此我把 `Step 0` 的工程 gate 改成：

1. `Smoke A`: Feishu / OpenClaw transport
2. `Smoke B1`: bridge 本体直调 capture
3. `Smoke B2`: OpenClaw 主链 tool-execution capture
4. `Smoke C`: optional natural-chain smoke

关键变化是：

> `B1` 证明 bridge 本体 contract；`B2` 才证明 canonical main path；而且 `B2` 里必须显式回答 tool caller / agent model 是否会把文件路径写进 `params.context`。

## 4. 对总计划的影响

这轮红队不会推翻 phase-1 主方向，但会收紧第一步：

1. `会议沉淀` 仍然是第一条生产切片
2. 但 `Step 0` 现在必须显式验证：
   - transport 是否能接住材料
   - bridge 本体是否会生成对的 payload
   - 主链是否真的把附件与 identity 送到 bridge
   - tool caller / agent model 是否真的把文件路径写进 bridge 读取的位置
3. 在 `B2` 通过前，不能把 `OpenClawBot -> canonical task plane` 说成 ready baseline

## 5. 一句话裁决

红队最值钱的贡献不是“否定方向”，而是把 `Step 0` 从“材料链 smoke”收紧成了：

> 同时证明 `bridge 本体` 和 `OpenClaw 主链` 的两层 smoke gate。
