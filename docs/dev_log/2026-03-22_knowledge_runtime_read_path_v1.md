# 2026-03-22 Knowledge Runtime Read Path v1

## Result

`/v2/context/resolve` 现在不只返回 context blocks，也会返回可解释的 retrieval plan。

## Source Plane Map

[ContextResolver](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py) 现在显式暴露 source-plane 对应关系：

- `memory -> runtime_working`
- `knowledge -> kb_working_set`
- `graph -> canonical_knowledge`
- `policy -> runtime_policy`

这些信息通过 `metadata.source_planes` 返回。

## Retrieval Plan

`metadata.retrieval_plan` 现在会按 source 逐项解释：

- 请求了哪一类 source
- 命中了哪一层 plane
- 是否真正 resolved
- 实际返回了多少 blocks
- 为什么命中或为什么没有命中

这次的重点不是新增更多 retrieval logic，而是把已有 hot-path recall 的命中理由显式化，避免再出现：

- “为什么这次用的是 KB 而不是 graph”
- “为什么 graph requested 但没有命中”
- “repo_graph 为什么只在 degraded_sources 里出现”

## Current Semantics

当前 read path 的正式语义已经可以写清楚：

- `memory` 命中表示身份范围内的 working/episodic/captured memory 有匹配
- `knowledge` 命中表示 `kb_hub` working set 有 evidence hits
- `graph` 命中表示 canonical EvoMap knowledge plane 返回了 promoted atoms
- `policy` 命中表示 runtime policy hints 已基于前述 context 做了派生

## Boundary

本次没有把 `repo_graph` 真正注入 hot-path context。

所以 read path 仍然保留这个边界：

- `personal graph` 是当前 hot-path graph source
- `repo_graph` 仍通过 degraded 标记 + `/v2/graph/query` 单独补充

但现在 `retrieval_plan` 已经能把这件事解释清楚，而不再只靠调用方自己猜。
