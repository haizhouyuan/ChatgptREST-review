# 2026-04-01 基于用户目标意图的优先级栈冻结 v1

## 目的

把“现状复盘之后，下一阶段到底最想实现什么”压成一个稳定目标栈，避免再次把：

- 用户真正想要的 agent 能力
- Anthropic 式 harness 机制
- EvoMap 进化闭环

混成一个无边界的大包。

## 冻结结论

用户这轮表达出来的目标，其实不是三条并列 roadmap，而是三层递进结构：

1. **产品目标**：能发布工作任务、带记忆、懂历史、能分析现状、高质量完成工作的 agent
2. **执行机制目标**：具备 Anthropic 式 harness 能力，保证长任务一致性与独立严苛验收
3. **进化目标**：每次任务后复盘，并通过定期复盘持续提升 agent 能力

所以更准确的理解应该是：

> `1` 是用户真正购买的结果；`2` 是为了稳定做出这个结果的运行机制；`3` 是让这套能力持续变强的学习闭环。

## 一、第一优先级：工作型 agent 能力

这是最上位目标，也是后面所有内部机制必须服务的对象。

如果压成一句话：

> 用户真正要的不是“一个更复杂的系统”，而是“一个能接工作任务、读懂项目历史和当前状态、可靠完成高质量工作的 agent”。

这条能力至少包含：

1. 能接收正式任务，而不是只做即时问答
2. 能读取项目历史、决策上下文、既有记忆
3. 能分析当前 repo / runtime / workspace / artifact 现状
4. 能把任务推进到高质量完成，而不是“看起来回答了”
5. 能产出可交付结果、证据和后续 handoff

这也是为什么下一阶段不能只讨论 harness 结构，而必须先确定：

- 默认 northbound 是什么
- completion authority 是什么
- memory/history/current-state 分别从哪里取真相

## 二、第二优先级：Anthropic 式 harness 能力

这不是最终产品本身，而是保证第一优先级可靠成立的“运行机制”。

按用户这轮口径，真正必须吸收的，不是“多 agent”这个表面形式，而是以下组合：

1. `planner` 先把短任务扩成更完整的 spec
2. `generator` 按块推进，而不是一口气把整个任务做完
3. `evaluator` 独立验收，不能让 generator 自己给自己打高分
4. 每轮先有 `sprint/chunk contract`
5. 用结构化 artifact 持续维持长任务一致性
6. 用真实运行态反馈驱动下一轮迭代

### 这条线里哪些是“硬要求”

从当前目标看，我认为真正应冻结成硬要求的是：

1. `generator / evaluator` 分离
2. `done-definition / contract` 前置
3. `skeptical gate`，能真实阻断低质量结果
4. 结构化 handoff artifact
5. 长任务 resumability / recovery / continuity
6. 真实运行态验证，不只看静态文本

### 哪些不必在第一阶段宗教化

下面这些应视为可调实现，不要一开始就写死成宗教：

1. 是否始终三 agent 常驻
2. 是否必须固定叫 sprint，而不能叫 chunk
3. context reset 还是 compaction
4. planner 是否总要“主动扩 scope”
5. evaluator 是否一开始就覆盖设计/产品/视觉/代码四维完整体系

原因很简单：

Anthropic 原文自己也强调，随着模型能力变化，harness 结构应简化或重排；真正重要的是 load-bearing capability，不是外形照搬。

## 三、第三优先级：EvoMap 进化能力

这条是用户明确想要的长期差异化能力。

如果压成一句话：

> agent 不只要完成任务，还要从任务里学习，并在任务间逐步变强。

我认为它应分成两层：

1. **每任务复盘**
   - 每次任务完成后，生成结构化 retro
   - 记录哪里判断对、哪里判断错、哪里返工、哪里 evaluator 拦下
   - 提炼可进入 memory / policy / rubric / eval backlog 的对象
2. **定期复盘**
   - 定期汇总一段时间的任务数据
   - 找 recurring failure、重复返工、常见低质量模式
   - 更新 prompt / rubric / route / policy / eval tasks

### 这条线的正确位置

EvoMap 进化能力很重要，但它不该先于第一、第二优先级独立膨胀成大平台。

更准确的顺序应该是：

1. 先有可复盘的正式任务主线
2. 再有可信的 evaluator / outcome / artifact
3. 再把 retro 和 periodic review 写进 EvoMap / memory / eval program

如果前两步没有站稳，进化层很容易变成“记录了很多东西，但并没有真正改善能力”。

## 四、这三层目标对当前 repo 的含义

结合 2026-04-01 的现状冻结，下一阶段更合适的解释不是：

- “我们要全面实现 Anthropic harness + EvoMap + 多平面平台”

而是：

- “我们要在这个已经是多平面宿主的 repo 里，优先做出一条真正能工作的任务型 agent 主线；Anthropic harness 是其质量控制操作系统；EvoMap 是其复盘与进化闭环。”

这三层对应关系如下：

| 层级 | 真正目标 | 对 repo 的要求 |
|---|---|---|
| L1 | 工作型 agent 能力 | 冻结默认入口、completion authority、memory/history/current-state truth |
| L2 | Anthropic 式 harness | planner/spec、chunk contract、generator/evaluator 分离、skeptical gate、artifact continuity、runtime validation |
| L3 | EvoMap 进化 | task retro、periodic review、policy/rubric/eval 更新闭环 |

## 五、我建议的下一阶段讨论顺序

### 先讨论什么

1. 先冻结 `L1` 的产品句子
2. 再决定 `task runtime` 是否升格为 next-stage mainline
3. 如果升格，再讨论 `L2` 里哪些 harness 能力是第一阶段硬要求
4. 最后再讨论 `L3` 如何接进 EvoMap，而不是先做大而全的进化平台

### 先不要讨论什么

1. `opencli` 高标准化
2. `CLI-Anything` governed intake
3. 新增更多 northbound surface
4. 一次性建设 mega eval platform

## 六、当前 mouthpiece

如果要把这轮用户目标压成一句可直接进入下一轮讨论的口径，我建议先冻结为：

> 下一阶段的首要目标，是做出一个能接正式工作任务、具备历史记忆和现状分析能力、能高质量完成工作的 agent；Anthropic 式 harness 是这条能力的质量控制与长任务执行机制；EvoMap 则负责把每次任务后的复盘沉淀成持续进化能力。
