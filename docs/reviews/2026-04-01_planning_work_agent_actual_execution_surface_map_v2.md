# 2026-04-01 Planning Work Agent 实际执行面地图 v2

## 1. 这版修正什么

`v1` 已经把“主工作台”和“专项 ask lane”分开了，但对你手机端那条路径的描述还不够准确。

现在代码和 live 进程都已经核清：

1. `8702` 不是泛泛的“网页化交互面”。
2. `8702` 是独立仓库 `tmuxagent` 的 dashboard。
3. `tmuxagent` 的本质，是远程读取和控制当前 tmux server 里的 pane。
4. 所以它并不是新的模型执行层，而是 **现有 Codex / Claude Code workbench 的远程入口 + 控制面**。

与此同时，`chatgpt_web.ask / gemini_web.ask / consult` 这条线也需要进一步纠偏：

1. 它们不是你现实工作流里的主执行层。
2. 它们是 ChatgptREST 内部的 provider/job substrate 与专项外援能力面。
3. 过去之所以越做越乱，是因为从 low-level ask 到 wrapper、CLI、advisor、`/v3/agent/turn`、public MCP，一直在 additive 叠层，没有退役旧层。

## 2. 先分清两条完全不同的主线

### 2.1 你的真实工作执行主线

这条线是你当前真正用来产出 `planning/` 成果的主线。

包括：

1. `Codex`
2. `Claude Code`
3. `Antigravity`
4. `tmuxagent(8702)` 作为对 tmux pane 的远程访问与控制

这条线的特点是：

1. 原地读写 repo / 文件 / 文档
2. 长时间连续交互
3. 多轮澄清与推进
4. 真实产出当前 `planning/` 里的报告、结论、台账、规划稿

### 2.2 ChatgptREST 的 provider/job 主线

这条线不是你现在每天真正坐着工作的工作台，而是 ChatgptREST 自己内部逐步长出来的执行与编排体系。

它的现实结构更接近：

1. low-level jobs：`/v1/jobs kind=chatgpt_web.ask|gemini_web.ask`
2. broad/admin MCP：`chatgptrest/mcp/server.py`
3. wrapper / CLI：`chatgptrest_call.py`、`python -m chatgptrest.cli`
4. advisor 层：`/v1/advisor/*`、`/v2/advisor/*`
5. v3 agent facade：`/v3/agent/turn`
6. slim public MCP：`advisor_agent_turn`

所以这两条线不能再用同一个“执行层”去概括。

## 3. `8702 / tmuxagent` 的准确定义

### 3.1 它是什么

`8702` 对应的是独立仓库 `tmuxagent` 的 dashboard 进程，不在 ChatgptREST 仓内。

代码和 live 进程都能对上：

1. dashboard 入口在 `tmux_agent.dashboard.cli`
2. FastAPI app 在 `tmux_agent.dashboard.app`
3. pane 读取与发送输入最终落到 `tmux list-panes`、`tmux capture-pane`、`tmux send-keys`

### 3.2 它不是什么

它不是：

1. ChatgptREST 的 ask lane
2. ChatgptREST 的内部执行器
3. 新的模型 provider
4. 独立于 Codex / Claude Code 的新 workbench

### 3.3 它在整体结构里属于哪层

如果按你当前真实工作流来划分，它更准确地属于：

> `现有 tmux workbench 的远程入口 + 控制面`

也就是说：

1. pane 里真正跑着的是 `Codex / Claude Code / ChatgptREST` 等执行体
2. `tmuxagent` 只是把这些 pane 暴露成一个手机可访问、网页可控的入口
3. 所以它仍然是“在用 Codex / CC”，不是新起了一套替代执行层

## 4. `chatgpt_web.ask / gemini_web.ask / consult` 的准确定义

### 4.1 `chatgpt_web.ask`

它是：

1. low-level job kind
2. ChatGPT Web 自动化调用 lane
3. ChatgptREST 内部的一条 provider substrate

它不是：

1. 你当前 planning 日常工作的主工作台
2. 你真实 daily workflow 的默认执行面

### 4.2 `gemini_web.ask`

它是：

1. low-level job kind
2. Gemini Web 自动化调用 lane
3. 适合 Gemini DeepThink / Deep Research / Drive / imported-code 等专项能力

它也不是：

1. 日常主工作台
2. `Codex / Claude Code / Antigravity` 的替代物

### 4.3 `consult`

它是：

1. 多模型并行咨询 / 双审编排模式
2. 高风险、争议问题、复核任务的专项 lane

它不是：

1. 普通日常任务的默认入口
2. 单一 provider

## 5. 为什么你会觉得越来越乱

因为现在仓里同时活着两种不同层次的东西，而且旧层没有真正退掉。

### 5.1 第一种混乱：把“工作台”跟“provider lane”混了

你的现实工作台是：

1. `Codex`
2. `Claude Code`
3. `Antigravity`
4. `tmuxagent` 远程控制这些 pane

而 `chatgpt_web.ask / gemini_web.ask / consult` 是另一层：

1. Web model provider lane
2. multi-model consult lane
3. ChatgptREST 的内部 capability surface

这两类东西不能并排叫“执行层”。

### 5.2 第二种混乱：ChatgptREST 内部的 additive migration

过去的演化不是“旧层退掉，新层接管”，而是“旧层保留，新层继续叠”。

现在同时并存的主要层次是：

1. low-level jobs
2. broad/admin MCP
3. wrapper / CLI
4. advisor v1/v2
5. v3 agent facade
6. slim public MCP
7. OpenClaw 兼容名工具

所以你体感上会像在看几代架构同时活着。

## 6. 当前更准确的结构图

### 6.1 你的实际工作侧

1. `Feishu / OpenClawBot`
   - 目前更适合 capture / dispatch / 轻交互
2. `tmuxagent(8702)`
   - 远程访问 tmux pane 的手机/网页入口
3. `Codex / Claude Code / Antigravity`
   - 真实主工作台

### 6.2 ChatgptREST 内部侧

1. `advisor_agent_turn` public MCP
   - coding-agent canonical northbound
2. `/v3/agent/turn`
   - 高层编排面
3. `consult / direct gemini / controller.ask`
   - 编排分流层
4. `/v1/jobs kind=*web.ask`
   - provider/job substrate

## 7. 一句话收口

这次核完之后，最准确的口径应该是：

> 你当前 planning 工作的真实主执行面，是 `Codex / Claude Code / Antigravity` 及其通过 `tmuxagent(8702)` 暴露出来的远程控制工作台；`chatgpt_web.ask / gemini_web.ask / consult` 则属于 ChatgptREST 内部的 provider/job substrate 与专项外援 lane。混乱的根因，不是它们其中某一个存在，而是这些层次长期被混着谈，并且 additive 迁移一直没有完成 authority 与 retirement 收口。

## 8. 这版对后续讨论的意义

后面如果继续讨论：

1. 飞书到底能不能做第一入口
2. 哪些任务该走 native workbench
3. 哪些任务才值得调 ChatgptREST ask / Gemini / consult
4. planning 第一目标到底需不需要多 agent

都必须在这版分层之上继续，而不能再把：

1. 用户工作台
2. 手机远程控制面
3. ChatgptREST 编排面
4. low-level provider substrate

混成同一个词。
