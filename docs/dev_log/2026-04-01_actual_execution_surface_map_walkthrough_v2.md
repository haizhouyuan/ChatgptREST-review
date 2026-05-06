# 2026-04-01 Actual Execution Surface Map Walkthrough v2

## 这轮为什么要出 v2

`v1` 已经把主工作台和 ask lane 分开了，但用户随后补充了一个关键事实：

1. 手机端常用的 `8702` 不是泛泛的“某个网页交互面”
2. 它是独立项目 `tmuxagent`
3. 本质是在远程控制 tmux pane 里的 `Codex / Claude Code`

这意味着上一版里“移动访问变体”的说法方向对，但还不够具体，不足以支撑后续目标讨论。

## 这轮新增了什么

新增：

1. `docs/reviews/2026-04-01_planning_work_agent_actual_execution_surface_map_v2.md`

这版把两件事正式写清：

1. `tmuxagent(8702)` 属于现有 workbench 的远程入口 + 控制面
2. `chatgpt_web.ask / gemini_web.ask / consult` 属于 ChatgptREST 的 provider/job substrate 与专项外援 lane

## 这轮的关键纠偏

### 1. 关于 `8702`

它不是新执行层。

它是：

1. 独立仓库 `tmuxagent`
2. 读取 tmux pane
3. 发送输入到 tmux pane
4. 远程操控已开着的 `Codex / Claude Code` workbench

### 2. 关于 `chatgpt_web.ask / gemini_web.ask / consult`

它们也不该再被混称为“你日常 planning 工作的执行层”。

更准确地说：

1. `chatgpt_web.ask / gemini_web.ask` 是 low-level provider kinds
2. `consult` 是多模型专项复核模式
3. 它们属于 ChatgptREST 内部能力面，不等于你的 daily workbench

### 3. 关于“为什么会乱”

这轮确认，乱不是单点 bug，而是两种混淆叠加：

1. 把用户 workbench 和 provider lane 混了
2. ChatgptREST 内部 low-level ask、broad MCP、wrapper/CLI、advisor、v3 facade、public MCP 长期 additive 叠层

## 这轮收口后的口径

后续再讨论 planning 第一目标时，应把结构固定为：

1. 用户工作侧
   - `Codex / Claude Code / Antigravity`
   - `tmuxagent(8702)` 作为远程控制入口
   - `Feishu / OpenClawBot` 作为 capture / dispatch 候选入口
2. ChatgptREST 内部侧
   - public MCP / `/v3/agent/turn`
   - consult / controller / direct gemini
   - low-level `/v1/jobs kind=*web.ask`

只有先把这个现状图冻结，后面讨论“入口怎么做、哪些任务走哪条 lane、需不需要多 agent”才不会继续串层。
