# 2026-04-07 EvoMap Scope Project Groundwork Review Packet for Claude v1

## 审核目标

请审核 `B0` 地基批次是否正确完成了 EvoMap `scope_project` / `scope_component` 的基础对齐，并确认这批改动适合作为后续 `project_id` 主链贯穿的前置条件。

## 变更范围

- [schema.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/schema.py)
- [db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/db.py)
- [ingest_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/ingest_service.py)
- [backfill_evomap_scope_project.py](/vol1/1000/projects/ChatgptREST/scripts/backfill_evomap_scope_project.py)
- [test_evomap_scope_project.py](/vol1/1000/projects/ChatgptREST/tests/test_evomap_scope_project.py)
- [test_cognitive_api.py](/vol1/1000/projects/ChatgptREST/tests/test_cognitive_api.py)

## 期望审核点

### 1. schema / DB / dataclass 是否真正对齐

重点看：
- `Atom` dataclass 是否已不再静默丢 `scope_project / scope_component`
- fresh DB 和 legacy DB 是否都能得到这两个列
- scope 索引的位置是否正确从静态 `_DDL` 移到了 migration 后

### 2. 写入默认继承逻辑是否合理

当前优先级：
1. atom 显式字段
2. applicability JSON
3. episode -> document project

请重点审：
- 这条优先级是否干净
- 是否会意外覆盖显式 scope
- 是否会对 duck-typed atom / fake atom 造成不兼容

### 3. governed ingest 路径是否已吃到 project scope

请确认：
- `_mirror_into_graph()` 显式 `scope_project=item.project_id`
- `test_knowledge_ingest_writes_kb_and_graph` 已覆盖 runtime graph atom 上的 `scope_project`

### 4. backfill 脚本边界是否正确

请重点看：
- 是否只做数据修复，不和 `init_schema()` 混边界
- repo-root bootstrap 是否必要且正确
- dry-run / write 输出是否足够作为 harness 记录

### 5. 对后续 `C + D` 是否构成有效前置

请判断：
- 这批改动后，`project_id` 贯穿 retrieval/context/memory 是否还存在明显地基缺口
- 是否还需要在 `B0` 再补别的底层字段或 migration 才适合进入下一阶段

## 已知 live 结果

`scripts/backfill_evomap_scope_project.py --write` 在 runtime DB 上的结果：

```python
{
  'updates': {
    'scope_project_from_applicability': 53743,
    'scope_project_from_documents': 24033,
    'scope_component_from_applicability': 5
  },
  'remaining': {
    'blank_scope_project': 31,
    'blank_scope_component': 103922
  }
}
```

这批次的预期不是把 `scope_component` 历史数据全部治理完，而是：
- `scope_project` 基本补齐
- `scope_component` 通道打通

## 希望 Claude 重点挑战的方向

1. `scope_component` 目前只做轻治理，会不会给后续 retrieval/memory 造成误导
2. `KnowledgeDB._prepare_atom_for_write()` 是否应该更严格地区分 dataclass atom 和 fake atom
3. live backfill 留下的 `31` 条 blank `scope_project` 是否需要在本阶段继续处理，还是可以进入 `C + D`
