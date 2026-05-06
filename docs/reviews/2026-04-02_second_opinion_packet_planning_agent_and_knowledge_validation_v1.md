# 2026-04-02 Second Opinion Packet: Planning Agent And Knowledge Validation v1

## 1. 这份 packet 是给谁看的

这份文档不是给代码执行器看的，而是给第二个 reviewer 用的。

目的只有两个：

1. 让第二个 reviewer 快速看懂我这轮到底调查了什么、已经形成了哪些判断。
2. 让第二个 reviewer 重点核验：
   - 我的结论哪里成立
   - 哪里说重了
   - 下一阶段应该补齐、收口，还是重构

## 2. 这轮工作到底在做什么

这轮工作不是单点 bug 修复，而是在为一个更清晰的目标收口：

> 做一个面向 `planning/` 日常工作的长任务 agent。

这里的 `planning/` 不只是写文档，而是用户高频的实际工作：

- 人员规划
- 项目规划
- 任务拆解
- 汇报材料
- 会议沉淀
- 研究与调研
- 决策与复盘

所以这轮一直围绕三个问题推进：

1. 系统现在到底是什么，不是什么。
2. `planning agent` 的效果目标是什么。
3. 当前和 `planning` 相关的知识、记忆、上下文能力到底哪些是真有用的。

## 3. 目前已经冻结的主线判断

### 3.1 关于系统整体定位

当前比较稳定的判断是：

- `Codex / Claude Code / Antigravity` 才是用户现实里的主工作台
- `tmuxagent(8702)` 是这些工作台的远程入口/控制面
- `Feishu / OpenClawBot` 目前更像 capture / dispatch 入口
- public MCP + `/v3/agent/turn` 是 ChatgptREST 的 canonical northbound
- `chatgpt_web.ask / gemini_web.ask / consult` 不是用户主入口，而是内部 provider/job substrate 与专项 lane

对应文档：

- [2026-04-01_execution_surface_authority_and_retirement_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_execution_surface_authority_and_retirement_matrix_v1.md)
- [2026-04-01_planning_task_surface_and_lane_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_planning_task_surface_and_lane_matrix_v1.md)
- [2026-04-01_planning_work_agent_actual_execution_surface_map_v2.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_planning_work_agent_actual_execution_surface_map_v2.md)

### 3.2 关于 planning agent 目标

已经冻结下来的效果目标是：

1. 能承接 `planning/` 日常工作
2. 懂历史，不从零开始
3. 会判断现状，不只会复述
4. 产出可直接使用的结果
5. 长任务不漂
6. 能被独立验收
7. 会复盘并持续变强

对应文档：

- [2026-04-01_goal_priority_stack_from_user_intent_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_goal_priority_stack_from_user_intent_v1.md)
- [2026-04-01_planning_work_agent_effect_requirements_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_planning_work_agent_effect_requirements_v1.md)
- [2026-04-01_planning_work_agent_acceptance_checklist_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_planning_work_agent_acceptance_checklist_v1.md)

### 3.3 关于多端与记忆治理

当前冻结的主判断不是“强行统一成一个窗口”，而是：

> 统一成一个逻辑任务层，而不是统一成一个聊天窗口。

已冻结的关键件：

- `task_id`
- `new / continue / branch`
- `checkpoint`
- `memory scope`

对应文档：

- [2026-04-02_planning_unified_logical_task_layer_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_unified_logical_task_layer_v1.md)
- [2026-04-02_planning_task_new_continue_branch_policy_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_task_new_continue_branch_policy_v1.md)
- [2026-04-02_planning_checkpoint_schema_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_checkpoint_schema_v1.md)
- [2026-04-02_planning_memory_writeback_policy_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_memory_writeback_policy_v1.md)

## 4. 这轮关于知识与记忆的调查主结论

### 4.1 不是只做了“KB / 向量检索”

目前我把相关能力分成 5 层：

1. `KB working evidence layer`
2. `planning reviewed runtime pack`
3. `EvoMap canonical knowledge plane`
4. `planning durable work memory`
5. `signals / observer`

关键判断：

> 对 `planning` 最有价值的，不是“泛化向量检索”本身，而是 `planning review plane -> reviewed runtime pack -> planning-priority context resolution -> active_project / decision_ledger work memory`

对应文档：

- [2026-04-02_planning_knowledge_capability_value_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_knowledge_capability_value_matrix_v1.md)

### 4.2 我当前认为最该保留和继续投入的

1. `planning_review_plane`
2. `planning reviewed runtime pack`
3. `ContextResolver` 的 planning 优先逻辑
4. `active_project / decision_ledger / handoff / post_call_triage`

### 4.3 我当前认为应降级看待的

1. 继续把通用 `KB / vector / graph` 做成更大平台
2. 图边推理优先于 reviewed pack / promotion gate
3. multi-graph query 持续扩张
4. 把 `signals / observer` 当成 planning 主能力

## 5. 这轮已经做过的“存在性调查”

我已经核清的代码现实包括：

- `KBHub` 是真实的 `FTS5 + vector + RRF` facade
- `planning_review_plane` 会直接从 `planning` 源抓材料、分桶、筛噪
- `planning_runtime_pack_search` 会读取 ready bundle 并套 runtime gate
- `ContextResolver` 在 `role_id=planning` 时会优先 planning pack
- `KnowledgeDB` 是真实的 canonical `documents / episodes / atoms / evidence / entities / edges` 存储
- `WorkMemoryManager` 已经支持：
  - `active_project`
  - `decision_ledger`
  - `post_call_triage`
  - `handoff`
- `WorkMemoryImporter` 已经能把 `planning/docs/backfill` 的 manifest 导入 durable memory

## 6. 这轮已经做过的“效果验证”

### 6.1 已通过的聚焦测试

我本轮实际跑过：

```bash
./.venv/bin/pytest -q tests/test_planning_runtime_pack_search.py tests/test_controller_engine_planning_pack.py
./.venv/bin/pytest -q tests/test_work_memory_importer.py tests/test_work_memory_manager.py tests/test_context_service_work_memory.py tests/test_capture_work_memory.py
./.venv/bin/pytest -q tests/test_kb_hub.py tests/test_kb.py tests/test_funnel_graph.py tests/test_advisor_consult.py -k 'planning_review or planning_pack or graph or kb or recall or evidence_pack'
```

结果：

- `planning runtime pack` 相关：`7 passed`
- `work memory` 相关：`32 passed`
- `KB / graph / recall` 聚焦相关：`48 passed`

### 6.2 已通过的真实 materials smoke

#### A. planning runtime pack 离线 golden-query 校验

我实际跑了：

```bash
./.venv/bin/python ops/run_planning_runtime_pack_offline_validation.py --output-dir /tmp/planning_runtime_pack_validation_20260402
```

结果：

- `ok = true`
- `query_count = 4`
- `domain_hits = 4`
- `bucket_hits = 4`
- `token_hits = 4`

输出：

- `/tmp/planning_runtime_pack_validation_20260402/summary.json`

#### B. planning work memory 真实 manifest 导入

我实际跑了：

```bash
env OPENMIND_MEMORY_DB=/tmp/work_memory_import_smoke_20260402.db \
  ./.venv/bin/python -m chatgptrest.cli work-memory import-manifest \
  --manifest /vol1/1000/projects/planning/docs/backfill/active_project_seed_manifest_v1.json \
  --manifest /vol1/1000/projects/planning/docs/backfill/decision_ledger_seed_manifest_v1.json \
  --execute \
  --account-id acct-backfill \
  --role-id planning \
  --json-out /tmp/work_memory_import_execute_ready_20260402.json \
  --report-out /tmp/work_memory_import_execute_ready_20260402.md
```

结果：

- `entry_count = 27`
- `selected_count = 24`
- `written_count = 24`
- `manual_review_required = 3`
- `blocked_count = 0`

#### C. work memory 召回 smoke

我实际用 `ContextResolver` 跑了两条 query：

1. `shared cognition 四端 联合验收`
2. `会议录音 ASR 知识沉淀`

结果说明：

- `work_memory_scope_hits.active_project == account_role`
- `work_memory_scope_hits.decision_ledger == account_role`
- `work_memory_query_sensitive == true`
- imported `active_project` / `decision_ledger` 的确进入了 prompt-safe active context

## 7. 这轮新发现的关键问题

### 7.1 runtime pack 不是“不能用”，但当前 freshness 已经过期

我实际重跑了：

```bash
./.venv/bin/python ops/audit_planning_runtime_pack_sensitivity.py
./.venv/bin/python ops/check_planning_runtime_pack_release_readiness.py --max-age-hours 72
```

结果：

- sensitivity audit：`ok = true`
- release readiness：`ready = false`

直接原因不是内容坏掉，而是：

- `freshness_ok = false`
- `age_hours ≈ 530`

也就是说：

> 这条线更像“做出来了，但缺持续维护和刷新”，而不是“必须整体推倒重来”。

### 7.2 离线 validation 通过，不等于运行时 query 全部命中

我直接用 `ContextResolver` 以 `role_id=planning` 做了 4 个 query：

1. `2026预算关键数字汇总`
2. `104 模组量产导入计划`
3. `横向应用事业部 十五五规划 对内 领导 审阅稿`
4. `硬门槛授权矩阵`

结果：

- 前 3 个 query 的 `planning_pack_hits > 0`
- 第 4 个 query `硬门槛授权矩阵` 的 `planning_pack_hits = 0`
- 真实运行时已经回退到普通 `KBHub`

这很重要，因为 pack 里其实确实有这份文档：

- `硬门槛授权矩阵（停投/停采/停产/退场谈判）`

但对应 atom 在 canonical DB 里大多还是：

- `promotion_status = staged / candidate`
- `groundedness = 0.0`

所以热路径 gate 把它挡掉了。

这说明：

> 当前 planning runtime pack 的主要问题不是“完全没做出来”，而是“pack freshness 和 atom promotion / groundedness 维护没有跟上，导致部分用户关键 query 在真实运行时掉回普通 KB”。

## 8. 我当前的倾向性判断

### 8.1 我不倾向于整体重构

原因：

1. `planning review plane`
2. `runtime pack`
3. `ContextResolver` 接线
4. `work memory importer + active context`

这几块不是概念稿，也不是空壳，已经有真实测试和真实 materials smoke 支撑。

如果现在整套推倒，等于把最接近 `planning work agent` 的那部分一起砍掉。

### 8.2 我倾向于“补齐 + 收口”，不是“大重构”

当前更像需要补齐这几件事：

1. `planning reviewed runtime pack` 的 refresh / release 维护机制
2. pack query 与真实运行时 query 的 coverage 对齐
3. planning 关键 doc 对应 atom 的 promotion / groundedness 修复
4. 把 `work memory` 真正挂进任务线程与 checkpoint 回写，而不只停在 import-ready 状态

## 9. 需要第二个 reviewer 重点把关的问题

我建议第二个 reviewer 不要泛泛点评，而是重点回答下面这些问题。

### 9.1 关于 planning runtime pack

1. 这条线当前最大的真实问题，是不是 freshness / maintenance，而不是架构错误。
2. `硬门槛授权矩阵` 这类 query 的失效，更像数据 promotion 问题，还是检索策略问题。
3. 这条线应继续补齐，还是应该改成另一种 runtime retrieval 结构。

### 9.2 关于 work memory

1. `active_project / decision_ledger / handoff / post_call_triage` 这四类对象，是否已经足够作为 planning 第一阶段主对象。
2. 现在这条线最缺的是不是“任务线程 writeback”，而不是 schema 重做。

### 9.3 关于 KB / vector / graph

1. 当前是否应明确把它们压成支撑层，而不是继续当主平台扩张。
2. `canonical atom + promotion gate + reviewed active set` 是否应该明确高于图边推理 / 多图查询扩张。

## 10. 我给 second reviewer 的一句话

如果要一句最核心的 briefing，我会用这句：

> 这套 planning 相关知识能力不是没做出来，而是已经做出了一个有希望的窄主线；现在真正要判断的，不是要不要整体重构，而是这条主线到底该补齐 freshness、promotion、runtime coverage 和 task-thread writeback，还是其中某一段已经证明设计方向错了。

