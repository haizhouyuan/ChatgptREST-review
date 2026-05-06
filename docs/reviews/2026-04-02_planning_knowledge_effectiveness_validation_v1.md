# 2026-04-02 Planning Knowledge Effectiveness Validation v1

## 1. 结论先说

这轮我不再看“有没有代码”，而是看“效果有没有真的出来”。

验证结论是：

1. `planning durable work memory` 已经达到“真能用”的程度，值得继续补齐，不需要重构。
2. `planning reviewed runtime pack` 也达到“功能成立”的程度，但它现在更像一个 **需要持续刷新和收口的受控热路径**，而不是已经闭环的长期主线产品。
3. 通用 `KB / vector` 是有用的支撑层，但对 `planning` 的实际效果目前仍然有噪声泄漏，不能当成正式答案面。
4. `knowledge graph` 不是空架子，但对 `planning` 当前热路径的直接贡献有限；现在更应该压住扩张，而不是重构成更大的图平台。

一句话：

> 当前更像是“主线已经做出来，但效果治理和持续运维没跟上”。对 `planning` 而言，优先动作应是 **补齐**，不是整体 **重构**。

## 2. 这轮做了哪些真实验证

### 2.1 聚焦测试

#### planning runtime pack

命令：

```bash
./.venv/bin/pytest -q \
  tests/test_planning_runtime_pack_search.py \
  tests/test_controller_engine_planning_pack.py \
  tests/test_cognitive_api.py \
  -k 'planning_pack or runtime_pack or planning_review'
```

结果：

- `9 passed`

#### work memory

命令：

```bash
./.venv/bin/pytest -q \
  tests/test_work_memory_importer.py \
  tests/test_work_memory_manager.py \
  tests/test_context_service_work_memory.py \
  tests/test_capture_work_memory.py
```

结果：

- `32 passed`

#### KB / graph / recall

命令：

```bash
./.venv/bin/pytest -q \
  tests/test_kb_hub.py \
  tests/test_kb.py \
  tests/test_funnel_graph.py \
  tests/test_advisor_consult.py \
  tests/test_cognitive_api.py \
  -k 'kb or graph or evomap or recall'
```

结果：

- 选中的 case 全通过

### 2.2 真实 `planning` manifests 导入与召回 smoke

#### dry-run

命令：

```bash
env OPENMIND_MEMORY_DB=/tmp/work_memory_import_smoke_20260402.db \
  ./.venv/bin/python -m chatgptrest.cli work-memory import-manifest \
  --manifest /vol1/1000/projects/planning/docs/backfill/active_project_seed_manifest_v1.json \
  --manifest /vol1/1000/projects/planning/docs/backfill/decision_ledger_seed_manifest_v1.json \
  --dry-run \
  --only-gate all
```

结果：

- `entry_count = 27`
- `ready = 24`
- `manual_review_required = 3`
- `blocked = 0`

#### fresh execute

命令：

```bash
env OPENMIND_MEMORY_DB=/tmp/work_memory_import_smoke_fresh_20260402.db \
  ./.venv/bin/python -m chatgptrest.cli work-memory import-manifest \
  --manifest /vol1/1000/projects/planning/docs/backfill/active_project_seed_manifest_v1.json \
  --manifest /vol1/1000/projects/planning/docs/backfill/decision_ledger_seed_manifest_v1.json \
  --execute \
  --account-id acct-backfill \
  --role-id planning
```

结果：

- `written = 24`
- `skipped = 3`
- `blocked = 0`
- `duplicate = 0`

#### resolver smoke

我用 fresh DB 再跑了两条 query：

1. `shared cognition 四端 联合验收`
2. `会议录音 ASR 知识沉淀`

结果都证明：

- `ok = true`
- `degraded = false`
- `work_memory_query_sensitive = true`
- `scope_hits.active_project = account_role`
- `scope_hits.decision_ledger = account_role`

而且确实打中了导入对象：

- `AP-007`
- `AP-006`
- `DCL-20260329-SC-BLOCKER`
- `DCL-20260330-LTM-PROJECTIONONLY`

代码与运行链路：

- [work_memory_importer.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_importer.py#L16)
- [work_memory_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_manager.py#L58)
- [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py#L131)
- [work_memory_backfill_importer_runbook_v1.md](/vol1/1000/projects/ChatgptREST/docs/ops/work_memory_backfill_importer_runbook_v1.md#L112)

### 2.3 planning runtime pack 实包验证

#### release readiness

命令：

```bash
./.venv/bin/python ops/check_planning_runtime_pack_release_readiness.py \
  --pack-dir artifacts/monitor/planning_reviewed_runtime_pack/20260311T083052Z
```

结果：

- `required_files_ok = true`
- `manifest_ok = true`
- `opt_in_only_ok = true`
- `default_runtime_cutover_disabled_ok = true`
- `freshness_ok = false`
- `ready = false`

这说明：

> pack 结构没坏，但当前仓里现成这包太旧，不能算“release-ready”

#### offline golden-query validation

命令：

```bash
./.venv/bin/python ops/run_planning_runtime_pack_offline_validation.py \
  --pack-dir artifacts/monitor/planning_reviewed_runtime_pack/20260311T083052Z \
  --spec ops/data/planning_runtime_pack_golden_queries_v1.json \
  --output-dir /tmp/planning_runtime_pack_validation_20260402
```

结果：

- `docs = 116`
- `atoms = 226`
- `query_count = 4`
- `domain_hits = 4`
- `bucket_hits = 4`
- `token_hits = 4`
- `ok = true`

这说明：

> pack 的检索质量是成立的，但 freshness / refresh 没跟上

代码与测试：

- [planning_runtime_pack_search.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_runtime_pack_search.py#L39)
- [tests/test_planning_runtime_pack_search.py](/vol1/1000/projects/ChatgptREST/tests/test_planning_runtime_pack_search.py#L180)
- [tests/test_run_planning_runtime_pack_offline_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_run_planning_runtime_pack_offline_validation.py#L84)

### 2.4 当前 live resolve 的一个真实问题

我直接用当前 runtime 跑：

- `query = 预算关键数字`
- `role_id = planning`
- `sources = ('knowledge', 'graph', 'policy')`

结果是：

- `planning_pack_hits = 2`
- `planning_pack_prompt = true`
- 说明 planning pack 确实进了 prompt

但同时也出现了一个很具体的问题：

- 后面混进了无关的通用 KB 内容
- 实际出现的是一个与 query 无关的 `AI 发展趋势` 报告片段

同时：

- `degraded_sources = ['personal_graph_empty']`
- `evomap_hits = null`

这说明：

1. `planning pack` 自己是有效的
2. 通用 KB fallback 还会把噪声带进来
3. graph 在这类 planning query 上当前没有形成稳定帮助

相关代码：

- [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py#L862)
- [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py#L907)
- [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py#L925)

## 3. 我现在对每条能力的判断

### 3.1 `planning durable work memory`

判断：

- `真好用`

理由：

1. 有真实 planning manifests
2. 有 dry-run / execute / review queue / dedup
3. 有真实 query-sensitive recall
4. 打中的对象和 query 语义是对的

结论：

- `补齐`
- 不需要重构

最该补的是：

1. 从真实 ingress 自动写回
2. 新任务/继续任务/branch 判定与 work memory 的联动
3. 多任务并发下的 thread hygiene

### 3.2 `planning reviewed runtime pack`

判断：

- `功能成立，但运维未闭环`

理由：

1. 单测过
2. golden query 过
3. 当前实包 readiness 失败点不是质量，而是 freshness

结论：

- `补齐`
- 不建议重构

最该补的是：

1. review pack 的持续刷新
2. release bundle freshness gate
3. stale pack 失效后的 fallback 策略

### 3.3 `KB / vector`

判断：

- `有用，但现在还不是 planning 的好答案面`

理由：

1. KBHub、registry、writeback 都是真能力
2. 但 live planning resolve 已经证明了噪声泄漏
3. 向量层存在，但不是当前 planning 效果的主要来源

结论：

- `补齐 scope / tag / source gating`
- 不要重构成更大的向量平台

### 3.4 `knowledge graph`

判断：

- `不是空架子，但当前 planning 热路径帮助有限`

理由：

1. canonical knowledge DB 是活的
2. planning 是主语料之一
3. 但当前这轮 live query 里 graph 没形成有效命中，反而 degraded 了 `personal_graph_empty`

结论：

- `先降级看待`
- `后置`
- 不是现在要重构的重点

## 4. 我对“补齐还是重构”的最终判断

### 4.1 该补齐的

1. `work memory`
2. `planning runtime pack`
3. `planning resolve` 的 scope / source gating
4. pack freshness / refresh / readiness 运维

### 4.2 该降级或后置的

1. graph edge 推理扩张
2. multi-graph query 持续平台化
3. 把 generic vector recall 当 planning 主效果来源

### 4.3 现在不建议重构的

1. `work memory` 主链
2. `planning runtime pack` 主链

原因：

> 这两条线已经验证出真实效果了，问题主要在补齐和收口，不在于架构方向彻底错误。

## 5. 最关键的现实判断

如果你问我现在最准确的一句判断，我会用这句：

> `planning` 知识主线已经从“概念”进入“可用但未闭环”阶段；现阶段最需要的是补齐刷新、降噪和写回治理，而不是推倒重构。

