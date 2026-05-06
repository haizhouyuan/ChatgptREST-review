# 2026-04-02 Planning Knowledge Effectiveness Verification v1

## 1. 结论先说

这轮我不再只看“代码存在”，而是看“效果是否真的出来”。

结论分 4 条：

1. `planning runtime pack` **不是没用**，但它现在的真实状态是：**结构正确、热路径可用、运营 freshness 失效、验证口径偏乐观**。
2. `planning durable work memory` **是真好用**，而且比 runtime pack 更接近你要的工作型能力。
3. 通用 `KB / vector` **能用，但只能算支撑层**；向量检索不够强，不值得当 planning 主能力。
4. `knowledge graph` **真正值钱的是 canonical atom + promotion gate**，不是继续放大“多图查询平台”。

所以我的判断不是“重构这整套”，而是：

> `planning` 这条知识主线 **优先补齐，不宜推倒重构**；但需要立刻承认 `runtime pack` 目前存在 freshness 和 runtime validation gap。

## 2. 这轮实际做了哪些验证

### 2.1 定向测试

我跑了 4 组定向验证：

1. `planning runtime pack / planning pack routing`
2. `work memory`
3. `planning runtime pack offline validation / release readiness / sensitivity / bundle`
4. `KB / funnel graph`

结果：

- `planning runtime pack` 相关：
  - `tests/test_planning_runtime_pack_search.py` = 2 passed
  - `tests/test_controller_engine_planning_pack.py` = 5 passed
  - `tests/test_advisor_consult.py` 里 `planning_review` 相关 = 4 passed
  - `tests/test_cognitive_api.py` 里 `planning_pack` 相关 = 1 passed
- `work memory` 相关：
  - `tests/test_capture_work_memory.py` = 2 passed
  - `tests/test_context_service_work_memory.py` = 9 passed
  - `tests/test_work_memory_importer.py` = 9 passed
  - `tests/test_work_memory_manager.py` = 12 passed
- `planning runtime pack` sidecar 校验：
  - `tests/test_run_planning_runtime_pack_offline_validation.py`
  - `tests/test_check_planning_runtime_pack_release_readiness.py`
  - `tests/test_audit_planning_runtime_pack_sensitivity.py`
  - `tests/test_build_planning_runtime_pack_release_bundle.py`
  - 共 8 passed
- `KB / graph` 相关：
  - `tests/test_kb_hub.py` = 12 passed
  - `tests/test_kb.py` = 10 passed
  - `tests/test_funnel_graph.py` = 15 passed

相关路径：

- [tests/test_planning_runtime_pack_search.py](/vol1/1000/projects/ChatgptREST/tests/test_planning_runtime_pack_search.py)
- [tests/test_controller_engine_planning_pack.py](/vol1/1000/projects/ChatgptREST/tests/test_controller_engine_planning_pack.py)
- [tests/test_advisor_consult.py](/vol1/1000/projects/ChatgptREST/tests/test_advisor_consult.py)
- [tests/test_cognitive_api.py](/vol1/1000/projects/ChatgptREST/tests/test_cognitive_api.py)
- [tests/test_work_memory_importer.py](/vol1/1000/projects/ChatgptREST/tests/test_work_memory_importer.py)
- [tests/test_work_memory_manager.py](/vol1/1000/projects/ChatgptREST/tests/test_work_memory_manager.py)
- [tests/test_context_service_work_memory.py](/vol1/1000/projects/ChatgptREST/tests/test_context_service_work_memory.py)
- [tests/test_capture_work_memory.py](/vol1/1000/projects/ChatgptREST/tests/test_capture_work_memory.py)
- [tests/test_run_planning_runtime_pack_offline_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_run_planning_runtime_pack_offline_validation.py)
- [tests/test_check_planning_runtime_pack_release_readiness.py](/vol1/1000/projects/ChatgptREST/tests/test_check_planning_runtime_pack_release_readiness.py)
- [tests/test_audit_planning_runtime_pack_sensitivity.py](/vol1/1000/projects/ChatgptREST/tests/test_audit_planning_runtime_pack_sensitivity.py)
- [tests/test_build_planning_runtime_pack_release_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_build_planning_runtime_pack_release_bundle.py)
- [tests/test_kb_hub.py](/vol1/1000/projects/ChatgptREST/tests/test_kb_hub.py)
- [tests/test_kb.py](/vol1/1000/projects/ChatgptREST/tests/test_kb.py)
- [tests/test_funnel_graph.py](/vol1/1000/projects/ChatgptREST/tests/test_funnel_graph.py)

### 2.2 实际 smoke

除了单测，我还跑了 4 个更像真实使用的 smoke：

1. 当前 live `planning runtime pack` 的 release readiness
2. 当前 live `planning runtime pack` 的 offline validation
3. 直接调用 `search_planning_runtime_pack()` 做查询
4. 用真实 `planning` backfill manifest 导入 `work memory`，再跑 `ContextResolver.resolve()`

## 3. 验证后的真实判断

## 3.1 `planning runtime pack`：有用，但现在是“半健康”

### 已证明真有效的部分

1. `ContextResolver` 在 `role_id=planning` 时，确实会把 `planning_pack` 放到知识热路径前面。
2. `search_planning_runtime_pack()` 确实会从 release bundle + canonical DB 组合出运行时可消费的 hits。
3. 这条链不是只在概念层成立，实际查询：
   - `2026预算关键数字汇总` 有 2 hits
   - `104 模组量产导入计划` 有 3 hits
   - `横向应用事业部 十五五规划 对内 领导 审阅稿` 有 3 hits

代码：

- [planning_runtime_pack_search.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_runtime_pack_search.py)
- [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)

### 已证明存在问题的部分

最关键的问题不是“搜不到任何东西”，而是：

> 当前验证体系把一部分“结构正确”误当成了“运行时好用”。

我实际跑出来两个相互冲突的结果：

1. `ops/run_planning_runtime_pack_offline_validation.py` 返回：
   - `docs=116`
   - `atoms=226`
   - `query_count=4`
   - `ok=true`
2. 但我直接调用 `search_planning_runtime_pack()` 跑 golden queries 时：
   - `硬门槛授权矩阵` = `0 hits`

原因也查到了：

`offline validation` 根本不走真实 runtime search，它只是对 `docs.tsv` 做 token/title/domain/source_bucket 排序，不查 canonical DB，也不走 active/promotion runtime gate。

代码：

- [run_planning_runtime_pack_offline_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_runtime_pack_offline_validation.py)

对应运行时真正的 gate 在这里：

- [planning_runtime_pack_search.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_runtime_pack_search.py)

我还直接查了 canonical DB：

- `doc_planning_f7bf03099395bed4` 这篇“硬门槛授权矩阵”文档当前只有：
  - `candidate = 2`
  - `staged = 4`
  - `active = 0`

所以它虽然在 pack 的 `docs.tsv` 里、也能在离线 doc 排序里命中，但因为没有 active atom，真实热路径就是进不来。

### 运营状态也有问题

当前 live bundle 跑 `check_planning_runtime_pack_release_readiness.py` 的结果是：

- `ready = false`
- `freshness_ok = false`
- `age_hours ≈ 530`

也就是说：

> 这套东西结构没坏，但当前默认 pack 已经过期太久，不该被当作“现在状态健康”。

代码：

- [check_planning_runtime_pack_release_readiness.py](/vol1/1000/projects/ChatgptREST/ops/check_planning_runtime_pack_release_readiness.py)

### 对它的判断

`planning runtime pack` **不该重构**，应该补齐。

要补的不是底层大架构，而是 3 个很具体的缺口：

1. `freshness maintenance`
2. `runtime validation` 必须走真实 search，不是只看 docs.tsv
3. 对关键 doc，如果预期进入热路径，就必须把 `candidate/staged` 提升到足够的 active atom

## 3.2 `planning durable work memory`：现在是真好用

### 已证明真有效的部分

我用真实 planning manifests 跑了导入和 retrieval smoke。

用这两个 manifest：

- [active_project_seed_manifest_v1.json](/vol1/1000/projects/planning/docs/backfill/active_project_seed_manifest_v1.json)
- [decision_ledger_seed_manifest_v1.json](/vol1/1000/projects/planning/docs/backfill/decision_ledger_seed_manifest_v1.json)

结果：

1. fresh temp DB 下：
   - `ready = 24` entries 全部写入
   - `manual_review_required = 3` 被正确跳过
   - `blocked_count = 0`
2. 然后我用同一个 temp DB 跑 `ContextResolver.resolve()`：
   - `context_block_types = ['work_memory_active', 'policy']`
   - `work_memory_scope_hits.active_project = account_role`
   - `work_memory_scope_hits.decision_ledger = account_role`
   - `work_memory_query_sensitive = true`
   - `work_memory_import_hits` 能回出 `active_project + decision_ledger`
   - `degraded_sources = []`

这说明：

> `work memory` 不只是“能存”，而是已经能被 planning 查询命中并回灌成 prompt-safe context。

代码：

- [work_memory_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_manager.py)
- [work_memory_importer.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_importer.py)
- [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)

runbook：

- [work_memory_backfill_importer_runbook_v1.md](/vol1/1000/projects/ChatgptREST/docs/ops/work_memory_backfill_importer_runbook_v1.md)

### 仍然没被验证到位的

`work memory` 不是没缺口，而是缺口不在“有没有这套能力”，而在“还没完全接到你的日常 ingress”：

1. backfill 目前只支持：
   - `active_project`
   - `decision_ledger`
2. 虽然 `WorkMemoryManager` 里已经有：
   - `post_call_triage`
   - `handoff`
   但它们还没像前两类那样形成完整的 planning backfill / live capture 主线。

代码：

- [work_memory_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_manager.py#L58)
- [work_memory_importer.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_importer.py#L19)

### 对它的判断

`work memory` **也不该重构**，而且比 runtime pack 更值得继续补齐。

最该补的是：

1. `post_call_triage`
2. `handoff`
3. 把真实会议纪要/转写/材料 intake 自动投影进这些对象

## 3.3 `KB / vector`：能用，但不够当 planning 主能力

### 已证明有效的部分

相关测试都过了，说明这层不是摆设：

- [tests/test_kb_hub.py](/vol1/1000/projects/ChatgptREST/tests/test_kb_hub.py)
- [tests/test_kb.py](/vol1/1000/projects/ChatgptREST/tests/test_kb.py)

当前 live 数据也说明它在工作：

- `kb_fts_meta = 940`
- `vectors = 150`

这说明：

1. FTS working set 是活的
2. vector 也不是零

### 已证明存在的问题

向量覆盖还是明显稀疏：

- `FTS = 940`
- `vectors = 150`

所以这层目前更像：

> working evidence recall

而不是：

> 足够强的 semantic mainline

### 对它的判断

`KB / vector` **不需要重构**，但也不该继续被当作 `planning` 的第一主件。

它应该保留成：

1. 证据召回层
2. working set
3. report/research 支撑层

## 3.4 `knowledge graph`：底盘有价值，平台化扩张要刹车

### 已证明有效的部分

当前 canonical DB 不是空壳：

- `planning documents = 3350`
- `planning_review_plane documents = 542`

而且真实热路径的价值点也很清楚：

1. `canonical atoms`
2. `promotion gate`
3. `quality / groundedness gate`

### 已证明不该被高估的部分

现在真正决定 runtime hit 的，不是边越多越好，而是：

1. 这个 atom 是否 active
2. groundedness 和 quality 是否过线

所以当前不该继续高估：

1. 图边推理
2. multi-graph query 扩张
3. graph_service 平台化

## 4. 补齐还是重构

### 4.1 我的明确判断

不是重构。

是 **沿主线补齐**。

### 4.2 为什么不是重构

因为真正要的主链已经存在，而且已经能产出效果：

1. `planning pack` 能命中并进 context
2. `work memory` 能导入并恢复 active context
3. `KB` 能做 working evidence recall
4. `canonical graph` 能做 promotion-gated atom store

也就是说，问题不是：

> “方向错了，整套推翻”

而是：

> “主线已经长出来了，但有些关键环节只做到结构正确，还没做到运行态可靠”

### 4.3 最值得补齐的 5 件事

1. `planning runtime pack` freshness 维护
2. 用真实 `search_planning_runtime_pack()` 替换或补充当前离线 doc-token 验证
3. 把关键 planning docs 的 active atom promotion 补齐，不要只停在 `candidate/staged`
4. 把 `post_call_triage / handoff` 接成和 `active_project / decision_ledger` 一样的 planning work-memory 主线
5. 把真实 ingress 材料自动投影到 `work memory`，而不是只靠 backfill

## 5. 最终建议

### 5.1 立即继续投

1. `planning runtime pack`
2. `work memory`

### 5.2 立即补齐

1. runtime freshness
2. runtime hit validation
3. active atom promotion
4. `handoff / post_call_triage`

### 5.3 暂时不要大动

1. 通用 `KB / vector` 架构
2. canonical knowledge DB 主结构

### 5.4 暂时不要再扩

1. 图边推理优先化
2. multi-graph query 平台化
3. signals/observer 过早升格为 planning 主链

