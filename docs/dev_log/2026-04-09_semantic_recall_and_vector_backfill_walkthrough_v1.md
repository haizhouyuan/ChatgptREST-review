# Walkthrough

## 1. 为什么开这轮

在 `Phase 2 live complete` 之后，新的主瓶颈已经不是 `promotion`，而是：

- 真实业务 query 仍然返回 `0`
- EvoMap vector lane 只有 `740`

用户明确给了 3 个真实 query：

- `绿源来访准备`
- `钛虎机器人关节模组合作`
- `两轮车车轮市场竞争分析`

所以本轮不再做抽象方案，而是直接围绕这 3 个 query 做 semantic recall + vector backfill。

## 2. 做了什么

### 2.1 Retrieval

在 [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py) 里：

- 增加 planning explicit 的中文 query normalization
- 对 `来访准备 / 合作洽谈 / 竞争分析` 做同义扩展
- substring fallback 增加 `canonical_question / document.title / raw_ref`
- `planning explicit` 明确允许 `status=reviewed`
- fallback 收窄到 `project_id`

### 2.2 Vector backfill

在 [vector_lane.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/vector_lane.py) 和 [run_evomap_vectorization.py](/vol1/1000/projects/ChatgptREST/ops/run_evomap_vectorization.py) 里：

- 增加 batch embedding
- 增加 `save_every_batches`
- 把“最后一次性写盘”的模式改成周期性落盘

### 2.3 Harness

新增：

- [run_evomap_semantic_recall_harness.py](/vol1/1000/projects/ChatgptREST/ops/run_evomap_semantic_recall_harness.py)
- [test_run_evomap_semantic_recall_harness.py](/vol1/1000/projects/ChatgptREST/tests/test_run_evomap_semantic_recall_harness.py)

## 3. 关键发现

最重要的 live 发现有 3 个：

1. `绿源` 在 DB 里不是完全没有，但可直接命中的 planning atom 极少，而且很多是 `reviewed + staged`
2. `钛虎` 在当前 planning 语料里没有形成实体级覆盖，只能靠“机器人/关节模组/合作”主题 bridging
3. `planning explicit` 之前查不到，并不只是 tokenization 问题，更是因为 runtime `min_status` 没放 `reviewed`

## 4. 验证

通过的 focused suite：

- `tests/test_evomap_runtime_contract.py`
- `tests/test_evomap_vector_lane.py`
- `tests/test_run_evomap_vectorization.py`
- `tests/test_run_evomap_semantic_recall_harness.py`

live artifacts：

- [evomap_vectorization summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_vectorization/20260408T230927Z/summary.json)
- [evomap_semantic_recall_harness summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_semantic_recall_harness/20260408T231936Z/summary.json)

## 5. 结果怎么表述

正确口径是：

- semantic recall 从 `0/0/0` 提升到 `4/4/5`
- vectors 从 `740` 提升到 `4547`
- 这轮把 semantic recall 做成了可验证、可回归、可继续扩展的工程面

不正确口径是：

- “实体级检索已经完全解决”
- “钛虎已经有充分 planning 知识档案”
- “全 surface 都已同等级提升”
