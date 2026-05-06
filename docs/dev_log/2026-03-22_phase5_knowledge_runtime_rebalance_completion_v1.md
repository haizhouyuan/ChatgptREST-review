# 2026-03-22 Phase 5 Knowledge Runtime Rebalance Completion v1

## Result

`Phase 5: Knowledge Runtime Rebalance` 已完成。

这次不是只补决策文档，而是把 `split-plane` 真正落成了 live code：

- advisor graph 最终产物写回不再只停在 KB working set
- context resolve 不再只给内容块，也会解释命中了哪一层 plane

## What Changed

### 1. Advisor graph final artifacts now request canonical projection

[chatgptrest/advisor/graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py)
里的 research / report / funnel 三条最终产物写回，现在统一通过 [KnowledgeIngestService](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/ingest_service.py) 进入：

- file artifact writeback
- KB working set registration
- optional canonical EvoMap graph projection

而且返回值会显式标明：

- `knowledge_plane`
- `write_path`
- `accepted`
- `success`

### 2. Context resolve now explains plane selection

[chatgptrest/cognitive/context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
现在会返回：

- `metadata.source_planes`
- `metadata.retrieval_plan`

所以调用方现在可以直接解释：

- 为什么这次命中了 memory / kb / graph / policy
- 哪一层是 working plane
- 哪一层是 canonical knowledge plane

### 3. Telemetry now carries write-path truth

`kb.writeback` 事件现在带：

- `knowledge_plane`
- `write_path`

这让 observer / activity ingest / diagnostics 不再把 “artifact 已写” 和 “canonical graph 已收口” 混成一件事。

## Acceptance

- 不再存在 “写到 KB 但没进 canonical graph” 的模糊状态
- retrieval path 现在能解释为什么命中了哪一层
- research / report / funnel 的 final artifact write path 已经统一

## Verification

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

## Remaining Boundary

- `post_review` 仍主要通过 EventBus / signals plane 回写，不直接生成 canonical knowledge artifact
- `repo_graph` 仍未注入 hot-path context，只通过 degraded 标记与 `/v2/graph/query` 侧路补充
- 本阶段没有开启新的 heavy execution 层
