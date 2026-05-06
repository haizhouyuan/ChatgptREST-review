# Codex 需求定义文档深度复核 — Claude Code 独立意见 v1

日期：2026-04-07
审核对象：`docs/reviews/2026-04-07_project_scoped_substrate_requirements_for_claude_v1.md`
审核方法：逐条对照源代码验证，批判性分析

---

## 总体评价

Codex 这版文档比前一版 adoption plan 有明显进步：

1. 从方向稿升级到了需求定义
2. 纳入了我之前指出的 4 个关键点
3. 分层模型和优先级合同定义清晰
4. 非目标边界画得好

但仍有 **7 个问题**需要在实施前解决，其中 2 个是阻断级。

---

## 问题 1（阻断级）：project 过滤存在两套语义，文档没有统一

### 事实

当前代码中存在两种 project 过滤机制：

**机制 A — graph_service.py `_filter_by_project()`**：
```python
# 通过 JOIN 链过滤：atoms → episodes → documents
SELECT a.atom_id FROM atoms a
JOIN episodes ep ON ep.episode_id = a.episode_id
JOIN documents d ON d.doc_id = ep.doc_id
WHERE a.atom_id IN (...)
  AND d.project = ?
```
这用的是 `documents.project`（7,893 docs，91 个 distinct project）。

**机制 B — 提议的 retrieval.py 过滤**：
直接用 `atoms.scope_project` 字段（26,120 行非空，占总量 25%）。

### 问题

这两套语义不一致：

- 一个 atom 可能 `scope_project=""` 但属于 `documents.project="planning"` 的文档
- graph_service 会把它算作 planning 项目的（通过 JOIN），但 retrieval.py 的 soft filter 会让它对所有项目可见
- 75% 的 atoms 没有 scope_project，它们在 retrieval 路径下对所有项目可见，但在 graph 路径下可以被正确过滤

### Codex 文档怎么说

FR-4 第 3 条写了："retrieval 没有 scope_project 时才回退到 document project / generic retrieval"。

但没有定义这个回退的实现方式。是在 retrieval.py 里加 JOIN 回退？还是在调用方做两轮查询？还是接受 75% atoms 对所有项目可见的现状？

### 我的判断

**必须在实施前明确选择一种策略**：

- **策略 A（推荐）**：retrieval.py 的 FTS5 查询改为 JOIN atoms → episodes → documents，当 `scope_project` 为空时回退到 `documents.project` 过滤。代价是 FTS5 查询变复杂，但语义统一。
- **策略 B**：接受 soft filter 现状，后续通过批量回填 `atoms.scope_project`（从 documents.project 继承）来收敛。代价是过渡期 75% atoms 无项目隔离。
- **策略 C**：先做一次性 migration 把 `documents.project` 回填到所有 atoms 的 `scope_project`，然后只用 scope_project 过滤。代价是一次性 migration 工作量。

我倾向 **策略 C**：一次性回填 + 后续 ingest 时自动继承。这样 retrieval.py 只需要简单的字段过滤，不需要 JOIN。

---

## 问题 2（阻断级）：_LocalOnlyContextAssembler.build() 签名已与父类分叉

### 事实

代码验证确认两个 build() 签名已经分叉：

**父类 ContextAssembler.build()**（context_assembler.py:165）：
```python
def build(self, query, session_id="", *, working_limit=10, episodic_limit=5, semantic_limit=3, kb_top_k=5)
```

**子类 _LocalOnlyContextAssembler.build()**（context_service.py:692）：
```python
def build(self, query, session_id="", account_id="", agent_id="", *, role_id="", thread_id="", working_limit=10, episodic_limit=5, semantic_limit=3, kb_top_k=5)
```

子类多了 `account_id`, `agent_id`, `role_id`, `thread_id` 四个参数。

此外，子类还有父类没有的源类型：
- `planning_pack`（lines 862-905）
- `captured` memory（独立于 working/episodic）

### 问题

Codex 文档的 FR-3 说"涉及 context_assembler.py 的 build(...)"，但没有区分父类和子类。如果只改父类的 build() 加 project_id，子类不会自动继承这个参数（因为子类 override 了 build()）。

更关键的是：**ContextResolver.resolve() 调用的是子类**，不是父类。所以 project_id 必须加到子类的 build() 上，而不仅仅是父类。

### 我的判断

实施时必须同时改两个 build()：
1. 父类 `ContextAssembler.build()` 加 `project_id: str = ""`
2. 子类 `_LocalOnlyContextAssembler.build()` 加 `project_id: str = ""`
3. `ContextResolver.resolve()` 传递 `options.project_id` 到子类 build()

这不是可选的，是必须的。Codex 文档需要在 FR-3 中明确这一点。

---

## 问题 3（重要）：authority anchor 注入路径比文档描述的更复杂

### 事实

我验证了 openmind-advisor/index.ts 的实际代码。authority anchor 的注入不是一条路径，而是三条：

**路径 1 — project_context 文本**：
```typescript
payload.available_inputs.project_context = args.projectContext.projectContextText;
```
`_project_context.md` 的 body 文本 → `available_inputs.project_context` → prompt_builder 的 `{available_inputs}` 模板变量。

**路径 2 — 结构化字段**：
```typescript
payload.available_inputs.frozen_facts = [...projectContext.frozenFacts];
payload.available_inputs.style_rules = [...projectContext.styleRules];
payload.available_inputs.current_focus = [...projectContext.currentFocus];
```
YAML frontmatter 解析出的结构化字段 → `available_inputs` 的独立 key。

**路径 3 — authority docs 文件路径**：
```typescript
payload.available_inputs.authority_docs = [...projectContext.authorityDocs];
// 同时作为 attachments
attachments: files,  // authority docs merged with other files
```
authority doc 文件路径 → 既在 available_inputs 中，又作为 attachments 传入。

### 问题

Codex 文档 §7.2 说"openmind-advisor 现在通过 task_intake.available_inputs.project_context 注入 authority anchor"。这只描述了路径 1，遗漏了路径 2 和路径 3。

更关键的是：authority docs 作为 attachments 传入后，advisor pipeline 会读取文件内容并注入 prompt。这意味着 authority 内容实际上可能出现在 prompt 的多个位置：
- `{available_inputs}` 区域（project_context 文本 + frozen_facts + style_rules）
- attachments 区域（authority doc 文件内容）

### 我的判断

优先级合同必须覆盖所有三条路径。具体来说：

1. prompt_builder 需要识别 `available_inputs` 中的 `frozen_facts`、`style_rules`、`current_focus` 并给予 authority 级别保护
2. attachments 中的 authority docs 需要在 prompt 中标记为 authority 来源
3. 这三条路径的内容不应该被 token 裁剪

Codex 文档需要把 §7.2 的注入点描述从"一条路径"扩展为"三条路径"。

---

## 问题 4（重要）：_derive_available_inputs() 修改方向可能错误

### 事实

`build_task_intake_spec()` 的 available_inputs 解析链是：
```python
available_inputs = task_input.get("available_inputs")      # ← 优先
if available_inputs is None:
    available_inputs = contract_input.get("available_inputs")
if available_inputs is None:
    available_inputs = parsed_message_contract.fields.get("available_inputs")
if available_inputs is None:
    available_inputs = _derive_available_inputs(...)        # ← 最后回退
```

当 OpenClaw plugin 提供了 `task_intake.available_inputs`（包含 project_context、frozen_facts 等）时，`_derive_available_inputs()` 根本不会被调用。

### 问题

如果实施方案是修改 `_derive_available_inputs()` 来处理 project_context，那这个修改在 OpenClaw 调用路径下永远不会生效。

### 我的判断

authority anchor 的优先级保护应该在 prompt_builder 层面做，而不是在 task_intake 层面做。因为无论 available_inputs 从哪条路径来，最终都要经过 prompt_builder。

具体做法：prompt_builder 在拼装 prompt 时，检查 `available_inputs` 是否包含 `frozen_facts`、`style_rules`、`authority_docs` 等 key，如果有，将它们提取出来放在 prompt 最前面，并标记为不可裁剪。

---

## 问题 5（中等）：ContextResolver 和 advisor pipeline 是两条独立路径

### 事实

当前系统有两条主要的上下文组装路径：

**路径 A — advisor pipeline**：
```
/v3/agent/turn → advisor → prompt_builder → LLM
```
这条路径使用 prompt_builder，authority anchor 通过 available_inputs 注入。不经过 ContextResolver。

**路径 B — context/resolve API**：
```
/v2/context/resolve → ContextResolver → _LocalOnlyContextAssembler → ContextPack
```
这条路径被 openmind-memory plugin 的 recall 使用。不经过 prompt_builder。

### 问题

Codex 文档把这两条路径混在一起讨论，没有明确区分。FR-3 说"涉及 context_assembler.py 的 build(...)"，但 advisor pipeline 根本不调用 ContextAssembler.build()。

### 我的判断

需要在文档中明确：
1. **advisor pipeline 路径**：project_id 通过 task_intake.context 传入，authority 通过 available_inputs 注入，优先级在 prompt_builder 层保证
2. **context/resolve 路径**：project_id 通过 ContextResolveRequest 传入，authority 需要作为新的 source type 注入 ContextAssembler，优先级在 _apply_budget() 层保证

两条路径的优先级合同实现方式不同，但最终效果必须一致。

---

## 问题 6（中等）：FR-2 遗漏了 get_semantic() 和 get_episodic() 的实际签名

### 事实

代码验证确认 `get_semantic()` 和 `get_episodic()` 的签名已经包含所有 5 个 identity 字段作为独立参数：

```python
def get_semantic(self, domain="", key="", agent_id="", session_id="", role_id="", account_id="", thread_id="")
def get_episodic(self, query="", category="", limit=10, agent_id="", session_id="", role_id="", account_id="", thread_id="")
```

### 问题

FR-2 说"get_episodic() 支持按 project_id 过滤"和"get_semantic() 支持按 project_id 过滤"，但没有说明这需要：
1. 给两个方法的签名都加 `project_id: str = ""` 参数
2. 在 WHERE 子句中加 `AND project_id = ?` 条件
3. 确保 `_upgrade_schema()` 的 back-fill 逻辑也覆盖 project_id

这不是大问题，但实施时容易遗漏。

---

## 问题 7（低）：Phase 5 promotion pipeline 恢复缺乏具体诊断

### 事实

103,874 atoms 中只有 202 个 active（0.19%）。promotion_audit 只有 505 条。

### 问题

Codex 文档 Phase 5 说"确认 staged 长期堆积根因"，但没有给出任何初步假设。根据我对代码的了解，可能的根因包括：

1. promotion 触发条件太严格（groundedness gate 通过率低）
2. promotion 没有被定期调度（缺少 cron/scheduler）
3. promotion 只在特定事件触发时运行，而这些事件很少发生

这不影响当前需求定义，但 Phase 5 的退出条件"active knowledge 占比显著提升"太模糊。建议至少定义一个数字目标（比如从 0.19% 提升到 5%）。

---

## 回答 Codex 文档 §13 的 8 个审核问题

### Q1：project_id 贯穿主链的定义是否完整

**不完整。** 遗漏了：
- _LocalOnlyContextAssembler.build() 与父类签名分叉问题（问题 2）
- advisor pipeline 和 context/resolve 是两条独立路径（问题 5）
- get_semantic() 和 get_episodic() 需要加 project_id 参数（问题 6）

### Q2：Atom.scope_project 修复是否应列为 Phase 1 前置阻断

**是的，而且还不够。** 除了 dataclass 修复，还需要解决 scope_project 与 documents.project 的语义统一问题（问题 1）。建议在 Phase 1 之前先做一次性 migration 回填。

### Q3：authority 优先级合同是否覆盖了所有注入点

**没有。** 遗漏了路径 2（frozen_facts/style_rules 结构化字段）和路径 3（authority docs 作为 attachments）。见问题 3。

### Q4：KB evidence 归入 runtime heuristics 的定位是否合理

**基本合理。** KB 当前没有 project scope，排在 EvoMap 之后是对的。但文档应该明确：KB evidence 是否需要在后续也加 project scope？如果不加，它在 project-scoped 场景下的价值会越来越低。

### Q5：Phase 1 与 Phase 2 并行的要求是否必要

**必要。** 我在之前的审核中已经指出：如果 Phase 1（project-scoped retrieval）先上线而 Phase 2（优先级合同）没有同步，EvoMap 返回的 project-scoped 结果可能覆盖 authority anchor 内容。这个风险是真实的。

### Q6：Phase 4 的通用 project memory schema 约束是否足够避免补丁系统

**方向对，但约束不够具体。** FR-7 说"不允许写成只适用于某一项目或某一业务域的固定字段组合"，但 WorkMemoryManager._QUERY_FIELDS 中的 `active_project` 已经有 `project_id`, `name`, `phase`, `status`, `blockers`, `next_steps` 等字段。这些字段是否算"通用"？需要一个更明确的判断标准。

建议：定义一个"通用性测试"——如果一个字段只在某一类项目中有意义（比如只有 planning 项目才有 `phase`），那它应该放在 `value` JSON 里而不是作为顶层字段。

### Q7：Phase 5 是否还缺更明确的 promotion 恢复动作

**缺。** 见问题 7。至少需要：
1. 初步诊断 promotion 停滞的根因
2. 定义一个数字目标（比如 active 占比从 0.19% 到 5%）
3. 明确是调整 gate 阈值、增加调度频率、还是两者都做

### Q8：这份需求定义是否已经足够细，能直接指导后续设计与实施

**还不够。** 用户明确要求"不要只给方向，我要实现全部细节"。这份文档仍然是需求级别（FR-1 到 FR-8），不是实现级别。缺少：
- 精确的字段添加位置（哪个 dataclass 的哪一行）
- 精确的 SQL DDL 变更
- 精确的函数签名变更
- 精确的 migration 代码
- 精确的过滤逻辑

我之前提交的 `docs/reviews/2026-04-07_project_scope_threading_requirements_definition_v1.md` 是实现级别的，可以作为补充。两份文档应该配合使用：Codex 的定义"做什么"，我的定义"怎么做"。

---

## 综合判断

Codex 这份文档作为需求基线是合格的，方向判断全部正确。但在以下方面需要补充后才能进入实施：

1. **必须解决**：scope_project vs documents.project 语义统一策略（问题 1）
2. **必须解决**：_LocalOnlyContextAssembler 签名分叉的处理方案（问题 2）
3. **应该补充**：authority 三条注入路径的完整描述（问题 3）
4. **应该补充**：advisor pipeline vs context/resolve 两条路径的区分（问题 5）
5. **建议补充**：实现级细节（与我的文档合并）

建议下一步：把这份审核意见和我之前的实现级需求定义合并成一份最终的实施规格书，然后开始 Batch A 实施。
