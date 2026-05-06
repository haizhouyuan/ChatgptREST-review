# 2026-04-07 EvoMap Scope Project Groundwork Walkthrough v1

## 目标

完成 `B0` 地基批次，把 EvoMap 中 `scope_project` / `scope_component` 的 schema、dataclass、写入链和 live 数据回填对齐，为后续 `project_id` 主链贯穿提供稳定基础。

## 本批次改动

### 1. Schema / dataclass 对齐

- 在 [schema.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/schema.py) 的 `Atom` dataclass 增加：
  - `scope_project`
  - `scope_component`

这修复了 DB 已有列但 `Atom.from_row()` 静默丢字段的问题。

### 2. KnowledgeDB schema / migration 对齐

在 [db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/db.py) 中：

- fresh DDL 的 `atoms` 表新增：
  - `scope_project`
  - `scope_component`
- `init_schema()` 增加 legacy migration：
  - 老 `atoms` 表缺列时自动 `ALTER TABLE`
  - migration 后统一创建 `idx_atoms_scope_project`
  - migration 后统一创建 `idx_atoms_scope_component`

注意：
- scope 索引没有继续留在静态 `_DDL` 中。
- 原因是 legacy DB 若先存在旧版 `atoms` 表，`executescript(_DDL)` 里直接建索引会在列不存在时失败。

### 3. 写入链默认继承

`KnowledgeDB` 新增 atom 写入前规范化：

- `_parse_atom_applicability()`
- `_derive_atom_scope_project()`
- `_derive_atom_scope_component()`
- `_prepare_atom_for_write()`

写入优先级：
1. atom 显式 `scope_project / scope_component`
2. `applicability.project / applicability.component / applicability.scope_component`
3. `episode -> document.project`

覆盖路径：
- `put_atom()`
- `put_atom_if_absent()`
- `bulk_put_atoms()`

兼容性处理：
- 允许 duck-typed fake atom（测试里常见）
- 不假定对象一定有 `scope_project / scope_component / applicability / episode_id`

### 4. cognitive ingest 显式透传

在 [ingest_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/ingest_service.py) 的 `_mirror_into_graph()` 中，创建 `Atom` 时显式设置：

- `scope_project=item.project_id`

这让 governed ingestion 路径从入口开始就带上项目 scope，而不是只依赖下游继承。

### 5. backfill 脚本

新增脚本：

- [backfill_evomap_scope_project.py](/vol1/1000/projects/ChatgptREST/scripts/backfill_evomap_scope_project.py)

能力：
- dry-run 报告 blank scope 现状
- `--write` 执行回填
- 回填来源：
  - `applicability.project`
  - `applicability.component / applicability.scope_component`
  - `episodes -> documents.project`

入口修复：
- 脚本自身会把 repo root 注入 `sys.path`
- 避免 `python scripts/foo.py` 时误吃环境里的旧 `chatgptrest` 包

## 测试

新增：

- [test_evomap_scope_project.py](/vol1/1000/projects/ChatgptREST/tests/test_evomap_scope_project.py)

覆盖：
- `Atom.from_row()` 保留 scope 字段
- legacy `atoms` 表 migration 会补齐 scope 列
- `put_atom()` 从 `episode -> document.project` 推导 `scope_project`
- `put_atom_if_absent()` 保留显式 scope
- `bulk_put_atoms()` 对每个 atom 都做 scope 继承

扩充：

- [test_cognitive_api.py](/vol1/1000/projects/ChatgptREST/tests/test_cognitive_api.py)
  - `test_knowledge_ingest_writes_kb_and_graph` 新增 `graph_atom.scope_project == "ChatgptREST"`

回归通过：

```bash
./.venv/bin/pytest -q tests/test_evomap_scope_project.py tests/test_evomap_db_locking.py
./.venv/bin/pytest -q tests/test_cognitive_api.py -k knowledge_ingest_writes_kb_and_graph
./.venv/bin/pytest -q tests/test_sqlite_inventory.py tests/test_substrate_contracts.py -k "sqlite_inventory or mirror_into_graph_creates_candidate_atom"
```

## Live backfill 结果

先 dry-run：

```python
{'ok': True, 'mode': 'dry_run', 'db': '/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db', 'blank_scope_project': 77807, 'blank_scope_component': 103927}
```

执行 `--write` 后：

```python
{
  'ok': True,
  'mode': 'write',
  'db': '/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db',
  'updates': {
    'scope_project_from_applicability': 53743,
    'scope_project_from_documents': 24033,
    'scope_component_from_applicability': 5
  },
  'remaining': {
    'blank_scope_project': 31,
    'blank_scope_component': 103922
  },
  'delta': {
    'scope_project_filled': 77776,
    'scope_component_filled': 5
  }
}
```

结论：
- `scope_project` 回填基本完成
- `scope_component` 目前历史数据极少，本批次只做通道打通，不做大规模组件级治理

## 风险边界

- `Atom` 是 GitNexus `CRITICAL` 风险对象，本批次只做字段追加与向后兼容，不改现有调用签名和语义分支
- 不把历史数据回填偷偷塞进 `init_schema()`
- 数据修复通过显式脚本执行，保持 schema migration 和 data remediation 的边界清晰

## 下一步

进入 `C + D`：

1. `project_id` 贯穿 `MemoryManager / ContextResolveRequest / ContextResolveOptions / ContextAssembler / signals / telemetry`
2. 同步落地 authority 优先级合同
3. 明确 `prompt_builder` 与 `ContextAssembler` 双注入点的 section ordering 和 token 裁剪保护
