# 2026-04-02 Second Opinion Packet: Full Planning Agent Strategy And Investigation v1

## 1. 这份 packet 的范围

这份 packet 不是只审 `KB`、`向量检索`、`知识图谱`。

这次希望第二个 reviewer 独立审核的范围，是我们这一整轮已经冻结下来的全盘判断：

1. 系统现状到底是什么
2. `planning` 第一阶段的目标到底是什么
3. 入口、工作台、执行面、内部 lane 应该怎么分层
4. 为什么要统一逻辑任务层，而不是强行统一成一个窗口
5. `planning` 相关知识、记忆、runtime pack 到底哪些真有价值
6. 现在更该补齐哪些闭环，而不是又开新盘子

所以这份 packet 的目的，是让 reviewer 回答这句话：

> 我们现在对 `planning` agent 的整体方向、现状判断、主线设计、能力优先级、知识主线判断，是否已经大体正确；哪些地方说重了、说轻了、漏了。

## 2. 这轮已经冻结下来的主线判断

### 2.1 产品目标层

当前已经冻结的顶层目标是：

> 先做一个面向 `planning/` 日常工作的长任务 agent。

这条主线的第一阶段目标不是“做一个更大更复杂的平台”，而是先做出：

1. 能接正式工作任务
2. 懂历史
3. 会判断现状
4. 高质量完成工作
5. 长任务不漂
6. 可被独立验收
7. 会复盘并持续变强

对应文档：

1. [2026-04-01_goal_priority_stack_from_user_intent_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_goal_priority_stack_from_user_intent_v1.md)
2. [2026-04-01_planning_work_agent_effect_requirements_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_planning_work_agent_effect_requirements_v1.md)
3. [2026-04-01_planning_work_agent_acceptance_checklist_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_planning_work_agent_acceptance_checklist_v1.md)
4. [2026-04-02_planning_agent_nontechnical_overview_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_agent_nontechnical_overview_v1.md)

### 2.2 现状与系统分层

当前已经冻结的现状判断是：

1. `Codex / Claude Code / Antigravity` 是现实里的主工作台
2. `tmuxagent(8702)` 是这些 workbench 的远程入口 + 控制面
3. `Feishu / OpenClawBot` 目前更适合做 capture / dispatch / 轻交互
4. public MCP + `/v3/agent/turn` 是 ChatgptREST 的 canonical northbound
5. `chatgpt_web.ask / gemini_web.ask / consult` 不是用户主入口，而是内部 provider/job substrate 与专项 lane

对应文档：

1. [2026-04-01_planning_work_agent_actual_execution_surface_map_v2.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_planning_work_agent_actual_execution_surface_map_v2.md)
2. [2026-04-01_execution_surface_authority_and_retirement_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_execution_surface_authority_and_retirement_matrix_v1.md)
3. [2026-04-01_planning_task_surface_and_lane_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_planning_task_surface_and_lane_matrix_v1.md)
4. [2026-04-02_public_agent_mcp_scope_and_pruning_review_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_public_agent_mcp_scope_and_pruning_review_v1.md)
5. [2026-04-02_repo_bootstrap_and_doc_obligations_scope_review_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_repo_bootstrap_and_doc_obligations_scope_review_v1.md)

### 2.3 多端与记忆治理层

当前已经冻结的关键判断不是“强制只有一个入口”，而是：

> 统一逻辑任务层，而不是统一聊天窗口。

目前已冻结的 load-bearing pieces：

1. `task_id`
2. `new / continue / branch`
3. `checkpoint`
4. `memory scope`
5. `memory writeback policy`

对应文档：

1. [2026-04-02_planning_unified_logical_task_layer_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_unified_logical_task_layer_v1.md)
2. [2026-04-02_planning_task_new_continue_branch_policy_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_task_new_continue_branch_policy_v1.md)
3. [2026-04-02_planning_checkpoint_schema_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_checkpoint_schema_v1.md)
4. [2026-04-02_planning_memory_writeback_policy_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_memory_writeback_policy_v1.md)

### 2.4 planning 知识主线层

当前已经冻结的主判断是：

> 对 `planning` 最有价值的，不是泛化 `KB / vector / graph` 平台本身，而是 `planning review plane -> reviewed runtime pack -> planning-priority context resolution -> active_project / decision_ledger work memory`。

而且这一条线已经不再只是“存在性判断”，而是做过实际效果验证。

对应文档：

1. [2026-04-02_planning_knowledge_capability_value_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_knowledge_capability_value_matrix_v1.md)
2. [2026-04-02_planning_knowledge_effectiveness_validation_v2.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_knowledge_effectiveness_validation_v2.md)
3. [2026-04-02_planning_knowledge_gap_closure_and_rebuild_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_knowledge_gap_closure_and_rebuild_decision_v1.md)
4. [2026-04-02_second_opinion_packet_planning_agent_and_knowledge_validation_v2.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_second_opinion_packet_planning_agent_and_knowledge_validation_v2.md)

## 3. 最小阅读顺序

如果 reviewer 时间有限，我建议只读 8 份：

1. [2026-04-02_planning_agent_nontechnical_overview_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_agent_nontechnical_overview_v1.md)
2. [2026-04-01_goal_priority_stack_from_user_intent_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_goal_priority_stack_from_user_intent_v1.md)
3. [2026-04-01_execution_surface_authority_and_retirement_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_execution_surface_authority_and_retirement_matrix_v1.md)
4. [2026-04-01_planning_task_surface_and_lane_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_planning_task_surface_and_lane_matrix_v1.md)
5. [2026-04-02_planning_unified_logical_task_layer_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_unified_logical_task_layer_v1.md)
6. [2026-04-02_planning_knowledge_capability_value_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_knowledge_capability_value_matrix_v1.md)
7. [2026-04-02_planning_knowledge_effectiveness_validation_v2.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_knowledge_effectiveness_validation_v2.md)
8. [2026-04-02_planning_knowledge_gap_closure_and_rebuild_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_knowledge_gap_closure_and_rebuild_decision_v1.md)

如果 reviewer 要核“清理和裁剪方向”，再补读：

1. [2026-04-02_public_agent_mcp_scope_and_pruning_review_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_public_agent_mcp_scope_and_pruning_review_v1.md)
2. [2026-04-02_repo_bootstrap_and_doc_obligations_scope_review_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_repo_bootstrap_and_doc_obligations_scope_review_v1.md)

## 4. 现在请 reviewer 重点审的，不是所有细节，而是这 6 个判断

### A. 第一阶段主线判断

现在把第一阶段主线冻结为“面向 `planning/` 日常工作的长任务 agent”，而不是继续扩成大而全平台，这个判断对不对。

### B. Surface 分层判断

现在把：

1. `Codex / Claude Code / Antigravity`
2. `tmuxagent`
3. public MCP + `/v3/agent/turn`
4. `chatgpt_web.ask / gemini_web.ask / consult`

明确分成四层，而不再混成“执行层”，这个判断对不对。

### C. 统一逻辑任务层判断

现在优先统一：

1. `task_id`
2. `checkpoint`
3. `memory scope`
4. `new / continue / branch`

而不是先强行统一入口或统一会话窗口，这个判断对不对。

### D. planning 知识主线判断

现在把 `planning review plane + reviewed runtime pack + planning-priority context + work memory` 当成主线，而把 `KB / vector / graph` 降成支撑层，这个判断对不对。

### E. “补齐优先，不重构”判断

基于本轮效果验证，现在把主判断冻结为“优先补 freshness / promotion / acceptance / writeback，而不是整套重构”，这个判断对不对。

### F. 清理节奏判断

现在不急着删旧层，而是先收 authority / default posture，再逐步裁剪 `consult`、`repo_bootstrap/doc_obligations` 对 public 面的污染，这个节奏是否合理。

## 5. 当前我认为已经比较稳的部分

这些是我认为 reviewer 更可能“核验通过”的部分：

1. 第一阶段目标应围绕 `planning/` 高频工作，而不是继续发散
2. `Codex / Claude Code / Antigravity` 才是现实主工作台
3. `tmuxagent` 属于远程控制面，不是新执行引擎
4. 多端可以共存，但任务线程和记忆线程必须统一
5. `work memory` 已经证明有真实效果
6. `runtime pack` 结构成立，但当前半健康

## 6. 当前我认为最值得 reviewer 挑刺的部分

这些是我希望 reviewer 重点反驳或收紧的地方：

1. 我是否把 `Feishu / OpenClawBot` 的第一阶段角色说得太保守或太激进
2. 我是否把 `public MCP` 和 `/v3/agent/turn` 的后续价值说轻了或说重了
3. 我是否过早把 `KB / vector / graph` 降成支撑层
4. 我是否过早下了“补齐优先，不重构”的判断
5. 我是否低估了 future harness / evaluator / EvoMap 对第一阶段的 load-bearing 程度

## 7. 这次 second opinion 最希望 reviewer 回答的 3 个问题

### 1. 方向问题

我们现在把主线收口到 `planning` 长任务 agent，这个方向是否正确。

### 2. 架构问题

我们现在把 system surfaces、任务层、知识层这样切分，是否是一个可持续的分层，而不是新的复杂化。

### 3. 节奏问题

下一阶段应该：

1. 先补齐闭环
2. 还是先做局部重构
3. 还是现在就应该推翻重来

## 8. Reviewer 输出建议格式

为了让 second opinion 可直接拿来用，我建议 reviewer 输出时最少分 4 段：

1. `核验通过`
2. `发现问题`
3. `我会收紧或改写的口径`
4. `下一阶段建议`

## 9. 当前冻结口径

如果 reviewer 只需要记一句话，请用这句：

> 这轮已经不只是“技术调查”，而是在为一个面向 `planning/` 日常工作的长任务 agent 收口主线；当前最合理的方向，是先把主工作台、逻辑任务层、planning 知识主线和最小闭环补齐，而不是继续让入口、lane、知识平台和进化平台同时扩张。
