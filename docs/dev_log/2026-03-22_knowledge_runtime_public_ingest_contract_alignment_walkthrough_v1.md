# 2026-03-22 Knowledge Runtime Public Ingest Contract Alignment Walkthrough v1

## Trigger

评审指出一个真实但局部的精度问题：

- `Phase 5` 文档写的是 public ingest response 已显式带 `knowledge_plane / write_path / success`
- 实际 `/v2/knowledge/ingest` 仍只在 `graph_refs` 里暴露 plane/path，顶层没有 `success`

## Independent Judgment

这个问题成立，但它不推翻 `Phase 5`。

- `Phase 5` 的写路和读路主链已经成立
- 剩下的是 public ingest response 没有完全 flatten
- 正确修法是补 contract surface，而不是回退写路实现

## Implementation

1. 给 `KnowledgeIngestItemResult` 增加顶层派生字段：
   - `success`
   - `knowledge_plane`
   - `write_path`
2. 保持 `graph_refs` 原样继续返回，避免丢失细节。
3. 给 cognitive API 测试补上三种典型状态：
   - canonical projected
   - canonical policy blocked
   - canonical partial failure

## Outcome

现在 `/v2/knowledge/ingest` 的 public response 和 advisor graph `kb_writeback` 可以按同一套顶层字段读：

- `success`
- `accepted`
- `knowledge_plane`
- `write_path`
