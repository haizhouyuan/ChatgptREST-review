# v3 蓝图独立验证 — 基于实际数据的修正

> 日期：2026-03-10 | 独立验证补充件
> 方法：直接查询 production DB (kb_search.db + memory.db)

---

## 1. 实际数据（而非推测）

### KB Tags 覆盖率

```
Total docs:    903
Docs with tags: 0 (0.0%)
```

**903 个文档没有一个打了 tag。** FTS5 `tags` 列存在，`index_text()` 支持写入 tags，
但 production 里全为空字符串。

**结论**：KB tag 过滤不是"15 行技术改动 + 补一些 tag"的问题。
这是 **903 文档的冷启动标注问题**。在此之前，任何依赖 `kb_scope_tags` 的角色化 KB
过滤都是空操作。

### Memory Agent 分布

```
openclaw      → 370 records
advisor       → 136 records
report_graph  →  36 records
main          →  12 records
deep_research →  10 records
test          →   3 records
cc_native     →   3 records
```

**570 条记录的 `source.agent` 全部是组件名**（`"advisor"`, `"openclaw"` 等），
不是角色名（`"devops"`, `"research"`）。

**结论**：`MemoryManager.get_episodic(agent_id="devops")` 今天返回 0 条。
但这 **不是 blocker**——不需要回溯改历史记录。新的角色化写入会自然积累：
`MemorySource(agent="devops", ...)` 写入后 → 下次 `get_episodic(agent_id="devops")`
就能拿到。冷启动期间，角色化 memory 是空的，但不会出错。

---

## 2. 对 v2 和主库 codex 反馈的独立判断

| 论点 | v2 蓝图 | 主库 codex | 我的独立判断 |
|------|---------|-----------|-------------|
| Memory "已就绪" | ✅ 就绪 | ❌ identity 没通 | **机制就绪，数据为空**。不需要修 identity，需要开始写入角色化记录。冷启动期 memory 为空但不报错。 |
| KB "~15 行" | 是 | 治理是真正工作量 | **0% tag 覆盖率 = 冷启动问题**。15 行加过滤是真的，但没有 903 文档的批量标注，过滤全返回空集。 |
| EvoMap 角色化 | 可做 | 讲早了 | **同意主库 codex**，当前 EvoMap 做观察层更合适 |
| coordinator | 要做 | 不做 | **同意主库 codex**，main 继续做 controller |
| 自动 role_hint | 要做 | 不做 | **同意主库 codex**，显式选角色 |
| identity 审计是前提 | 未提及 | 是顺序前提 | **不同意**。不是前提，是并行事项。角色化写入从 Day 1 就可以开始积累。 |
| KB tag 审计是前提 | 未提及 | 是顺序前提 | **部分同意**。批量标注 903 文档是前提，但可以用 LLM 辅助分类一次性完成（不需要完美 tag）。 |

---

## 3. 修正后的执行方案

### 阶段 1A：立即可做（不依赖数据治理）

```
1. RoleSpec 加 2 字段 (memory_namespace, kb_scope_tags)   ~5L
2. role_context.py (contextvars)                           ~20L  
3. role_loader.py + agent_roles.yaml                       ~70L
4. ContextService 用 role.memory_namespace 作 agent_id     ~3L
5. 新角色化写入自然带 role 标签                              ~0L (配置)
```

**效果**：从 Day 1 开始，devops 和 research 角色的新操作会写入角色化 memory。
Memory 隔离从空集开始积累。KB 过滤暂时不生效（因为没有 tag），
但不会出错——无 tag 过滤 = 返回全量，等同于现在。

### 阶段 1B：并行做（数据治理）

```
1. 批量标注 903 个 KB 文档                                  1 次性任务
   → 用 LLM 对每个文档推荐 tag（基于标题+前 500 字）
   → 人工审核 + 批量 UPDATE kb_fts SET tags = ?
   
2. KBRetriever.search() 加 tags 过滤                       ~20L
   → FTS5 MATCH 加 tags 列的 AND 条件
   → KBHub.search() 透传 tags
```

**这两件事可以并行**。不需要 1B 完成后 1A 才能启动。

### 阶段 2（第一阶段验证后）

```
- signal_domain → EvoMap
- policy_profile → PolicyEngine
- 路由层可以 suggest role（但不 auto-decide）
```

---

## 4. 和 v3 蓝图的差异

| 项目 | v3 蓝图 | 本修正 |
|------|---------|--------|
| Memory 前提 | 先修 identity gaps | **不需要修**。冷启动即可。 |
| KB 前提 | 先做 tag 审计 | **并行做**。1A 不等 1B。 |
| 执行顺序 | 顺序依赖 | **1A 立即开始 + 1B 并行** |
| 冷启动策略 | 未讨论 | **明确**：角色化 memory/KB 从空集开始积累 |
