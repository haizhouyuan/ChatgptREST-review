# 2026-03-22 Phase 5 Knowledge Runtime Rebalance Review v1

## 结论

`Phase 5: Knowledge Runtime Rebalance` 的主链已经成立：

- advisor graph 的 research / report / funnel 最终产物现在都显式请求 canonical projection
- `_kb_writeback_and_record(...)` 返回给 graph 上层的 `kb_writeback` 已经带 `knowledge_plane` / `write_path` / `success`
- `/v2/context/resolve` 已经返回 `metadata.source_planes` 和 `metadata.retrieval_plan`
- `kb.writeback` telemetry 也已经带上 `knowledge_plane` / `write_path`

但这轮还不能写成“所有 write/read surface 都完全收口”。我确认存在 1 个公开 contract 精度问题。

## Findings

### 1. `/v2/knowledge/ingest` 的公开 response 还没有把 write-path truth 提升成顶层字段

文档口径在 [2026-03-22_phase5_knowledge_runtime_rebalance_completion_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-22_phase5_knowledge_runtime_rebalance_completion_v1.md#L23) 和 [2026-03-22_knowledge_runtime_write_path_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-22_knowledge_runtime_write_path_v1.md#L19) 都把 “返回值会显式标明 `knowledge_plane` / `write_path` / `accepted` / `success`” 写得很强。

但公开 ingest surface 目前还不是这个形状：

- [KnowledgeIngestItemResult](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/ingest_service.py#L73) 的 [to_dict](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/ingest_service.py#L84) 只返回：
  - `ok`
  - `accepted`
  - `message`
  - `graph_refs`
- `knowledge_plane` / `write_path` 仍埋在 `graph_refs` 里
- `success` 这个别名也没有出现在公开 item 顶层，只有 `ok`

我本地用开放认证直打 `/v2/knowledge/ingest` 复现到的实际响应也是：

- 顶层 item 有 `ok=true`、`accepted=true`
- `knowledge_plane` / `write_path` 在 `graph_refs.knowledge_plane` / `graph_refs.write_path`
- 没有顶层 `success`

这不是主链功能 bug，但它意味着：

- advisor graph 自己的 `kb_writeback` contract 和公开 `/v2/knowledge/ingest` contract 还没完全统一
- 下游如果按文档冻结口径消费 ingest response，仍要自己钻 `graph_refs`

评审判断：

- 这是中优先级 contract gap
- 不阻断 Phase 5 主链成立
- 但阻止我把这轮签成“write path contract fully flattened across public surfaces”

建议修法：

- 最直接：给 `KnowledgeIngestItemResult.to_dict()` 增加顶层 `knowledge_plane` / `write_path` / `success`
- 更稳健：把 `graph_refs` 保留给 graph-specific payload，但把 write-path truth 抽成公共一层字段，和 graph `kb_writeback` 对齐

## 通过项

以下关键点我重新核过，结论成立：

- [graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py#L726) 的 `_kb_writeback_and_record(...)` 已经把 `knowledge_plane` / `write_path` / `success` 暴露给 advisor graph 上层
- research / report / funnel 三条路径都在 [graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py#L1099)、[graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py#L1198)、[graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py#L1366) 统一请求 `knowledge_plane="canonical_knowledge"`
- [ContextResolver](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py#L113) 返回的 `metadata.source_planes` / `metadata.retrieval_plan` 确实可解释 read path
- `kb.writeback` telemetry 在 [ingest_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/ingest_service.py#L248) 到 [ingest_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/ingest_service.py#L266) 已带 `knowledge_plane` / `write_path`

## 复核命令

我本轮实际复跑/复现了这些：

```bash
./.venv/bin/pytest -q \
  tests/test_advisor_graph.py \
  tests/test_report_graph.py \
  tests/test_funnel_kb_writeback.py \
  tests/test_cognitive_api.py \
  tests/test_substrate_contracts.py

python3 -m py_compile \
  chatgptrest/advisor/graph.py \
  chatgptrest/cognitive/ingest_service.py \
  chatgptrest/cognitive/context_service.py \
  tests/test_advisor_graph.py \
  tests/test_cognitive_api.py
```

另外做了 1 条定向 API 复现：

```bash
OPENMIND_AUTH_MODE=open ./.venv/bin/python - <<'PY'
from fastapi.testclient import TestClient
from chatgptrest.api.app import create_app
...
resp = client.post('/v2/knowledge/ingest', json={...})
print(resp.json())
PY
```

结果确认：

- `accepted` 在 item 顶层
- `knowledge_plane` / `write_path` 在 `graph_refs`
- 没有 item 顶层 `success`

## 总评

这轮可以签成：

- `knowledge runtime mainline rebalanced`

还不能签成：

- `public ingest/writeback contract fully aligned across surfaces`

下一步最值得补的是把 `/v2/knowledge/ingest` 的 item response flatten 到与 graph `kb_writeback` 相同的 write-path contract。
