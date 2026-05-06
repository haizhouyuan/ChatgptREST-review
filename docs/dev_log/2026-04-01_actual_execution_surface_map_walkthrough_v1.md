# 2026-04-01 Actual Execution Surface Map Walkthrough v1

## 这轮为什么要补这一版

上一轮把 `chatgpt_web.ask / gemini_web.ask / consult` 说成“执行层”的核心构成，这对 ChatgptREST 内部 lane 视角还说得过去，但对用户真实工作流是不对的。

用户明确补充了当前现实：

1. 日常 planning 工作主要是在 `Codex / Claude Code / Antigravity` 里完成
2. 手机端也更多是在借网页/端口去访问某个 native 交互面
3. 飞书/OpenClawBot 效果目前不如 TUI / IDE
4. `ChatGPT ask` 这种网页自动化路径显然不应承担所有任务

所以必须把“真实主执行层”和“专项外援 lane”分开。

## 这轮新增了什么

新增：

- `docs/reviews/2026-04-01_planning_work_agent_actual_execution_surface_map_v1.md`

这份文档的目的，是把下面四件事完全拆开：

1. 工作台
2. 入口
3. 编排前门
4. 专项外部能力 lane

## 这轮收口后的新口径

### 1. 主执行层

当前 planning 工作真正的主执行层，应定义为：

1. `Codex`
2. `Claude Code`
3. `Antigravity`

也就是 native interactive workbench。

### 2. 入口

当前入口应分成：

1. workbench 内直接发起
2. 手机上通过网页/端口访问某个 workbench
3. `Feishu / OpenClawBot`

### 3. 编排前门

ChatgptREST 这一侧的前门应定义为：

1. public MCP
2. `/v3/agent/turn`
3. `/v2/advisor/advise`

它们是治理与编排面，不是用户主工作台。

### 4. 专项外援 lane

`chatgpt_web.ask / gemini_web.ask / consult` 应被下沉定义为：

1. 外部 Web model capability lane
2. second-opinion / deep research / high-risk review lane
3. 不是 everyday workbench

## 这样改完之后的直接意义

这版口径最大的价值，是把“你真正每天靠什么干活”重新放回了中心。

后续再讨论：

1. 飞书怎么接材料
2. ChatgptREST 应该管到哪一层
3. 哪些任务该调 ChatGPT/Gemini/consult
4. 多 agent 什么时候有收益

都能在更清楚的分层上继续，不会再把 workbench、lane、入口、编排面混成一个词。
