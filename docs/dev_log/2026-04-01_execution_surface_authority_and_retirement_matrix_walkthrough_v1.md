# 2026-04-01 Execution Surface Authority and Retirement Matrix Walkthrough v1

## 为什么要补这份 matrix

前一轮已经把两件事查清了：

1. `tmuxagent(8702)` 是远程控制既有 tmux pane 的 dashboard，不是新的模型执行层
2. `chatgpt_web.ask / gemini_web.ask / consult` 属于 ChatgptREST 内部 provider/job substrate，不是用户当前真实主工作台

但如果只停在“解释现状”，下一轮仍然容易重新串层。

所以这一轮要做的不是再写一篇复盘，而是把各个 surface 的 authority 和 posture 冻结成一张可执行矩阵。

## 这轮新增了什么

新增：

1. `docs/reviews/2026-04-01_execution_surface_authority_and_retirement_matrix_v1.md`

这份文档不是删除计划，而是第一阶段 planning 目标的 surface freeze：

1. 哪些是主线
2. 哪些保留但不升格
3. 哪些只给内部
4. 哪些只给维护
5. 哪些只是兼容名

## 这轮的关键判断

### 1. 用户工作侧

对 planning 第一阶段，真正的主工作台仍然应该是：

1. `Codex`
2. `Claude Code`
3. `Antigravity`

`tmuxagent(8702)` 则应正式认定为：

1. 这些 workbench 的远程入口 + 控制面

而不是新的执行层。

`Feishu / OpenClawBot` 目前只适合：

1. capture
2. dispatch
3. 轻交互

不该过早承诺成可替代 workbench 的主入口。

### 2. ChatgptREST northbound

对 coding agent，当前需要继续冻结为 canonical 的仍然是：

1. public MCP `18712/mcp`
2. `/v3/agent/turn`

`/v2/advisor/ask` 和 `/v2/advisor/advise` 仍然 live，也要保留，但其 posture 应降为：

1. advisor/openmind/internal 次主线

而不是默认 coding-agent northbound。

### 3. Provider/job substrate

`chatgpt_web.ask / gemini_web.ask / consult` 这条线不该再当用户主入口解释。

更准确的定位是：

1. provider substrate
2. internal orchestration lane
3. 高风险复核 lane

### 4. Legacy/helper stack

这轮最重要的收口之一，是明确 broad/admin MCP、legacy wrapper/jobs CLI、deprecated tool names 仍然存在，但 posture 应明确写成：

1. maintenance-only
2. compatibility-only

否则文档、技能、口头说法会继续把它们误当主线。

## 这轮收口后的直接意义

有了这张 matrix，后续讨论下面这些问题时就不会继续串层：

1. 飞书到底只是 capture，还是要升格成主入口
2. 哪些任务该直接在 workbench 里做
3. 哪些任务才值得调 ChatgptREST 的专项 lane
4. 哪些旧层先不删，只做 posture 降级

一句话说，这轮不是“减少功能”，而是先冻结默认面与权威面，让第一阶段 planning 目标有稳定地基。
