# Agent Role v3 蓝图 — 与两份 Codex Workstream 文档的交叉验证

> 日期：2026-03-10
> 对照文档：
> - `docs/dev_log/2026-03-10_codex_workstream_end_to_end_summary.md`（issue graph codex）
> - `/vol1/maint/exports/.../kb_codex_workstream_full_summary_2026-03-10.md`（kb codex）
> 蓝图文档：
> - `docs/reviews/2026-03-10_agent_role_architecture_blueprint_v3.md`
> - `docs/reviews/2026-03-10_agent_role_architecture_blueprint_v3_addendum.md`

---

## 一、发现的架构冲突（3 个）

### 冲突 1：kb_scope_tags 过滤层放错了位置

**蓝图做法**：在 `KBRetriever.search()` 加 FTS5 tags 过滤 → role 决定 KB 看到什么。

**kb_codex 的架构决定**（§5.2, §10.2）：

> "keep raw truth in source files / authoritative stores → define a canonical plane →
>  let KB handle evidence retrieval, graph handle relation, memory handle continuity,
>  EvoMap handle governed evolution, **router decide what the agent actually sees**"

**冲突分析**：kb_codex 明确把"决定 agent 看到什么"的权责放在 **router 层**，不是 retrieval 层。
我的蓝图把过滤放在 `KBRetriever.search()` → 这是在 retrieval 层做 router 的事。

**实际影响**：
- 如果以后 router 也做角色化限定 → retrieval 层和 router 层会双重过滤，语义冲突
- 如果只在 retrieval 层做 → 绕过了 kb_codex 建立的 authority-first 架构的 router 边界

**修正方案**：
- `kb_scope_tags` 应该是 **router hint**，不是 retrieval filter
- `KBRetriever.search()` 可以接受 tags 参数（技术已有基础），但默认行为不应改变
- 角色化 KB 限定的正确入口是 `ContextResolver`（已在 router 层），而不是 `KBHub.search()`

---

### 冲突 2：蓝图的 KB 对象是 903 个 FTS5 文档，但真正的知识大体量不在这里

**蓝图假设**：903 个 KB 文档 × tags 过滤 = role-based KB。

**kb_codex 的发现**（§10.2）：

> "traditional KBHub DBs were effectively sparse;
>  the real broad corpus had accumulated inside data/evomap_knowledge.db"

**实际验证**：

| 存储 | 大小 | 对象数量 | 角色 |
|------|------|---------|------|
| `kb_search.db` (FTS5) | ~小 | 903 docs, 0 tags | KBRetriever 检索面 |
| `.openmind/evomap_knowledge.db` | 13MB | 2727 atoms, 2700 evidence, 239 episodes | 运行时 EvoMap |
| `data/evomap_knowledge.db` | 755MB | (大体量主库) | 历史积累语料 |

**冲突分析**：我的蓝图只盯着 903 个 FTS5 文档做 tag 过滤。但 kb_codex 早就发现这个
FTS5 表面是 **sparse**。真正的知识大部分在 2727 atoms + 755MB 主库里。
对 903 FTS5 文档打 tag 做过滤，可能只覆盖了知识体量的一个子集。

**修正方案**：
- 角色化 KB 策略需要同时考虑 FTS5（`kb_search.db`）和 EvoMap atoms（`evomap_knowledge.db`）
- 第一阶段可以只在 FTS5 加 tags（903 docs），但必须明确这是 **表面，不是全量**
- 长期方案必须和 kb_codex 的 canonical plane 对齐

---

### 冲突 3：memory_namespace 的 agent_id 映射方向与 "memory recall/capture as first substrate slice" 有张力

**蓝图做法**：`role.memory_namespace` → 作为 `agent_id` 传入 `MemoryManager.get_episodic()`。

**kb_codex 的立场**（§10.3）：

> "`memory recall/capture` as the first real substrate slice"

**张力分析**：kb_codex 把 memory recall/capture 定义为 cognitive substrate 的
"第一个真正切片"，意味着 memory 的组织方式是 substrate 架构的核心。
我的蓝图把 `memory_namespace` 直接映射为 `agent_id`，用已有的 `json_extract(source, '$.agent')` 
做 SQL 过滤——这是一种 **便宜但浅层的接入**，没有真正介入 substrate 的组织层。

**实际影响**：
- 短期可以工作（addendum 已证明冷启动无害）
- 但这不是"substrate slice"级别的集成——它只是复用了一个 SQL 过滤条件
- 如果后续 substrate 层要做更深的角色隔离（比如角色间 memory 共享/继承），纯 SQL 过滤不够

**修正方案**：
- 第一阶段保持 addendum 的方案（`memory_namespace` → `agent_id`，冷启动积累），但
- **明确标注这是 "shallow binding" 而非 "substrate integration"**
- 第二阶段与 kb_codex 的 substrate slice work 对齐

---

## 二、发现的补充修正（3 个）

### 补充 1：kb_codex 的 "not everything should become graph retrieval" 原则

**来源**：kb_codex §8.3 research pilot 结论。

**对蓝图的影响**：蓝图的 `kb_scope_tags` 是一种"blanket tag filter"——所有 KB 检索
都按角色 tag 过滤。但 kb_codex 的 research pilot 明确显示：

> "some questions are still best answered by file baseline"
> "graph becomes clearly better only for cross-file relation questions"

这意味着角色化 KB 过滤不应该是无条件的。某些场景下（跨领域研究、通用知识检索）,
tag 限定反而会降低召回率。

**修正**：`kb_scope_tags` 应该是 **default hint (默认推荐)**，而非 hard filter。
`ContextResolver` 在组装上下文时可以选择性使用或忽略 tags。

---

### 补充 2：end_to_end 的 cold client acceptance 模式可复用于 role 验证

**来源**：end_to_end §5.2。

> "cold Codex client acceptance lane — 让'新起 Codex 不知道怎么用'这类问题能被集成测试发现"

**对蓝图的影响**：蓝图的 test plan 只有单元测试（`test_role_pack.py`）。
但 end_to_end 已经建立了 cold client 验收模式——新角色配置也应该走类似的验收：

```
cold role acceptance:
  1. 起一个新 session
  2. 激活 devops role
  3. 验证 memory 是否正确隔离
  4. 验证 KB 搜索结果是否受 tags 影响
  5. 验证跨 role 切换是否干净
```

---

### 补充 3：end_to_end 的 mitigated → closed 治理模式可复用于 role 问题管理

**来源**：end_to_end §5.3。

**对蓝图的影响**：蓝图没有定义角色化系统的问题管理。如果角色化引入后出现
memory 污染、KB 过滤误伤等问题，应该套用已有的
`mitigated = live 验证通过, closed = 3 次 qualifying success + 无复发` 模式。

---

## 三、无冲突的确认（2 个）

### 确认 1：cognitive substrate API 与 role pack 兼容

end_to_end §4.1 列出的 `/v2/context/resolve` 等 API 通过 `ContextResolver` 工作，
而蓝图的改动点也在 `ContextResolver`（改 `agent_id` fallback）。两者兼容，
不存在 API 路由冲突。

### 确认 2：EvoMap 后置与 kb_codex 的 import contract 对齐

蓝图把 EvoMap 角色化推到第二阶段。kb_codex 的结论是 EvoMap 当前处于
"import-only, review-only, candidate-only" 状态，明确拒绝 runtime activation。
两者完全一致——第一阶段不碰 EvoMap 是正确的。

---

## 四、修正后的蓝图变更清单

| 蓝图原有 | 修正 | 理由 |
|----------|------|------|
| `KBRetriever.search()` 加 tags hard filter | → `ContextResolver` 用 tags 做 **soft hint** | router 层决定，不在 retrieval 层做 |
| 903 FTS5 文档 = KB 全量 | → FTS5 是一个 **检索表面**，不是全量 | 755MB evomap_knowledge.db 才是大体量 |
| `kb_scope_tags` 无条件过滤 | → **default hint**，可选择性忽略 | "not everything should be filtered" |
| memory_namespace = substrate level | → 标注为 **shallow binding** | 与 substrate slice 区分 |
| 单元测试为唯一验证 | → 加 cold role acceptance 验收 | 复用已有 cold client 模式 |
| 未定义问题管理 | → 复用 mitigated→closed 模式 | 复用已有治理机制 |
