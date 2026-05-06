# Project Scope Threading — 需求定义文档 v1

日期：2026-04-07
作者：Claude Code (claudegac)
状态：待评审

## 0. 本文档的目的

这不是方向性文档，而是可直接执行的需求定义。每个变更集（Changeset）都包含：

- 精确的文件路径和行号
- 精确的字段/签名变更
- SQL DDL / migration 语句
- 验收条件（可测试）
- 依赖关系

---

## 1. 总目标

让 `project_id` 成为 Memory / Retrieval / Context / Signal 主链的一等维度，同时写死上下文优先级合同，防止自动检索结果覆盖人工 authority。

### 1.1 不在范围内

- promotion pipeline 吞吐优化（Phase 5）
- harness-driven 自我进化（Phase 6）
- OpenClaw 入口层增强（Phase 3 of layered architecture）
- 新建 `_project_context.md` 模板（Phase 0，独立任务）

---

## Changeset 1：修复 Atom.scope_project schema 断层

### 1.1 问题

DB 中 `atoms` 表已有 `scope_project` 列（26,120 行非空），但：

1. `schema.py` 的 `Atom` dataclass 没有 `scope_project` 字段
2. `from_row()` 使用 `if k in cls.__dataclass_fields__` 静默丢弃未知列
3. `db.py` 的 `_DDL` 和 P1 migration 都没有 `scope_project`
4. 结果：即使 DB 有数据，Python 侧 Atom 对象永远拿不到 scope_project

### 1.2 变更

#### 文件 1：`chatgptrest/evomap/knowledge/schema.py`

在 `Atom` dataclass 的 `promotion_reason` 之后（约 line 208）添加：

```python
    # Project/component scoping (P2: project-scope threading)
    scope_project: str = ""        # Project identifier for scoped retrieval
    scope_component: str = ""      # Component identifier within project
```

#### 文件 2：`chatgptrest/evomap/knowledge/db.py`

在 `_DDL` 的 atoms CREATE TABLE 中（line 94-121），`hash` 行之后添加：

```sql
    scope_project    TEXT NOT NULL DEFAULT '',
    scope_component  TEXT NOT NULL DEFAULT '',
```

在 atoms 索引区（line 122-126）添加：

```sql
CREATE INDEX IF NOT EXISTS idx_atoms_scope_project ON atoms(scope_project);
```

在 `init_schema()` 的 P1 migration 之后（约 line 335）添加 P2 migration：

```python
                # P2 Migration: add scope_project/scope_component columns
                try:
                    atom_cols_p2 = {r[1] for r in conn.execute("PRAGMA table_info(atoms)").fetchall()}
                    p2_columns = [
                        ("scope_project", "TEXT NOT NULL DEFAULT ''"),
                        ("scope_component", "TEXT NOT NULL DEFAULT ''"),
                    ]
                    p2_added = []
                    for col_name, col_def in p2_columns:
                        if col_name not in atom_cols_p2:
                            conn.execute(f"ALTER TABLE atoms ADD COLUMN {col_name} {col_def}")
                            p2_added.append(col_name)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_atoms_scope_project ON atoms(scope_project)")
                    if p2_added:
                        logger.info("P2 migration: added columns %s to atoms", p2_added)
                except Exception as e:
                    logger.debug("P2 migration check: %s", e)
```

### 1.3 验收条件

1. `Atom.from_row(dict(row))` 能正确读取 DB 中已有的 `scope_project` 值
2. 新建 Atom 对象默认 `scope_project=""`
3. 已有 26,120 行 scope_project 非空数据不受影响
4. `pytest tests/ -k atom` 全部通过

### 1.4 依赖

无。这是所有后续 changeset 的前置条件。

---

## Changeset 2：RetrievalConfig + retrieve() 增加 project 过滤

### 2.1 问题

`retrieval.py` 的 `retrieve()` 管线没有任何 project 过滤。FTS5 搜索返回全库候选，pre-filter 只看 stability/status/promotion_status。

### 2.2 变更

#### 文件：`chatgptrest/evomap/knowledge/retrieval.py`

**变更 A**：`RetrievalConfig` dataclass（line 74-107）添加字段：

```python
    # Project scope filter: empty = no filtering (backward compatible)
    scope_project: str = ""
```

**变更 B**：`retrieve()` 函数的 Step 2 pre-filter（line 306-315），在 `promotion_status` 检查之后添加 project 过滤：

```python
        # Project scope filter
        if cfg.scope_project and atom.scope_project and atom.scope_project != cfg.scope_project:
            continue
```

逻辑说明：
- `cfg.scope_project` 为空 → 不过滤（向后兼容）
- `atom.scope_project` 为空 → 不排除（未标注项目的 atom 对所有项目可见）
- 两者都非空且不匹配 → 排除

这是 soft filter：未标注的 atom 不会被误杀。

### 2.3 验收条件

1. `retrieve(db, "planning 规则", RetrievalConfig(scope_project="planning"))` 只返回 `scope_project="" or "planning"` 的 atoms
2. `retrieve(db, "planning 规则", RetrievalConfig())` 行为不变（无过滤）
3. 性能：pre-filter 是内存操作，不增加 DB 查询

### 2.4 依赖

Changeset 1（Atom 必须先有 scope_project 字段）

---

## Changeset 3：MemoryManager 增加 project_id 维度

### 3.1 问题

`memory_manager.py` 的 identity scoping 有 5 个维度（session_id, agent_id, role_id, account_id, thread_id），没有 project_id。所有 memory 操作（stage, recall, dedup）都无法按项目隔离。

### 3.2 变更

#### 文件：`chatgptrest/kernel/memory_manager.py`

**变更 A**：DDL（约 line 94-139），在 `thread_id` 之后添加列：

```sql
    project_id   TEXT NOT NULL DEFAULT '',
```

**变更 B**：`_IDENTITY_FIELDS` 元组（约 line 210）：

```python
_IDENTITY_FIELDS = ("agent_id", "role_id", "session_id", "account_id", "thread_id", "project_id")
```

**变更 C**：`_upgrade_schema()` migration 列表中添加：

```python
("project_id", "TEXT NOT NULL DEFAULT ''"),
```

**变更 D**：添加索引（在 migration 逻辑中）：

```sql
CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project_id);
```

**变更 E**：`stage()` 方法（约 line 300-385）的 INSERT 语句和参数列表中添加 `project_id`。

**变更 F**：`get_working_context()` 方法（约 line 436-448）：当 `project_id` 非空时，WHERE 条件增加 `AND project_id = ?`。

**变更 G**：`get_episodic()` 方法：identity WHERE 子句自动包含 project_id（因为它在 `_IDENTITY_FIELDS` 中）。

### 3.3 验收条件

1. `stage(content="x", project_id="planning")` 写入的记录 project_id="planning"
2. `get_working_context(session_id="s1", project_id="planning")` 只返回该项目的记录
3. `get_working_context(session_id="s1")` 行为不变（project_id="" 不过滤）
4. dedup 在同一 project_id 内生效
5. 已有记录（project_id=""）不受影响

### 3.4 依赖

无。可与 Changeset 1-2 并行。

---

## Changeset 4：WorkMemoryManager scope_candidates 增加 project_id

### 4.1 问题

`work_memory_manager.py` 的 `_QUERY_FIELDS` 已有 `project_id`（用于评分 +4.0），但 `_scope_candidates()` 生成的候选 scope 组合中没有 project_id。这意味着 project_id 只影响排序，不影响召回范围。

### 4.2 变更

#### 文件：`chatgptrest/kernel/work_memory_manager.py`

**变更 A**：`_scope_candidates()` 方法中，当 `project_id` 非空时，在现有 scope 层级中增加 project 维度的组合。

具体做法：在现有 8 级 scope 层级之上，增加带 project_id 的变体：

```python
# 现有层级（不变）：
# account_role → account_thread → account → thread_role → thread → session_role → session_agent → session

# 新增：当 project_id 非空时，在最高优先级位置插入 project-scoped 变体
if project_id:
    candidates.insert(0, {"project_id": project_id, "account_id": account_id})
    candidates.insert(1, {"project_id": project_id})
```

**变更 B**：`build_active_context()` 签名添加 `project_id: str = ""`。

### 4.3 验收条件

1. `build_active_context(project_id="planning", ...)` 优先返回 project_id="planning" 的记录
2. 无 project_id 时行为不变
3. project scope 优先级高于 account scope

### 4.4 依赖

Changeset 3（MemoryManager 必须先有 project_id 列）

---

## Changeset 5：ContextResolveOptions / ContextResolveRequest 增加 project_id

### 5.1 问题

`context_service.py` 的 `ContextResolveOptions` 和 `routes_cognitive.py` 的 `ContextResolveRequest` 都没有 `project_id`。这是 project scope 进入 runtime context 主链的入口。

### 5.2 变更

#### 文件 1：`chatgptrest/cognitive/context_service.py`

**变更 A**：`ContextResolveOptions` dataclass（约 line 54-70）添加字段：

```python
    project_id: str = ""
```

**变更 B**：`ContextResolver.resolve()` 方法（约 line 157-168），将 `options.project_id` 传递给 assembler 的 `build()` 调用。

**变更 C**：`_LocalOnlyContextAssembler.build()` 方法（约 line 692-704），签名添加 `project_id: str = ""`，并将其传递给：
- `evomap_retrieve()` 调用（通过 RetrievalConfig）
- `self._memory.get_working_context()` 调用
- `self._memory.get_episodic()` 调用

具体改动（约 line 935-941，EvoMap 调用）：

```python
                evomap_hits = evomap_retrieve(
                    self._evomap_db,
                    query,
                    config=runtime_evomap_retrieval_config(
                        surface=EvoMapRetrievalSurface.USER_HOT_PATH,
                        scope_project=project_id,  # 新增
                    ) if runtime_evomap_retrieval_config and EvoMapRetrievalSurface else None,
                )
```

注意：`runtime_evomap_retrieval_config()` 也需要接受 `scope_project` 参数并传递给 `RetrievalConfig`。

#### 文件 2：`chatgptrest/api/routes_cognitive.py`

**变更 A**：`ContextResolveRequest` Pydantic model（约 line 48-63）添加字段：

```python
    project_id: str = ""
```

**变更 B**：`/context/resolve` endpoint handler（约 line 358-381），将 `request.project_id` 映射到 `ContextResolveOptions.project_id`。

#### 文件 3：`chatgptrest/evomap/knowledge/retrieval.py`

**变更 A**：`runtime_retrieval_config()` 函数签名添加 `scope_project: str = ""`，并将其设置到返回的 `RetrievalConfig` 中。

### 5.3 验收条件

1. `POST /context/resolve {"query": "x", "project_id": "planning"}` 返回的 EvoMap 结果只包含 planning 项目的 atoms
2. `POST /context/resolve {"query": "x"}` 行为不变
3. memory recall 结果按 project_id 过滤
4. response 中的 provenance metadata 包含 project_id

### 5.4 依赖

Changeset 1 + 2（retrieval 必须先支持 scope_project）
Changeset 3（memory 必须先支持 project_id）

---

## Changeset 6：ContextAssembler 增加 project_id + authority 源类型

### 6.1 问题

`context_assembler.py` 的 `build()` 没有 `project_id` 参数。更关键的是，`SOURCE_PRIORITY` 中没有 authority anchor 源类型，无法实现优先级合同。

### 6.2 变更

#### 文件：`chatgptrest/kernel/context_assembler.py`

**变更 A**：`SOURCE_PRIORITY` dict（line 143-151）改为：

```python
    SOURCE_PRIORITY = {
        "authority": 0,    # Authority anchor (_project_context.md) — 最高优先级，不可被裁剪
        "semantic": 1,     # User profile / preferences
        "evomap": 2,       # EvoMap knowledge atoms (project-scoped)
        "calendar": 3,     # Schedule awareness
        "obsidian": 4,     # Personal vault notes (real-time)
        "kb": 5,           # Knowledge base evidence
        "working": 6,      # Recent conversation
        "episodic": 7,     # Historical tasks
    }
```

**变更 B**：`TokenBudget` dataclass（line 60-74）添加：

```python
    authority_anchor: int = 800   # Authority anchor — 固定预留，不参与裁剪
```

**变更 C**：`build()` 签名（line 165-174）添加：

```python
    def build(
        self,
        query: str,
        session_id: str = "",
        *,
        project_id: str = "",           # 新增
        authority_content: str = "",     # 新增：authority anchor 内容
        working_limit: int = 10,
        episodic_limit: int = 5,
        semantic_limit: int = 3,
        kb_top_k: int = 5,
    ) -> ContextPack:
```

**变更 D**：`build()` 方法体，在 Step 1（working memory）之前插入 authority 注入：

```python
        # 0. Authority anchor (highest priority, never trimmed)
        if authority_content:
            tokens = self._estimate_tokens(authority_content)
            pack.sources.append(ContextSource(
                source_type="authority",
                priority=self.SOURCE_PRIORITY["authority"],
                content=authority_content,
                token_count=tokens,
                metadata={"source": "authority_anchor"},
            ))
```

**变更 E**：`build()` 中的 memory 和 EvoMap 调用传递 `project_id`：

- `self._memory.get_working_context(session_id=session_id, project_id=project_id)`
- EvoMap retrieve 的 config 中设置 `scope_project=project_id`

**变更 F**：`_apply_budget()` 方法（line 358+），authority 源不参与裁剪：

```python
    def _apply_budget(self, pack: ContextPack) -> ContextPack:
        available = self._budget.available_for_context()
        # Authority sources are never trimmed
        authority_sources = [s for s in pack.sources if s.source_type == "authority"]
        other_sources = [s for s in pack.sources if s.source_type != "authority"]

        authority_tokens = sum(s.token_count for s in authority_sources)
        remaining = available - authority_tokens

        # Sort other sources by priority (lower = higher priority)
        other_sources.sort(key=lambda s: s.priority)

        kept = list(authority_sources)  # authority always kept
        for source in other_sources:
            if remaining >= source.token_count:
                kept.append(source)
                remaining -= source.token_count
            # else: trimmed

        pack.sources = kept
        return pack
```

**变更 G**：`ContextPack` dataclass 添加 `project_id` 字段：

```python
    project_id: str = ""
```

### 6.3 验收条件

1. authority 源永远出现在 context pack 中，即使 token budget 紧张
2. authority 源的 priority=0，排在所有其他源之前
3. 当 token budget 不足时，episodic（priority=7）先被裁剪，authority 永远保留
4. `build(project_id="planning")` 的 EvoMap 和 memory 结果按项目过滤
5. `build()` 无 authority_content 时行为不变

### 6.4 依赖

Changeset 2（RetrievalConfig.scope_project）
Changeset 3（MemoryManager.project_id）

---

## Changeset 7：Signal + TraceEvent 增加 project_id

### 7.1 问题

`signals.py` 的 `Signal` dataclass 和 `event_bus.py` 的 `TraceEvent` dataclass 都没有 `project_id`。telemetry 和 trace 无法按项目聚合。

### 7.2 变更

#### 文件 1：`chatgptrest/evomap/signals.py`

**变更 A**：`Signal` dataclass（约 line 37-44）添加字段：

```python
    project_id: str = ""
```

**变更 B**：`from_trace_event()` classmethod，从 event.data 中提取 project_id：

```python
    @classmethod
    def from_trace_event(cls, event) -> Signal:
        # ... existing code ...
        return cls(
            signal_id=event.event_id,
            trace_id=event.trace_id,
            signal_type=event.event_type,
            source=event.source,
            timestamp=event.timestamp,
            domain=_infer_domain(event.event_type),
            data=event.data,
            project_id=event.data.get("project_id", "") or getattr(event, "project_id", ""),
        )
```

#### 文件 2：`chatgptrest/kernel/event_bus.py`

**变更 A**：`TraceEvent` dataclass 添加字段：

```python
    project_id: str = ""
```

**变更 B**：`to_dict()` 方法包含 `project_id`。

**变更 C**：`create()` classmethod 签名添加 `project_id: str = ""`。

**变更 D**：EventBus 的 DDL（如果有持久化表），添加 `project_id` 列和索引。

**变更 E**：`query()` 方法添加可选 `project_id` 过滤参数。

### 7.3 验收条件

1. `TraceEvent.create(source="advisor", event_type="route", project_id="planning")` 正确携带 project_id
2. `Signal.from_trace_event(event)` 正确提取 project_id
3. `event_bus.query(project_id="planning")` 只返回该项目的事件
4. 已有事件（project_id=""）不受影响

### 7.4 依赖

无。可与其他 changeset 并行。

---

## Changeset 8：prompt_builder 路径的优先级合同

### 8.1 问题

authority anchor 有两条注入路径：

1. **ContextAssembler 路径**：Changeset 6 已覆盖
2. **prompt_builder 路径**：OpenClaw plugin → task_intake.available_inputs → prompt_builder template

`prompt_builder.py` 的 `{available_inputs}` 注入没有 token 预算控制，也没有与 ContextAssembler 输出的优先级协调。如果 available_inputs 中包含 authority anchor 内容，而 ContextAssembler 也注入了同样的内容，会出现重复。

### 8.2 变更

#### 文件 1：`chatgptrest/advisor/prompt_builder.py`

**变更 A**：在 `build()` 方法中（约 line 403-495），对 `available_inputs` 进行结构化解析。当 available_inputs 是 dict 时，识别 `authority_anchor` key：

```python
    # Parse available_inputs for authority anchor
    authority_block = ""
    other_inputs = ""
    if isinstance(available_inputs, dict):
        authority_block = available_inputs.get("authority_anchor", "")
        other_parts = {k: v for k, v in available_inputs.items() if k != "authority_anchor"}
        other_inputs = json.dumps(other_parts, ensure_ascii=False) if other_parts else ""
    elif isinstance(available_inputs, str):
        other_inputs = available_inputs
```

**变更 B**：authority_block 在 system prompt 中以显式标记注入，位于所有其他上下文之前：

```python
    if authority_block:
        system_prompt = f"## Authority Anchor (不可被覆盖)\n\n{authority_block}\n\n---\n\n{system_prompt}"
```

**变更 C**：添加 token 预算上限（硬编码 2000 tokens）防止 available_inputs 过大：

```python
    MAX_AVAILABLE_INPUTS_TOKENS = 2000
    if other_inputs and _estimate_tokens(other_inputs) > MAX_AVAILABLE_INPUTS_TOKENS:
        other_inputs = other_inputs[:MAX_AVAILABLE_INPUTS_TOKENS * 4]  # rough char estimate
        other_inputs += "\n\n[... truncated due to token budget ...]"
```

#### 文件 2：`chatgptrest/advisor/task_intake.py`

**变更 A**：`_derive_available_inputs()` 方法中，当 context_dict 包含 `project_context` 时，将其结构化为 dict 格式，分离 authority_anchor：

```python
    if project_context := context_dict.get("project_context"):
        if isinstance(project_context, dict):
            result["authority_anchor"] = project_context.get("authority_anchor", "")
            # other project context fields go to regular available_inputs
```

### 8.3 验收条件

1. 当 task_intake 包含 authority_anchor 时，它出现在 system prompt 最前面
2. authority_anchor 内容不会被 token 裁剪
3. 当 available_inputs 超过 2000 tokens 时被截断（authority 除外）
4. 当 available_inputs 是纯字符串时行为不变

### 8.4 依赖

无。可独立实施。但必须与 Changeset 6 同时上线，确保两条路径的优先级合同一致。

---

## Changeset 9：context_service._LocalOnlyContextAssembler 的 project_id 贯穿

### 9.1 问题

`context_service.py` 中的 `_LocalOnlyContextAssembler` 是 `ContextAssembler` 的本地包装，它的 `build()` 方法也需要接受和传递 `project_id`。

### 9.2 变更

#### 文件：`chatgptrest/cognitive/context_service.py`

**变更 A**：`_LocalOnlyContextAssembler.build()` 签名（约 line 692-704）添加 `project_id: str = ""`。

**变更 B**：内部调用 `self._assembler.build()` 时传递 `project_id`。

**变更 C**：EvoMap retrieval 调用（约 line 935-941）传递 `scope_project=project_id` 到 RetrievalConfig。

**变更 D**：`ContextResolver.resolve()` 方法（约 line 157-168），从 `options.project_id` 取值传递给 assembler。

### 9.3 验收条件

1. `ContextResolver.resolve(ContextResolveOptions(query="x", project_id="planning"))` 的 EvoMap 结果按项目过滤
2. memory 结果按项目过滤
3. 无 project_id 时行为不变

### 9.4 依赖

Changeset 5 + 6

---

## 2. 上下文优先级合同（跨 Changeset 硬约束）

这不是一个独立 changeset，而是贯穿 Changeset 6 和 Changeset 8 的硬约束。

### 2.1 合同内容

```
优先级（数字越小越高）：

0. Authority Anchor        — _project_context.md 中的人工冻结事实和规则
1. Semantic Memory         — 用户画像/偏好
2. EvoMap Knowledge        — project-scoped 知识原子
3. Calendar                — 日程感知
4. Obsidian                — 个人笔记
5. KB Evidence             — 知识库证据
6. Working Memory          — 近期对话
7. Episodic Memory         — 历史任务
```

### 2.2 合同规则

1. Authority anchor 永远不被 token budget 裁剪
2. 当 authority anchor 与 EvoMap/KB 结果冲突时，authority 永远赢
3. 冲突检测不在本轮实现（Phase 5+ 的 harness 职责），但优先级排序保证 authority 内容在 prompt 中出现在前面，LLM 自然倾向于遵循先出现的指令
4. 两条注入路径（ContextAssembler + prompt_builder）必须遵守同一合同

### 2.3 实现位置

| 路径 | 实现文件 | 机制 |
|------|---------|------|
| ContextAssembler | `context_assembler.py` | SOURCE_PRIORITY["authority"]=0 + _apply_budget() 豁免 |
| prompt_builder | `prompt_builder.py` | authority_block 前置于 system_prompt |

### 2.4 验收条件

1. 构造一个 token budget 只有 2000 的场景，authority(800) + working(1500) + evomap(1200)
2. 预期结果：authority 全部保留，working 保留，evomap 被裁剪
3. 在 prompt_builder 路径中，authority_anchor 出现在 system prompt 最前面

---

## 3. 实施顺序与依赖图

```
Changeset 1 (Atom.scope_project)
    ↓
Changeset 2 (RetrievalConfig + retrieve)
    ↓                                    Changeset 3 (MemoryManager)
    ↓                                        ↓
Changeset 5 (ContextResolveOptions)     Changeset 4 (WorkMemoryManager)
    ↓
Changeset 6 (ContextAssembler + authority)
    ↓
Changeset 9 (context_service 贯穿)

Changeset 7 (Signal + TraceEvent)  ← 独立，可并行
Changeset 8 (prompt_builder)       ← 独立，但必须与 CS6 同时上线
```

### 推荐实施批次

**Batch A（可并行）**：
- Changeset 1：Atom schema 修复
- Changeset 3：MemoryManager project_id
- Changeset 7：Signal/TraceEvent project_id

**Batch B（依赖 Batch A）**：
- Changeset 2：RetrievalConfig + retrieve
- Changeset 4：WorkMemoryManager scope

**Batch C（依赖 Batch A+B）**：
- Changeset 5：ContextResolveOptions/Request
- Changeset 6：ContextAssembler + authority
- Changeset 8：prompt_builder 优先级合同

**Batch D（依赖 Batch C）**：
- Changeset 9：context_service 贯穿

---

## 4. 测试计划

### 4.1 单元测试（每个 Changeset 必须有）

| Changeset | 测试文件 | 关键测试用例 |
|-----------|---------|-------------|
| CS1 | `tests/test_evomap_schema.py` | `test_atom_from_row_with_scope_project` |
| CS2 | `tests/test_evomap_retrieval.py` | `test_retrieve_with_scope_project_filter` |
| CS3 | `tests/test_memory_manager.py` | `test_stage_with_project_id`, `test_working_context_project_filter` |
| CS4 | `tests/test_work_memory_manager.py` | `test_scope_candidates_with_project_id` |
| CS5 | `tests/test_context_service.py` | `test_resolve_with_project_id` |
| CS6 | `tests/test_context_assembler.py` | `test_authority_never_trimmed`, `test_authority_priority_zero` |
| CS7 | `tests/test_signals.py` | `test_signal_from_trace_event_with_project_id` |
| CS8 | `tests/test_prompt_builder.py` | `test_authority_anchor_in_system_prompt` |
| CS9 | `tests/test_context_service.py` | `test_local_assembler_project_id_passthrough` |

### 4.2 集成测试

1. **端到端 project-scoped retrieval**：
   - 向 `/context/resolve` 发送 `project_id="planning"` 的请求
   - 验证返回的 EvoMap atoms 全部是 `scope_project="" or "planning"`
   - 验证 memory 结果按项目过滤

2. **authority 优先级合同**：
   - 构造 authority_content + 大量 EvoMap 结果
   - 设置极小 token budget
   - 验证 authority 内容完整保留，EvoMap 被裁剪

3. **向后兼容**：
   - 所有现有 API 调用（不带 project_id）行为不变
   - 现有测试全部通过

### 4.3 回归测试

```bash
./.venv/bin/pytest -q  # 全量回归
```

---

## 5. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Atom.scope_project 修复后 from_row() 行为变化 | 低：只是多读一个字段 | 默认值 ""，不影响已有逻辑 |
| MemoryManager DDL 变更导致已有 DB 问题 | 中：生产 DB 需要 migration | _upgrade_schema() 已有 ALTER TABLE 模式，复用 |
| authority 源占用过多 token budget | 低：authority_anchor 预算 800 tokens | 硬编码上限，超出截断 |
| 两条注入路径 authority 内容重复 | 中：同一 authority 出现两次 | 调用方负责只通过一条路径注入 authority |
| retrieve() project filter 误杀未标注 atom | 低：soft filter 设计 | scope_project="" 的 atom 对所有项目可见 |

---

## 6. 文件变更清单

| 文件 | Changeset | 变更类型 |
|------|-----------|---------|
| `chatgptrest/evomap/knowledge/schema.py` | CS1 | 添加 2 个字段 |
| `chatgptrest/evomap/knowledge/db.py` | CS1 | DDL + migration |
| `chatgptrest/evomap/knowledge/retrieval.py` | CS2, CS5 | 添加字段 + filter 逻辑 |
| `chatgptrest/kernel/memory_manager.py` | CS3 | DDL + migration + 6 处方法改动 |
| `chatgptrest/kernel/work_memory_manager.py` | CS4 | scope_candidates + 签名 |
| `chatgptrest/cognitive/context_service.py` | CS5, CS9 | Options + Resolver + LocalAssembler |
| `chatgptrest/api/routes_cognitive.py` | CS5 | Request model + handler |
| `chatgptrest/kernel/context_assembler.py` | CS6 | SOURCE_PRIORITY + build() + _apply_budget() |
| `chatgptrest/evomap/signals.py` | CS7 | Signal dataclass + from_trace_event |
| `chatgptrest/kernel/event_bus.py` | CS7 | TraceEvent + create() + query() |
| `chatgptrest/advisor/prompt_builder.py` | CS8 | authority 解析 + token 预算 |
| `chatgptrest/advisor/task_intake.py` | CS8 | available_inputs 结构化 |

总计：12 个文件，9 个 changeset。
