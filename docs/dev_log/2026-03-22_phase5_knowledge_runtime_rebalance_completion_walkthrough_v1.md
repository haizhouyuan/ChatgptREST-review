# 2026-03-22 Phase 5 Knowledge Runtime Rebalance Walkthrough v1

## Why this phase was needed

在 `Phase 4` 结束后，planning / research 两条主场景已经进了 live path，但知识层还存在一个明显断裂：

- 产物会写进 KB working set
- 但 canonical EvoMap knowledge plane 只在独立 ingest path 上明确
- hot-path context 又没有把命中 plane 的理由说清楚

所以 `Phase 5` 的核心不是“再造一个知识系统”，而是把已经冻结的 split-plane 变成明确的读写契约。

## What was implemented

1. 把 advisor graph 最终写回从 `KBWritebackService` 直写，收成 `KnowledgeIngestService` 驱动的显式 plane write。
2. 给 ingest 结果补上 `knowledge_plane / write_path`，避免 artifact accepted 和 canonical projected 再混写。
3. 给 `ContextResolver` 补 `source_planes / retrieval_plan`，让 hot-path context 对自己的命中层有解释能力。

## Why this boundary is the right one

- `research / report / funnel` 的最终产物属于正式知识，应该请求 canonical projection。
- session continuity、memory capture、运行期 hints 仍然属于 runtime working plane 或 signals plane。
- `repo_graph` 现在还不是 hot-path injected source，所以这次不硬把它塞进 context，而是先把 degraded truth 和 retrieval explanation 做实。

## Outcome

`Phase 5` 完成后，系统对知识层的表述终于和代码一致：

- 写路：知道自己是在写 working plane 还是 canonical plane
- 读路：知道自己为什么命中了 memory / KB / graph / policy
- telemetry：知道 artifact 接收和 canonical 收口不是一回事
