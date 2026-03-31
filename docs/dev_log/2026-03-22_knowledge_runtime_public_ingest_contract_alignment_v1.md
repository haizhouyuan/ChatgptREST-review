# 2026-03-22 Knowledge Runtime Public Ingest Contract Alignment v1

## Result

`Phase 5` 的主链不需要推翻，但 `/v2/knowledge/ingest` 的 public response contract 现在已经补平到和 `kb_writeback` 同一层级。

## What Changed

[KnowledgeIngestItemResult](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/ingest_service.py)
的公开序列化结果现在会在顶层直接返回：

- `success`
- `knowledge_plane`
- `write_path`

同时继续保留：

- `ok`
- `accepted`
- `message`
- `graph_refs`

## Why This Was Needed

`Phase 5 v1` 已经把 advisor graph 写路和 telemetry truth 收口了，但 `/v2/knowledge/ingest` 公开 surface 仍只把 plane/path 放在 `graph_refs` 里。那会造成一个残留不一致：

- graph `kb_writeback` 侧已经可以直接读顶层 `knowledge_plane / write_path / success`
- public ingest response 还需要调用方去 `graph_refs` 里二次拆

这次修正后，两边 contract 终于对齐。

## Verification

```bash
./.venv/bin/pytest -q tests/test_cognitive_api.py tests/test_substrate_contracts.py
python3 -m py_compile chatgptrest/cognitive/ingest_service.py tests/test_cognitive_api.py
```

## Boundary

这次没有改变 ingest 内部写路语义：

- canonical projection 还是由 `graph_extract + graph_mode + evomap runtime availability` 决定
- 这次只补 public response flatten，不重写 Phase 5 的 plane policy
