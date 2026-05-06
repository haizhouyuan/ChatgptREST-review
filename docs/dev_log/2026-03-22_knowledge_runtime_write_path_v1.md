# 2026-03-22 Knowledge Runtime Write Path v1

## Result

`Phase 5` 的写入边界已经从文档决策落成代码主链。

## Canonical Write Path

下面这三条 advisor graph 产物现在不再只停在 KB working set，而是通过 [KnowledgeIngestService](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/ingest_service.py) 显式请求 canonical projection：

- [execute_deep_research](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py)
- [execute_report](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py)
- [execute_funnel](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py)

这些路径统一经过 [_kb_writeback_and_record(...)](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py)，并传入 `knowledge_plane="canonical_knowledge"`。

## Runtime Working Plane

如果 canonical graph projection 被策略阻断、runtime 不可用、或只发生 fallback 文件写入，返回值和 telemetry 现在会显式保留 working-plane 状态，而不是继续含糊地只说 “KB 已写回”。

当前显式状态包括：

- `knowledge_plane`
- `write_path`
- `graph_refs.status`

## Writeback Contract

`kb_writeback` 结果现在至少区分这几类状态：

- `working_only`
- `canonical_requested`
- `canonical_projected`
- `canonical_policy_blocked`
- `canonical_partial_failure`
- `canonical_runtime_unavailable`

这意味着：

- `accepted=true` 表示 artifact 已接收/落盘
- `success=true` 表示整条请求的 write path 成功收口
- partial 或 blocked 不再和 full success 混写

## Telemetry Alignment

[KnowledgeIngestService](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/ingest_service.py) 发出的 `kb.writeback` 事件现在会额外带上：

- `knowledge_plane`
- `write_path`

所以 telemetry / observer / activity ingest 侧可以区分：

- 这是 runtime working write
- 还是 canonical projection write
- canonical projection 是否被策略或 runtime 阻断

## Boundary

本次没有把所有写入都升格成 canonical knowledge。

当前明确仍属于非-canonical 写入的是：

- runtime memory capture
- session-local review/feedback state
- 非 graph_extract 的 `/v2/knowledge/ingest`

但它们的边界现在已经和 advisor graph 最终产物分开了。
