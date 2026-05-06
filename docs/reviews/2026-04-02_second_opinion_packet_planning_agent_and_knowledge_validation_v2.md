# 2026-04-02 Second Opinion Packet: Planning Agent And Knowledge Validation v2

## 1. 这份 v2 是干什么的

这份 `v2` 不是重复 `v1`，而是基于本轮“好不好用”验证完成后的更新版 packet。

目的只有一个：

> 给第二个 reviewer 一份更短、更聚焦、且已经包含真实效果验证结果的审核入口。

如果你只看一份 packet，请看这份 `v2`。

## 2. 这轮现在已经完成到什么程度

这轮不再停留在“能力有没有做出来”，而是已经完成了 4 类验证：

1. 定向 pytest
2. `planning runtime pack` offline validation
3. `planning work memory` 真实 manifest import + recall smoke
4. `ContextResolver` live query smoke

所以这份 packet 对第二个 reviewer 的要求不是“帮我猜”，而是：

1. 帮我复核我对这些验证结果的解释是否准确
2. 帮我判断我得出的“补齐优先，不重构”是否成立

## 3. 当前最小阅读顺序

如果第二个 reviewer 时间有限，我建议按这个顺序读：

1. [2026-04-02_planning_knowledge_effectiveness_validation_v2.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_knowledge_effectiveness_validation_v2.md)
2. [2026-04-02_planning_knowledge_gap_closure_and_rebuild_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_knowledge_gap_closure_and_rebuild_decision_v1.md)
3. [2026-04-02_planning_knowledge_capability_value_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_knowledge_capability_value_matrix_v1.md)
4. [2026-04-02_planning_unified_logical_task_layer_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_unified_logical_task_layer_v1.md)

如果 reviewer 想看证据生成过程，再补读：

1. [2026-04-02_planning_knowledge_effectiveness_validation_walkthrough_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-02_planning_knowledge_effectiveness_validation_walkthrough_v2.md)
2. [2026-04-02_planning_knowledge_gap_closure_and_rebuild_decision_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-02_planning_knowledge_gap_closure_and_rebuild_decision_walkthrough_v1.md)

## 4. 本轮验证后的核心结论

### 4.1 已经可以签字成立的

1. `planning durable work memory` 已经证明是真可用，不只是“实现过”。
2. `planning reviewed runtime pack` 结构方向是对的，也已经能命中一部分真实 planning query。
3. `KB / vector / graph` 是真实存在的支撑层，但不是当前 planning 第一主线。

### 4.2 当前仍然不够好的

1. live `planning runtime pack` 太旧，`release readiness` 已经显示 `ready=false`。
2. live acceptance 还停留在很窄的 query 集，不能代表今天 planning 高频任务。
3. 有一批关键 planning docs 已进 pack，但 atom 仍停在 `candidate / staged`，或 `groundedness=0.0`，所以 live runtime 打不到。
4. `work memory` 已有 durable write + recall，但真实 ingress 到 memory 的自动投影还没打通。
5. `planning pack` 不命中时，普通 KB fallback 还可能带入不够相关的泛知识内容。

### 4.3 当前主判断

一句话冻结：

> `planning` 知识主线当前主要矛盾不是“要不要重写”，而是“能不能把 freshness、promotion、acceptance、writeback 这几个闭环补完”。

## 5. 这轮验证里最硬的证据

### 5.1 pytest

本轮实际跑过并通过：

1. `tests/test_planning_runtime_pack_search.py`
2. `tests/test_controller_engine_planning_pack.py`
3. `tests/test_work_memory_importer.py`
4. `tests/test_work_memory_manager.py`
5. `tests/test_context_service_work_memory.py`
6. `tests/test_capture_work_memory.py`
7. 一组 `KB / graph / recall` 相关聚焦测试

### 5.2 runtime pack offline validation

本轮实际跑过：

```bash
./.venv/bin/python ops/run_planning_runtime_pack_offline_validation.py --output-dir /tmp/planning_runtime_pack_validation_20260402
```

结果：

1. `ok = true`
2. `docs = 116`
3. `atoms = 226`
4. `domain_hits = 4`
5. `bucket_hits = 4`
6. `token_hits = 4`

### 5.3 runtime pack readiness

本轮实际跑过：

```bash
./.venv/bin/python ops/check_planning_runtime_pack_release_readiness.py --max-age-hours 72
```

结果：

1. `ready = false`
2. `freshness_ok = false`
3. `age_hours ≈ 530`

这说明问题不是主结构错，而是 live pack 已经 stale。

### 5.4 work memory 真实 import + recall

本轮实际把 `planning/docs/backfill` 的真实 manifests 导入临时 memory DB，结果：

1. `entry_count = 27`
2. `ready = 24`
3. `written = 24`
4. `manual_review_required = 3`
5. `blocked = 0`

随后在 `ContextResolver` 中，真实 query 已能召回：

1. `active_project`
2. `decision_ledger`

并进入 prompt-safe active context。

### 5.5 live query smoke

本轮用真实 planning query 做了 live resolve，结论不是一边倒“全好”或“全坏”，而是：

1. 前三类真实 planning query 已能命中 `planning_pack`
2. `硬门槛授权矩阵` 这类 query 当前仍会 miss
3. miss 后退回普通 KB 时，确实存在引入泛知识噪声的风险

这正是“补齐闭环”而不是“重写平台”的典型信号。

## 6. 我当前建议第二个 reviewer 重点审核的 5 件事

### A. work memory 判断

我把 `work memory` 判成“已经过了真可用门槛，应补齐不应重构”，这个判断是否成立。

### B. runtime pack 判断

我把 `runtime pack` 判成“半健康，应补 freshness / promotion / acceptance，不应重构主结构”，这个判断是否成立。

### C. KB / vector / graph 定位

我把 `KB / vector / graph` 统一降到“支撑层 / evidence layer / fallback layer”，这个判断是否合理。

### D. 缺口优先级

我当前建议的优先顺序是：

1. `freshness`
2. `live acceptance`
3. `active atom promotion / groundedness`
4. ingress 到 `work memory` 的自动投影
5. planning fallback gating

请 reviewer 判断这个排序是否合理。

### E. 有没有必须重构的硬证据

如果 reviewer 认为应该重构，请明确指出：

1. 主结构哪里错了
2. 当前验证里哪条证据 actually 支持“重构优于补齐”

## 7. 我当前不会再签的说法

为了让 reviewer 聚焦，我也把我现在不会再说的话写清楚：

1. 我不会再说“做了这些能力，所以应该没问题”。
2. 我不会再说“图谱很重要，所以继续往大平台做”。
3. 我不会再说“只要有向量检索，planning 就能好用”。
4. 我不会再说“runtime pack 不能用”。

更准确的说法是：

1. `work memory` 已经能用
2. `runtime pack` 已经部分能用，但还不稳
3. 当前最缺的是闭环，不是抽象层

## 8. Reviewer 输出建议格式

为了让 second opinion 更有用，我建议 reviewer 输出时至少分 3 段：

1. `核验通过`
   哪些判断成立
2. `发现问题`
   哪些结论说重了、说轻了、遗漏了
3. `决策建议`
   最终是：
   - `补齐优先`
   - `局部重构`
   - `整体重构`

## 9. 当前冻结口径

如果 reviewer 只需要记一句话，请用这句：

> 当前 `planning` 知识主线已经出现真实效果，主问题不是“有没有能力”，而是“这条主线能不能稳定、持续、低噪声地服务 planning 日常工作”；因此现阶段更应优先补齐闭环，而不是大规模重构。
