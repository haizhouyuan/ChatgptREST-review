# 2026-04-02 Planning Knowledge Effectiveness Validation Review v1

## 1. 结论先说

这轮不再回答“做了没有”，而是回答“现在到底好不好用”。

我的判断是：

1. `planning durable work memory` 已经证明是 **真可用**，而且对 `planning` 价值很高，应该继续补齐，不该重构。
2. `planning reviewed runtime pack` 是 **局部可用但明显不够用**，核心问题不是架构错了，而是 **pack 太旧、覆盖太窄、缺少持续刷新**。这条线该补齐，不该推倒重来。
3. `KB / 向量检索 / canonical knowledge graph` 这些底座能力是 **真实存在且可用** 的，但对 `planning` 当前帮助更多是支撑层，不该继续当第一主线扩张。
4. 如果只给一句行动建议：

> 先补齐 `planning runtime pack` 的 freshness、覆盖面和刷新机制；继续沿着 `work memory` 做真实入口 capture/writeback；不要在这一步重构通用 KB/graph 平台。

## 2. 这轮实际做了什么验证

### 2.1 定向 pytest

实际执行并通过：

```bash
./.venv/bin/pytest -q \
  tests/test_planning_runtime_pack_search.py \
  tests/test_controller_engine_planning_pack.py \
  tests/test_cognitive_api.py \
  -k 'planning_pack or context_resolve_injects_planning_runtime_pack_into_default_knowledge_chain or context_resolve_prioritizes_planning_pack_for_planning_role'

./.venv/bin/pytest -q \
  tests/test_work_memory_importer.py \
  tests/test_work_memory_manager.py \
  tests/test_context_service_work_memory.py \
  tests/test_capture_work_memory.py

./.venv/bin/pytest -q \
  tests/test_kb_hub.py \
  tests/test_kb.py \
  tests/test_funnel_graph.py \
  tests/test_advisor_consult.py \
  tests/test_cognitive_api.py \
  -k 'evidence_pack or knowledge_ingest_writes_kb_and_graph or graph_query_returns_personal_graph_nodes_edges_and_evidence or graph_query_marks_repo_graph_degraded_without_adapter or recall_can_opt_into_planning_review_pack or recall_does_not_use_planning_review_pack_without_opt_in or recall_returns_hit_explainability_and_promotion_audit_for_planning_review or recall_surfaces_evomap_promotion_audit_and_hit_explainability'
```

结果：

- planning pack 相关定向测试：`7 passed`
- work memory 相关定向测试：通过
- KB/graph/recall 相关定向测试：`8 passed`

关键测试证据：

- [tests/test_planning_runtime_pack_search.py](/vol1/1000/projects/ChatgptREST/tests/test_planning_runtime_pack_search.py#L202)
- [tests/test_controller_engine_planning_pack.py](/vol1/1000/projects/ChatgptREST/tests/test_controller_engine_planning_pack.py#L7)
- [tests/test_context_service_work_memory.py](/vol1/1000/projects/ChatgptREST/tests/test_context_service_work_memory.py#L410)
- [tests/test_advisor_consult.py](/vol1/1000/projects/ChatgptREST/tests/test_advisor_consult.py#L402)
- [tests/test_cognitive_api.py](/vol1/1000/projects/ChatgptREST/tests/test_cognitive_api.py#L1321)
- [tests/test_cognitive_api.py](/vol1/1000/projects/ChatgptREST/tests/test_cognitive_api.py#L683)

### 2.2 planning runtime pack 离线 validation

实际执行：

```bash
./.venv/bin/python ops/run_planning_runtime_pack_offline_validation.py \
  --pack-root artifacts/monitor/planning_reviewed_runtime_pack \
  --spec ops/data/planning_runtime_pack_golden_queries_v1.json \
  --output-dir /tmp/planning_runtime_pack_validation_20260402
```

结果文件：

- [/tmp/planning_runtime_pack_validation_20260402/summary.json](/tmp/planning_runtime_pack_validation_20260402/summary.json)

结果摘要：

- `docs = 116`
- `atoms = 226`
- `query_count = 4`
- `domain_hits = 4`
- `bucket_hits = 4`
- `token_hits = 4`
- `ok = true`

这证明一件事：

> 这包在它原本定义的 4 个 golden queries 上是好用的。

但它也暴露了边界：golden queries 很窄，只覆盖预算、104 导入、十五五规划、授权矩阵。

golden query 规格：

- [ops/data/planning_runtime_pack_golden_queries_v1.json](/vol1/1000/projects/ChatgptREST/ops/data/planning_runtime_pack_golden_queries_v1.json)

### 2.3 planning runtime pack readiness 检查

实际执行：

```bash
./.venv/bin/python ops/check_planning_runtime_pack_release_readiness.py \
  --pack-root artifacts/monitor/planning_reviewed_runtime_pack
```

结果：

- `pack_dir = artifacts/monitor/planning_reviewed_runtime_pack/20260311T083052Z`
- `age_hours = 530.18...`
- `freshness_ok = false`
- `ready = false`

关键代码：

- [check_planning_runtime_pack_release_readiness.py](/vol1/1000/projects/ChatgptREST/ops/check_planning_runtime_pack_release_readiness.py#L17)

pack manifest：

- [manifest.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_reviewed_runtime_pack/20260311T083052Z/manifest.json)

这个结果非常关键：

> planning runtime pack 不是不能用，而是现在仓里最新 pack 已经老了，按自己的 release-readiness 规则都不该算 ready。

### 2.4 live context resolve smoke

我直接用本地 runtime 做了两个 planning role 的 resolve smoke。

结果文件：

- [/tmp/ctx_live_pack_budget_20260402.json](/tmp/ctx_live_pack_budget_20260402.json)
- [/tmp/ctx_live_pack_shared_cognition_20260402.json](/tmp/ctx_live_pack_shared_cognition_20260402.json)

结论：

1. 对 `预算关键数字`，`planning_pack_hits = 2`，而且 `planning_priority_mode = planning_role_explicit_highest`。
2. 对 `shared cognition 四端 联合验收`，`planning_pack_hits = 0`，直接退到普通 `kb`。

这说明：

> planning pack 对它覆盖的旧领域能命中，但对你现在高频的部分 planning 主题并不可靠。

### 2.5 work memory import + retrieval smoke

实际执行：

1. 用 `planning` 真实 manifest 做 dry-run
2. 用全新 temp DB 做 execute
3. 再用 `ContextResolver` 做 retrieval smoke

结果文件：

- [/tmp/work_memory_import_dry_run_20260402.json](/tmp/work_memory_import_dry_run_20260402.json)
- [/tmp/work_memory_import_execute_fresh_20260402.json](/tmp/work_memory_import_execute_fresh_20260402.json)

结果摘要：

- dry-run：
  - `entry_count = 27`
  - `ready = 24`
  - `manual_review_required = 3`
  - `blocked = 0`
- fresh execute：
  - `written = 24`
  - `skipped = 3`
  - `duplicate = 0`
  - `blocked = 0`

runbook 和 live import 记录：

- [work_memory_backfill_importer_runbook_v1.md](/vol1/1000/projects/ChatgptREST/docs/ops/work_memory_backfill_importer_runbook_v1.md#L22)
- [2026-03-31_work_memory_live_import_and_review_queue_status_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-31_work_memory_live_import_and_review_queue_status_v1.md#L13)

更重要的是，retrieval smoke 真把 `Active Context` 组出来了，能看到：

- `Active Project Map`
- `Decision Ledger`
- `work_memory_scope_hits = account_role`
- `work_memory_query_sensitive = true`

这说明：

> work memory 不是“写进去就完了”，而是真能被 resolve 读出来，并以 planning 任务有用的结构返还。

## 3. 哪些能力已经证明“真好用”

### 3.1 work memory

这是这轮最稳的一条线。

理由：

1. importer / manager / resolver / capture 全链测试都过了。
2. 真实 planning manifests 能导入。
3. manual review 队列和 ready write 分流是有效的。
4. resolve 能把 `active_project + decision_ledger` 组装回 `Active Context`。

关键代码：

- [work_memory_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_manager.py#L58)
- [work_memory_importer.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_importer.py#L16)
- [tests/test_work_memory_importer.py](/vol1/1000/projects/ChatgptREST/tests/test_work_memory_importer.py#L195)
- [tests/test_context_service_work_memory.py](/vol1/1000/projects/ChatgptREST/tests/test_context_service_work_memory.py#L410)

判断：

> 这条线不该重构，应该补齐真实入口 capture。

### 3.2 planning runtime pack

它是“局部真好用”，不是“整体已经够好用”。

理由：

1. pack search 的 gate 行为是对的，只放行 runtime-visible atoms。
2. consult/recall 的 opt-in 行为是对的。
3. 在它覆盖的 golden queries 上，离线验证是过的。
4. 但 freshness 已失效，live coverage 也明显不够。

关键代码：

- [tests/test_planning_runtime_pack_search.py](/vol1/1000/projects/ChatgptREST/tests/test_planning_runtime_pack_search.py#L202)
- [tests/test_advisor_consult.py](/vol1/1000/projects/ChatgptREST/tests/test_advisor_consult.py#L402)
- [tests/test_cognitive_api.py](/vol1/1000/projects/ChatgptREST/tests/test_cognitive_api.py#L1321)

判断：

> 这条线该补齐，不该重构。

## 4. 哪些能力只是“存在，但对 planning 当前帮助有限”

### 4.1 通用向量检索

它能用，但不是 planning 当前效果的核心来源。

原因：

1. 你现在真正有效的是 reviewed pack 和 work memory，不是 generic vector recall。
2. 早前审计就写过，vector coverage 相对 FTS 稀疏。
3. 当前 planning 的 live resolve 成败，不主要取决于向量召回。

证据：

- [2026-03-19_memory_kb_graph_inventory_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_memory_kb_graph_inventory_audit_v1.md#L103)
- [vector_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kb/vector_store.py#L1)

### 4.2 edge-rich knowledge graph / multi-graph query

它们不是没用，但对 `planning` 当前不是第一优先级。

原因：

1. hot path 真正用的是 `atoms_fts + promotion/quality gate`，不是复杂图边推理。
2. `graph_service` 现在已经混了 `business / repo_code / issue_execution`，这对更广的平台有价值，但不是你现在的 planning 主目标。

证据：

- [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py#L61)
- [graph_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/graph_service.py#L716)
- [tests/test_cognitive_api.py](/vol1/1000/projects/ChatgptREST/tests/test_cognitive_api.py#L504)

判断：

> 对 planning 现在应降级/后置，不该重构后再硬推回主线。

## 5. 我现在给的处理建议

### 5.1 planning runtime pack：补齐，不重构

优先补这 4 件事：

1. `freshness`
   - pack 不能继续停在 `2026-03-11`
   - 至少让 refresh/export/check readiness 成为持续流程
2. `coverage`
   - golden queries 不能只覆盖预算/104/十五五/授权矩阵
   - 需要加入你现在高频的 planning 主题：
     - shared cognition
     - 会议沉淀
     - 项目现状诊断
     - 人员/任务规划
3. `live acceptance`
   - 不只验证离线 query 命中
   - 要验证 `ContextResolver.resolve()` 对真实 planning query 的命中效果
4. `staleness gating`
   - readiness=false 时，不要再把它当“可依赖 planning 热路径”

### 5.2 work memory：继续补齐真实入口，不重构

优先补这 4 件事：

1. 从会议录音/转写/聊天材料/文件 intake 自动抽取
2. 自动写入 `post_call_triage / handoff / active_project / decision_ledger`
3. 把 `task_id / checkpoint / memory writeback` 接稳
4. 验证“不同入口继续同一任务”时，是否真能恢复上下文

### 5.3 KB / graph：保留底座，控制扩张

当前更合理的定位是：

1. `KB FTS / registry / writeback` = evidence working set
2. `canonical atom store` = 长期正式知识底盘
3. `edge-rich graph / multi-graph query` = 后置层

## 6. 最终判断

如果你问我现在是“补齐”还是“重构”，我的答案是：

1. `work memory`：补齐
2. `planning runtime pack`：补齐
3. `KB / vector / graph`：降级定位，别重构成更大的平台

真正需要重构的不是底层知识系统，而是：

> `planning runtime pack` 的持续刷新与覆盖策略，和 `work memory` 的真实入口写回链。

