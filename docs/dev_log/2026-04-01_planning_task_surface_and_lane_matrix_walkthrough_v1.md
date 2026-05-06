# 2026-04-01 Planning Task Surface and Lane Matrix Walkthrough v1

## 为什么要补这份矩阵

上一轮已经冻结了 surface 的 authority / posture，但还缺一张“任务到底怎么走”的实用表。

如果没有这张表，后面依然容易出现两类混乱：

1. 明明只是普通 planning 长任务，却先去选 `chatgpt_web.ask` / `gemini_web.ask`
2. 明明只是要先把手机上的材料接住，却试图把飞书当主工作台

所以这轮要补的不是新架构，而是一个用户视角的默认使用法。

## 这轮新增了什么

新增：

1. `docs/reviews/2026-04-01_planning_task_surface_and_lane_matrix_v1.md`

它把三件事放在一张表里：

1. `planning/` 各类任务默认在哪个工作台里做
2. 哪些任务适合从飞书先 capture，再回到主工作台
3. 哪些场景才值得后置调用 `chatgpt_web.ask` / `gemini_web.ask` / `consult`

## 这轮的关键 freeze

### 1. 默认决策顺序

先选工作台，不先选模型。

也就是：

1. 先判断是不是长任务
2. 是长任务就先进 `Codex / Claude Code / Antigravity`
3. 只有确实需要专项能力时，才再调外部 lane

### 2. `tmuxagent(8702)` 的位置

这轮继续明确：

1. 它是远程入口 + 控制面
2. 不是新的模型 lane

### 3. 飞书的第一阶段 posture

这轮继续压稳：

1. 飞书现在最有价值的是 capture / dispatch
2. 不承诺替代主工作台

### 4. 专项 lane 的使用边界

这轮把 `chatgpt_web.ask / gemini_web.ask / consult` 的触发条件写得更具体了：

1. `chatgpt_web.ask`
   - premium reasoning / review / polish
2. `gemini_web.ask`
   - Deep Research / DeepThink / Drive / imported-code / second opinion
3. `consult`
   - 高风险双审 / 多审

## 这轮最重要的直接意义

从这轮开始，后续再谈：

1. 某个 planning 任务应该怎么进系统
2. 哪些输入应该先扔飞书
3. 哪些任务应该在手机上继续推进
4. 哪些场景才应该调 Gemini 或 consult

都可以直接对着这张矩阵判断，而不需要每次重新解释“surface 和 lane 的区别”。
