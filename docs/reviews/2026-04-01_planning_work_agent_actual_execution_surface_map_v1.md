# 2026-04-01 Planning Work Agent 实际执行面地图 v1

## 1. 先纠正上一版口径

上一轮把 `chatgpt_web.ask / gemini_web.ask / consult` 说成“执行层”的核心构成，这个说法对 **ChatgptREST 内部执行 substrate** 来说勉强成立，但对 **你当前真实工作流** 来说是不对的。

更准确的说法应该是：

1. 你当前真正的主工作执行面，不是 `ChatgptREST low-level ask`。
2. 你当前真正的主工作执行面，是 `Codex / Claude Code / Antigravity` 这类 **native interactive agent workbench**。
3. `chatgpt_web.ask / gemini_web.ask / consult` 应该被下沉成 **专项外部能力 lane**，而不是你日常 planning 工作的总执行层。

所以这一版要做的事就是把“你真实在怎么工作”和“系统内部有哪些 lane”拆开。

## 2. 先分清四种完全不同的东西

### 2.1 工作台（Workbench）

这是你真正坐在那里长时间推进任务、来回修改、读文件、写文档、反复交互的地方。

当前现实里主要是：

1. `Codex`
2. `Claude Code`
3. `Antigravity`

这类东西的特点是：

1. 交互连续
2. 本地文件/仓库操作强
3. 长任务推进强
4. 适合做真正的 planning 工作

### 2.2 入口（Ingress）

这是你把任务、材料、消息、录音、截图送进系统的入口。

当前现实里主要是：

1. 直接在 `Codex / Claude Code / Antigravity` 里发起
2. 手机上通过网页/端口去访问某个正在运行的交互面
3. `Feishu / OpenClawBot`

入口不等于工作台。

### 2.3 编排前门（Orchestration Front Door）

这是系统用来接住请求、做标准化、做路由、做状态管理的前门。

在 ChatgptREST 里主要是：

1. public MCP `advisor_agent_turn`
2. `/v3/agent/turn`
3. `/v2/advisor/advise`

这层是系统内部治理面，不等于你日常的工作面。

### 2.4 专项外部能力 lane

这是系统在某些场景下调用的特定模型/特定 provider 通道。

在当前 ChatgptREST 里主要是：

1. `chatgpt_web.ask`
2. `gemini_web.ask`
3. `consult`

它们更像“外挂能力”或“专项执行通道”，不是你日常思考的第一层。

## 3. 你当前真实工作流应该怎么描述

按你刚才补充的实际情况，更准确的现状图是：

### 3.1 现在真正的主工作流

你现在主要是这样工作：

1. 用 `Codex / Antigravity / Claude Code` 发起任务
2. 在交互式工作台里连续推进
3. 一边读 `planning/` 里的入口、台账、历史产物、报告
4. 一边持续产出新文档、新报告、新判断

也就是说：

- 你的 planning 成果，当前主要是由 **native interactive coding/work agent** 产出的
- 不是靠 `ChatgptREST` 低层 ask 直接主导完成的

### 3.2 手机上的现实补丁路径

你手机上现在会这样补用：

1. 通过暴露的端口访问某个网页化交互面
2. 再把消息输入进去
3. 实现“接近 TUI 的远程使用”

这个路径的本质是：

- 它仍然是在借用 **native workbench**
- 只是把工作台通过 Web/端口临时搬到手机上

所以它不是新的执行层，而是 **native workbench 的移动访问变体**。

### 3.3 飞书路径现在的现实地位

你也试过飞书，但实际效果不如 `TUI / IDE`。

所以按当前现实，它只能被定义成：

- capture / dispatch / 轻交互入口

而不能定义成：

- 你的 planning 主工作台

### 3.4 ChatgptREST ask 路径的现实地位

`chatgpt_web.ask / gemini_web.ask` 现在更像：

1. 某些特殊模型能力的调用面
2. Web-only provider 的桥接面
3. second opinion / external review / deep research / large attachment handling 的专项通道

它不是你每天写 planning 文档时的默认工作场。

## 4. 所以“执行层”应该重新怎么定义

如果按你真实工作流来定义，执行层至少要拆成两层。

### 4.1 主执行层：Native Interactive Workbench

这是你现在真正靠它干活的层。

包括：

1. `Codex`
2. `Claude Code`
3. `Antigravity`

这层适合：

1. 长时间交互推进
2. repo / file / doc 原地工作
3. planning 历史资料阅读
4. 高强度改稿、重构、补证据、梳理结构
5. 多轮澄清和逐步完成任务

这层不适合：

1. 移动端随手扔材料
2. 快速异步 capture
3. 靠聊天窗口完成复杂附件 intake

### 4.2 外挂执行层：Specialized External Capability Lanes

这是系统在某些明确场景下调用的专项外援。

包括：

1. `chatgpt_web.ask`
2. `gemini_web.ask`
3. `consult`

这层的作用不是替代 workbench，而是补 workbench 没有的能力。

## 5. 那 `chatgpt_web.ask / gemini_web.ask / consult` 到底该怎么定义

### 5.1 `chatgpt_web.ask`

它本质上是：

- ChatGPT Web 自动化调用通道

也就是说，它不是 `Codex`、不是 `Claude Code`、不是 `Antigravity` 那种原生交互工作台，而是：

- 去网页上替你调用 ChatGPT Web

这条 lane 适合：

1. 明确需要 ChatGPT Web / Pro 的能力
2. 特定的 report / reasoning / premium web ask
3. 作为系统统一编排里的一条可调用 provider lane

这条 lane 不适合：

1. 承担你所有 planning 长任务
2. 作为默认日常工作台
3. 承担需要大量本地文件来回编辑、连续长交互、快速迭代的任务

原因很直接：

1. 它慢
2. 它是网页自动化
3. 它交互保真度和操作效率都不如 native workbench

所以更准确的定义是：

> `chatgpt_web.ask` 是 ChatgptREST 内部的一条 Web-model capability lane，不是你 planning 主工作的总执行层。

### 5.2 `gemini_web.ask`

它本质上也是：

- Gemini Web 自动化调用通道

这条 lane 适合：

1. 需要 Gemini Web 特长的时候
2. Deep Research / DeepThink 类任务
3. 大文件 / Drive attach / imported-code 这类场景
4. 需要 Gemini 作为 second opinion 的时候

这条 lane 不适合：

1. 承担所有 planning 日常工作
2. 替代 native TUI / IDE workbench

所以更准确的定义是：

> `gemini_web.ask` 是 Gemini 特定能力 lane，不是日常主执行层。

### 5.3 `consult`

`consult` 甚至不是单一 provider，而是：

- 一个高风险双审/多审编排模式

当前默认就是把多模型并行跑起来，再做聚合。

这条 lane 适合：

1. 高风险判断
2. 重大决策复核
3. 争议性问题双审
4. 需要“1+1>2”的第二意见

这条 lane 不适合：

1. 日常所有任务默认开
2. 普通纪要、普通整理、普通规划草稿都走双审

所以更准确的定义是：

> `consult` 是 premium review mode，不是 everyday mode。

## 6. 这样重画之后，各工具的角色就清楚了

### 6.1 `Codex`

定位：

- 主工作台

适合：

1. planning 长任务
2. 读写 `planning/` 文档
3. 连续多轮推演
4. 结构化收口
5. repo 内工作

不适合：

1. 纯移动 capture
2. 外部消息随手投递

### 6.2 `Claude Code`

定位：

- 与 Codex 并列的主工作台之一

适合：

1. 某些你觉得它更强的写作/推演/工程整理场景
2. 与 Codex 形成不同风格的主 workbench

不适合：

1. 充当飞书型 capture 入口

### 6.3 `Antigravity`

定位：

- 主工作台之一，且当前你对它的文件拖拽/IDE 感知比较强

适合：

1. 文件密集型交互
2. 需要更接近 IDE 感的长任务
3. 作为 planning 工作的高保真桌面面

### 6.4 `手机访问的网页化交互面`

定位：

- native workbench 的移动降级访问方式

适合：

1. 人不在电脑旁边时继续推进
2. 临时回复、补充、续做

不适合：

1. 作为长期主力工作台
2. 承担安全敏感、复杂长时主任务

### 6.5 `Feishu / OpenClawBot`

定位：

- capture / dispatch / receipt / brief follow-up 入口

适合：

1. 移动端发任务
2. 随手扔消息、文件、录音
3. 收回执
4. 轻量跟进

不适合：

1. 承担高保真主工作流
2. 替代 Codex / Claude Code / Antigravity

### 6.6 `ChatgptREST public MCP`

定位：

- ChatgptREST 这套系统的统一 northbound 前门

适合：

1. 需要标准化 task intake
2. 需要统一 session / delivery / wait / provider routing
3. 让 coding agents 通过统一契约进入 ChatgptREST 能力面

不适合：

1. 被误认为你日常 planning 主工作台本身

### 6.7 `chatgpt_web.ask / gemini_web.ask`

定位：

- 专项 provider lane

适合：

1. 需要外部 Web model 能力
2. Deep Research
3. 大附件 / Drive
4. second opinion

不适合：

1. 承担全部主工作执行

### 6.8 `consult`

定位：

- 高风险双审/多审模式

适合：

1. 关键判断复核
2. 高价值任务终审

不适合：

1. 普通任务默认化

## 7. 所以第一阶段最正确的口径应该怎么改

第一阶段不应再说：

> planning work agent 的执行层主要是 ChatGPT ask / Gemini ask / consult

而应该改成：

> planning work agent 当前的主执行层，是 `Codex / Claude Code / Antigravity` 这类 native interactive workbench；`Feishu / OpenClawBot` 是 capture/dispatch 入口；`ChatgptREST public MCP` 是一套可接入的统一编排前门；`chatgpt_web.ask / gemini_web.ask / consult` 则是专项外部能力 lane，用于特殊模型能力、second opinion 和高风险复核，而不是日常主工作台。

## 8. 接下来最该梳理什么

基于这版更正，下一轮最该直接梳理的是一张真正有用的 `execution surface matrix`：

1. 哪些任务默认用 `Codex`
2. 哪些任务更适合 `Claude Code`
3. 哪些任务更适合 `Antigravity`
4. 哪些任务该调 `ChatGPT ask`
5. 哪些任务该调 `Gemini ask`
6. 哪些任务必须开 `consult`
7. 哪些场景只能算 capture，不该冒充主执行

如果这张表不先做出来，后面继续谈“统一入口、多 agent、EvoMap”，还是会再次混乱。

---

## 附：本次判断依赖的证据

### ChatgptREST

1. `docs/client_interactions_v3.md`
2. `docs/contract_v1.md`
3. `docs/runbook.md`
4. `docs/ops/2026-03-25_agent_maintainer_entry_v1.md`
5. `chatgptrest/mcp/agent_mcp.py`
6. `chatgptrest/api/routes_agent_v3.py`
7. `chatgptrest/api/routes_consult.py`

### planning

1. `planning/00_入口/Planning Shared Cognition 开发入口.md`
