# 2026-04-02 Planning Knowledge Effectiveness Validation v1

## 1. 结论先说

这轮我不是在看“有没有做出来”，而是在看“现在到底好不好用”。

当前结论很明确：

1. `planning durable work memory` 已经证明是真能用，应该补齐，不该重构。
2. `planning reviewed runtime pack` 结构是对的、部分 query 也能命中，但当前只有“半健康”状态，最大问题是 `freshness` 和 `active atom coverage`，应该补齐，不该重构。
3. `KB / vector / graph` 是真实可用的底座，但对 `planning` 当前的直接效果不如 `reviewed pack + work memory`，不该继续被当成 planning 第一主线。

一句话：

> 这条 planning 知识主线优先补齐，不宜重构。

## 2. 这轮实际做了哪些验证

### 2.1 定向 pytest

我实际跑了下面三组：

```bash
./.venv/bin/pytest -q tests/test_planning_runtime_pack_search.py tests/test_controller_engine_planning_pack.py
./.venv/bin/pytest -q tests/test_work_memory_importer.py tests/test_work_memory_manager.py tests/test_context_service_work_memory.py tests/test_capture_work_memory.py
./.venv/bin/pytest -q tests/test_kb_hub.py tests/test_kb.py tests/test_funnel_graph.py tests/test_advisor_consult.py -k 'planning_review or planning_pack or graph or kb or recall or evidence_pack'
```

结果：

- `planning runtime pack / planning_pack`：`7 passed`
- `work memory`：`32 passed`
- `KB / graph / recall`：`48 passed`

### 2.2 planning runtime pack 离线验证

我实际跑了：

```bash
./.venv/bin/python ops/run_planning_runtime_pack_offline_validation.py --output-dir /tmp/planning_runtime_pack_validation_20260402
```

结果：

- `docs = 116`
- `atoms = 226`
- `query_count = 4`
- `domain_hits = 4`
- `bucket_hits = 4`
- `token_hits = 4`
- `ok = true`

证据：

- [/tmp/planning_runtime_pack_validation_20260402/summary.json](/tmp/planning_runtime_pack_validation_20260402/summary.json)

### 2.3 runtime pack readiness / sensitivity

我实际跑了：

```bash
./.venv/bin/python ops/audit_planning_runtime_pack_sensitivity.py
./.venv/bin/python ops/check_planning_runtime_pack_release_readiness.py --max-age-hours 72
```

结果：

- sensitivity audit：`ok = true`
- release readiness：`ready = false`

根因：

- `freshness_ok = false`
- `age_hours ≈ 530`

也就是：

> 不是 pack 结构坏了，而是当前 live pack 太旧。

### 2.4 work memory 真实 manifest smoke

我实际跑了两步：

#### A. dry-run

```bash
env OPENMIND_MEMORY_DB=/tmp/work_memory_import_smoke_20260402.db \
  ./.venv/bin/python -m chatgptrest.cli work-memory import-manifest \
  --manifest /vol1/1000/projects/planning/docs/backfill/active_project_seed_manifest_v1.json \
  --manifest /vol1/1000/projects/planning/docs/backfill/decision_ledger_seed_manifest_v1.json \
  --dry-run \
  --only-gate all \
  --json-out /tmp/work_memory_import_dry_run_20260402.json \
  --report-out /tmp/work_memory_import_dry_run_20260402.md
```

结果：

- `entry_count = 27`
- `ready = 24`
- `manual_review_required = 3`
- `blocked = 0`

#### B. execute ready

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

- `written = 24`
- `skipped = 3`
- `blocked = 0`

证据：

- [/tmp/work_memory_import_dry_run_20260402.json](/tmp/work_memory_import_dry_run_20260402.json)
- [/tmp/work_memory_import_execute_ready_20260402.json](/tmp/work_memory_import_execute_ready_20260402.json)

### 2.5 context resolve live smoke

我实际把真实 query 丢给 `ContextResolver`，并把结果落盘：

- `2026预算关键数字汇总`
- `104 模组量产导入计划`
- `横向应用事业部 十五五规划 对内 领导 审阅稿`
- `硬门槛授权矩阵`
- `shared cognition 四端 联合验收`

证据：

- [/tmp/planning_context_resolve_live_20260402.json](/tmp/planning_context_resolve_live_20260402.json)
- [/tmp/planning_runtime_pack_search_live_20260402.json](/tmp/planning_runtime_pack_search_live_20260402.json)

## 3. 验证后得出的硬结论

### 3.1 work memory 已经是真可用

这条线最硬的证据不是测试数量，而是：

1. 真实 `planning` manifests 能被导入
2. `ready` 和 `manual_review_required` 被正确分流
3. `ContextResolver` 真能组出 `Active Project Map + Decision Ledger`

比如在 `shared cognition 四端 联合验收` 这个 query 上，实际命中了：

- `AP-007`
- `AP-006`
- `DCL-20260329-SC-BLOCKER`
- `DCL-20260330-LTM-PROJECTIONONLY`

这说明：

> work memory 不是“设计过”，而是已经能支撑 planning 上下文恢复。

### 3.2 runtime pack 结构可用，但运维和 coverage 不够

runtime pack 这条线不是空壳，但也不能说现在“够好了”。

实际情况是：

1. 离线 golden-query validation 能过
2. live `ContextResolver` 对前 3 个 planning query 能命中 `planning_pack`
3. 但 readiness 已因 `freshness_ok=false` 变成 `ready=false`
4. 而且 `硬门槛授权矩阵` 这种真实 planning query，当前 live pack search 是 `0 hits`

更关键的是，这个 `0 hits` 不是搜索函数坏了，而是那篇文档在 canonical DB 里对应 atom 目前还是：

- `promotion_status = candidate / staged`
- `groundedness = 0.0`

所以被 runtime gate 挡掉了。

这说明：

> runtime pack 最大的问题不是架构错，而是 freshness、active atom promotion 和 live acceptance 没闭环。

### 3.3 KB / vector / graph 是底座，但对 planning 当前帮助有限

这一层不是没用，但现在的实际效果是：

1. `planning pack` 命中时，帮助很直接
2. `planning pack` 不命中时，系统会退回普通 KB working set
3. 这个 fallback 可能带进不够相关的泛知识内容

在 `2026预算关键数字汇总` 这个 query 上，虽然 `planning_pack_hits = 2`，但后面也混进了普通 KB 的 `AI发展趋势报告` 片段，这说明通用 KB 当前没有足够强的 scope/source gating。

所以这层更适合这样定位：

> 底座 / evidence layer / fallback layer

而不是：

> planning 主答案面

## 4. 这轮最重要的缺口

### 4.1 runtime pack freshness

当前 live pack 太旧，这是硬伤。

### 4.2 runtime pack live acceptance 不够

离线 4-query golden set 太窄，不能代表今天的 planning 高价值 query。

### 4.3 active atom promotion 不够

当前 pack 里有一批文档“被打包进来了”，但 runtime gate 仍然看不到，因为 active/groundedness 没上来。

我本地抽出来的统计是：

- `doc_runtime_visible = 103`
- `doc_pack_but_not_runtime_visible = 13`

其中 blocked examples 包括：

- `条件批准清单_硬门槛动作表（v0.7）`
- `集成测试矩阵（SIT｜v0.2）`
- `指定件三方责任矩阵（客户-供应商-我方）`
- `硬门槛授权矩阵（停投/停采/停产/退场谈判）`

这些文档都在 pack 里，但当前 atom 还是 `candidate`，而且 `groundedness = 0.0`。

### 4.4 ingress 到 work memory 的自动投影还没打通

现在 work memory 已经能：

1. import
2. durable write
3. context recall

但它还没有稳定接住真实 ingress，比如：

- 飞书输入
- 会议录音 / 转写
- 微信转发材料
- 长任务 checkpoint writeback

## 5. 我的判断：补齐，不重构

### 5.1 不建议重构的原因

1. `work memory` 已经有真实效果
2. `runtime pack` 已经能命中真实 planning query
3. 问题集中在 freshness、promotion、coverage、writeback
4. 这些都更像“闭环没做完”，不是“主架构错了”

### 5.2 真正该补的 5 件事

1. `planning runtime pack freshness`
2. 真实 `runtime search` acceptance，不再只靠 4 个老 golden queries
3. planning 关键 doc 的 `active atom promotion + groundedness`
4. `handoff / post_call_triage` 进入真实任务主线
5. 真实 ingress 到 work memory 的自动投影

## 6. 最终建议

### 6.1 继续作为主线保留

1. `planning reviewed runtime pack`
2. `planning-priority context resolution`
3. `active_project / decision_ledger / handoff / post_call_triage`

### 6.2 保留为支撑层

1. `KB FTS`
2. `ArtifactRegistry`
3. `KB writeback`
4. `vector recall`

### 6.3 现在不要放大

1. 图边推理优先化
2. multi-graph query 扩张
3. 把 signals/observer 当 planning 主能力
4. 大规模重构整套知识主线

