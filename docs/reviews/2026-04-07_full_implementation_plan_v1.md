# ChatgptREST 全线实施计划 v1

日期：2026-04-07
作者：Claude Code（独立分析）
用途：交给 Codex 执行的完整实施规格书

---

## 总览

本计划覆盖 6 条主线工作流，按依赖关系排序。每条主线包含精确的改动范围、实现路径和验收目标。

```
主线 A: Public Agent MCP 契约修复（立即）
    ↓
主线 B: scope_project 语义统一 + Atom dataclass 修复（前置）
    ↓
主线 C: project_id 贯穿主链（核心）
    ↓
主线 D: Authority 优先级合同落地（与 C 并行）
    ↓
主线 E: OpenClaw / OpenMind 插件层完善（依赖 C+D）
    ↓
主线 F: Promotion Pipeline 恢复 + Harness（最后）
```

---

## 主线 A：Public Agent MCP 契约修复

### 目标
让 Codex / Claude Code / Antigravity 在 Deep Research 场景下能正确判断答案完成状态并获取完整答案。

### 前置条件
无。可立即开始。

### 第一批 PR（一个完整闭环）

#### 改动 A1：`_job_snapshot()` 补 completion_contract 字段

文件：`chatgptrest/api/routes_agent_v3.py`（约 line 2865）

新增 import：
```python
from chatgptrest.core.completion_contract import (
    get_completion_answer_state,
    get_authoritative_answer_path,
    get_authoritative_job_id,
    get_answer_provenance,
    is_research_final,
)
```

在 `_job_snapshot()` 返回值中追加：
```python
snapshot["answer_state"] = get_completion_answer_state(job_dict)
snapshot["authoritative_job_id"] = get_authoritative_job_id(job_dict)
snapshot["authoritative_answer_path"] = get_authoritative_answer_path(job_dict)
snapshot["answer_provenance"] = get_answer_provenance(job_dict)
snapshot["research_final"] = is_research_final(job_dict)
```

验收：`_job_snapshot()` 返回值包含 `answer_state` 字段。

#### 改动 A2：`_controller_snapshot()` 合并 contract 字段

文件：`chatgptrest/api/routes_agent_v3.py`（约 line 3137）

当 controller snapshot 包含 child job snapshot 时，把 A1 追加的字段提升到 controller 级别：
```python
if child_snapshot.get("answer_state"):
    result["answer_state"] = child_snapshot["answer_state"]
    result["authoritative_job_id"] = child_snapshot.get("authoritative_job_id")
    result["authoritative_answer_path"] = child_snapshot.get("authoritative_answer_path")
    result["answer_provenance"] = child_snapshot.get("answer_provenance")
    result["research_final"] = child_snapshot.get("research_final", False)
```

验收：controller snapshot 包含从 child job 提升的 contract 字段。

#### 改动 A3：`_build_delivery_surface()` 修正 `answer_ready`

文件：`chatgptrest/api/routes_agent_v3.py`（约 line 698）

当前逻辑：
```python
"answer_ready": bool(answer and answer.strip()),
```

改为：
```python
# 如果有 answer_state，用它判断；否则回退到旧逻辑保持兼容
if answer_state:
    "answer_ready": answer_state == "final",
else:
    "answer_ready": bool(answer and answer.strip()),
```

需要让 `_build_delivery_surface()` 接收 `answer_state` 参数（或从 existing dict 中读取）。

验收：
- Deep Research provisional 场景：`answer_ready=false`
- Deep Research final 场景：`answer_ready=true`
- 普通短回答：`answer_ready=true`（兼容旧行为）

#### 改动 A4：`_session_response()` 投射 contract 字段

文件：`chatgptrest/api/routes_agent_v3.py`

`_session_response()` 已经调用 `_controller_snapshot()`，所以 A2 的字段会自动出现在 session response 中。需要确认这些字段在 `_finalize_public_agent_surface()` 中不被过滤掉。

如果 `_finalize_public_agent_surface()` 有白名单机制，需要把以下字段加入白名单：
- `answer_state`
- `authoritative_job_id`
- `authoritative_answer_path`
- `answer_provenance`
- `research_final`

验收：`advisor_agent_status` 和 `advisor_agent_wait` 返回值包含 `answer_state` 字段。

### 第二批 PR

#### 改动 A5：新增 `advisor_agent_answer` 工具

文件：`chatgptrest/mcp/agent_mcp.py`

```python
async def advisor_agent_answer(
    ctx: Context | None,
    session_id: str,
    offset: int = 0,
    max_chars: int = 80000,
) -> dict[str, Any]:
    """Fetch the canonical answer for a completed session."""
```

逻辑：
1. 查询 session，获取 `authoritative_job_id` 和 `authoritative_answer_path`
2. 如果有 `authoritative_answer_path`：从文件读取完整答案，支持 offset/max_chars 分页
3. 如果没有 `authoritative_answer_path` 但有 `last_answer`：返回 last_answer
4. 如果都没有：返回 `{"ok": false, "error": "no_answer_available"}`

返回值：
```python
{
    "ok": True,
    "session_id": "...",
    "answer_state": "final",
    "answer": "完整答案文本...",
    "answer_chars": 12345,
    "offset": 0,
    "has_more": False,
    "source": "authoritative_answer_path" | "last_answer",
}
```

验收：
- Deep Research 完成后调用，返回完整答案
- no-job session 调用，返回 last_answer
- 空 session 调用，返回 error 不抛异常

#### 改动 A6：wrapper 脚本改用 answer_state

文件：`skills-src/chatgptrest-call/scripts/chatgptrest_call.py`

agent mode 的 wait 后逻辑改为：
```python
# wait 返回后
answer_state = result.get("answer_state", "")
if answer_state == "final" and result.get("authoritative_answer_path"):
    # 自动补一次 answer fetch
    answer_result = _run_mcp_tool("advisor_agent_answer", {
        "session_id": session_id,
        "max_chars": 80000,
    })
    result["canonical_answer"] = answer_result.get("answer", "")
elif not answer_state:
    # 旧行为兼容：没有 answer_state 时用 last_answer
    pass
```

验收：
- Deep Research 场景：wrapper 自动获取完整答案
- 普通短回答：行为不变

### 第三批 PR（稳态修复）

#### 改动 A7：controller/engine.py 改用 completion_contract

文件：`chatgptrest/controller/engine.py`（约 line 1768）

`_reconcile_job_work_item()` 改为：
```python
from chatgptrest.core.completion_contract import (
    completion_contract_from_job_like,
    is_research_final,
)

contract = completion_contract_from_job_like(job_dict)
answer_state = contract.get("answer_state", "")

if answer_state == "final":
    # 真正完成，创建 COMPLETED StepResult
elif answer_state == "provisional":
    # Deep Research 还没最终确认，创建 WAITING_EXTERNAL StepResult
elif job.status.value == "completed":
    # 回退兼容：没有 contract 信息时用旧逻辑
```

验收：Deep Research 场景下 controller 不会把 provisional 答案当成 final 交付。

### 主线 A 整体验收矩阵

| 场景 | 预期行为 |
|------|---------|
| Deep Research completed + final artifact | wait 返回 answer_state=final, answer_ready=true; advisor_agent_answer 返回完整正文 |
| Deep Research completed + provisional | wait 返回 answer_state=provisional, answer_ready=false |
| no-job session（纯 advisor 响应） | advisor_agent_answer 返回 last_answer, 不报错 |
| 普通短回答 | 兼容现有行为, answer_ready=true |

---

## 主线 B：scope_project 语义统一 + Atom Dataclass 修复

### 目标
解决 `atoms.scope_project` 与 `documents.project` 的语义不一致问题，为主线 C 的 project_id 贯穿扫清障碍。

### 前置条件
无。可与主线 A 并行开始。

### 阻断级问题：两套 project 过滤语义

当前代码中存在两种 project 过滤机制：

- **机制 A**：`graph_service._filter_by_project()` 通过 JOIN 链 `atoms → episodes → documents` 过滤，用 `documents.project`
- **机制 B**：提议的 `retrieval.py` 过滤直接用 `atoms.scope_project`

75% 的 atoms 没有 `scope_project`。如果用机制 B，这些 atoms 对所有项目可见。

### 推荐策略：一次性回填 + 后续自动继承（策略 C）

#### 改动 B1：一次性 migration 回填 scope_project

写一个 migration 脚本，把 `documents.project` 回填到所有 atoms 的 `scope_project`：

```sql
UPDATE atoms SET scope_project = (
    SELECT d.project FROM documents d
    JOIN episodes ep ON ep.doc_id = d.doc_id
    WHERE ep.episode_id = atoms.episode_id
)
WHERE scope_project IS NULL OR scope_project = '';
```

验收：
- 回填前：26,120 atoms 有 scope_project（25%）
- 回填后：绝大多数 atoms 有 scope_project（目标 >90%）
- 回填不改变已有的 scope_project 值

#### 改动 B2：Atom dataclass 补 scope_project 字段

文件：`chatgptrest/evomap/knowledge/schema.py`（约 line 164-209）

在 Atom dataclass 中追加：
```python
scope_project: str = ""
scope_component: str = ""
```

验收：
- `Atom.from_row()` 不再静默丢弃 `scope_project` 列
- 新创建的 Atom 对象有 `scope_project` 属性

#### 改动 B3：db.py DDL 补 scope_project 列

文件：`chatgptrest/evomap/knowledge/db.py`

在 atoms CREATE TABLE DDL 中追加 `scope_project TEXT DEFAULT ''`。
在 `_upgrade_schema()` 中追加 ALTER TABLE migration（如果列不存在则添加）。

验收：新建数据库时 atoms 表包含 scope_project 列。

#### 改动 B4：ingest 时自动继承 documents.project

文件：`chatgptrest/evomap/knowledge/` 相关 ingest 代码

新 atom 写入时，如果 `scope_project` 为空，自动从关联的 `documents.project` 继承。

验收：新 ingest 的 atoms 自动获得 scope_project。

### 主线 B 验收矩阵

| 检查项 | 预期 |
|--------|------|
| atoms.scope_project 非空占比 | >90%（回填后） |
| Atom.from_row() 保留 scope_project | 是 |
| 新 ingest 自动继承 project | 是 |
| 已有 scope_project 值不被覆盖 | 是 |

---

## 主线 C：project_id 贯穿主链

### 目标
让 project_id 成为 memory、context resolve、retrieval、signal 的一等维度。

### 前置条件
主线 B 完成（Atom dataclass 修复 + scope_project 回填）。

### 改动分 4 批，按依赖关系排序

#### Batch A（可并行）

**改动 C1：MemoryManager 增加 project_id**

文件：`chatgptrest/kernel/memory_manager.py`

1. DDL 追加 `project_id TEXT DEFAULT ''`（约 line 94-139）
2. `_IDENTITY_FIELDS` 追加 `"project_id"`（line 210）
3. `_upgrade_schema()` 追加 ALTER TABLE + back-fill（line 237-292）
4. `get_semantic()` 签名追加 `project_id: str = ""`，WHERE 子句追加 `AND project_id = ?`
5. `get_episodic()` 签名追加 `project_id: str = ""`，WHERE 子句追加 `AND project_id = ?`
6. dedup index 追加 project_id

验收：
- `get_episodic(project_id="planning")` 只返回 planning 项目的记忆
- `get_semantic(project_id="planning")` 只返回 planning 项目的语义记忆
- 写入时 project_id 被持久化

**改动 C2：Signal / TraceEvent 增加 project_id**

文件：
- `chatgptrest/evomap/signals.py`：Signal dataclass 追加 `project_id: str = ""`
- `chatgptrest/kernel/event_bus.py`：TraceEvent dataclass 追加 `project_id: str = ""`
- `from_trace_event()` 传递 project_id

验收：同一项目的事件可按 project_id 聚合。

#### Batch B（依赖 Batch A + 主线 B）

**改动 C3：retrieval.py 增加 project 过滤**

文件：`chatgptrest/evomap/knowledge/retrieval.py`

1. `RetrievalConfig` 追加 `scope_project: str = ""`（line 74-107）
2. `retrieve()` 的 Step 2 pre-filter 追加 project 过滤（line 306-315）：
   ```python
   if cfg.scope_project and atom.scope_project and atom.scope_project != cfg.scope_project:
       continue
   ```
3. `runtime_retrieval_config()` 支持通过 `**overrides` 传入 `scope_project`

验收：
- `retrieve(config=RetrievalConfig(scope_project="planning"))` 只返回 planning 项目的 atoms
- scope_project 为空的 atoms 在有 project 过滤时仍然可见（soft filter，不排除无标签 atoms）

**改动 C4：WorkMemoryManager 增加 project_id 过滤**

文件：`chatgptrest/kernel/work_memory_manager.py`

1. `_scope_candidates()` 追加 project_id 过滤（line 440-497）
2. `build_active_context()` 签名追加 `project_id: str = ""`

当前 project_id 只影响 scoring（+4.0），不影响 recall scope。改为：当 project_id 非空时，`_scope_candidates()` 优先返回匹配 project_id 的 candidates。

验收：`build_active_context(project_id="planning")` 优先返回 planning 项目的 active context。

#### Batch C（依赖 Batch A+B）

**改动 C5：ContextResolveOptions / ContextResolveRequest 增加 project_id**

文件：
- `chatgptrest/cognitive/context_service.py`：`ContextResolveOptions` 追加 `project_id: str = ""`（line 54-71）
- `chatgptrest/api/routes_cognitive.py`：`ContextResolveRequest` 追加 `project_id: str = ""`

验收：`/v2/context/resolve` 接口可传 `project_id`。

**改动 C6：ContextAssembler.build() 增加 project_id**

文件：
- `chatgptrest/kernel/context_assembler.py`：父类 `build()` 签名追加 `project_id: str = ""`（line 165）
- `chatgptrest/cognitive/context_service.py`：子类 `_LocalOnlyContextAssembler.build()` 签名追加 `project_id: str = ""`（line 692）

**关键注意**：父类和子类签名已经分叉。子类多了 `account_id`, `agent_id`, `role_id`, `thread_id`。必须同时改两个 build()。

子类 build() 中的 EvoMap retrieval 调用（line 935-941）改为传入 project_id：
```python
config = runtime_retrieval_config(
    surface=RetrievalSurface.USER_HOT_PATH,
    scope_project=project_id,
)
```

验收：
- `/v2/context/resolve?project_id=planning` 返回 project-scoped 结果
- 同一 query 在不同 project_id 下结果不同

**改动 C7：ContextResolver.resolve() 传递 project_id**

文件：`chatgptrest/cognitive/context_service.py`（约 line 157-168）

`ContextResolver.resolve()` 从 `options.project_id` 传递到子类 `build()`。

验收：端到端 project-scoped context resolve 工作。

#### Batch D（依赖 Batch C）

**改动 C8：context_service 的 planning_pack 传递 project_id**

文件：`chatgptrest/cognitive/context_service.py`（约 line 862-905）

planning_pack 搜索时传入 project_id，让 planning runtime pack 也能按项目过滤。

验收：planning_pack 结果按 project 收窄。

### 主线 C 验收矩阵

| 检查项 | 预期 |
|--------|------|
| `/v2/context/resolve` 可传 project_id | 是 |
| 同 query 不同 project_id 结果不同 | 是 |
| MemoryManager 按 project_id 过滤 | 是 |
| EvoMap retrieval 按 scope_project 过滤 | 是 |
| Signal/TraceEvent 携带 project_id | 是 |
| WorkMemoryManager 按 project_id 优先 | 是 |

---

## 主线 D：Authority 优先级合同落地

### 目标
保证 authority anchor 内容在任何情况下都优先于自动 recall / 自动知识。

### 前置条件
可与主线 C 并行。

### 改动

#### 改动 D1：ContextAssembler 增加 authority 源类型

文件：`chatgptrest/kernel/context_assembler.py`

1. `SOURCE_PRIORITY` 追加 `"authority": 0`（最高优先级，line 143-151）
2. `TokenBudget` 追加 `authority_min: int = 2000`（authority 最低保证 token 数）
3. `_apply_budget()` 修改：authority 源不参与 greedy 裁剪，先分配 authority_min，剩余 budget 再分给其他源

验收：
- authority 源永远排在其他源之前
- token 裁剪不先裁 authority 内容

#### 改动 D2：prompt_builder 识别 authority 内容

文件：`chatgptrest/advisor/prompt_builder.py`

当 `available_inputs` 包含 `frozen_facts`、`style_rules`、`authority_docs` 时：
1. 提取这些内容放在 prompt 最前面
2. 标记为 `[AUTHORITY — 不可被后续内容覆盖]`
3. 这些内容不参与 token 裁剪

**三条注入路径都要覆盖**：
- 路径 1：`available_inputs.project_context`（body 文本）
- 路径 2：`available_inputs.frozen_facts` / `style_rules` / `current_focus`（结构化字段）
- 路径 3：`available_inputs.authority_docs`（文件路径，作为 attachments）

验收：
- prompt 中 authority section 先于 runtime recall
- token 裁剪不先裁 authority anchor

#### 改动 D3：优先级顺序写入代码

最终优先级顺序（从高到低）：
1. Authority anchor（frozen_facts, style_rules, pinned_authority_docs）
2. Project memory（work memory objects）
3. EvoMap knowledge（project-scoped atoms）
4. KB evidence（当前不 project-scoped）
5. Runtime heuristics / generic recall

这个顺序必须在 `ContextAssembler.SOURCE_PRIORITY` 和 `prompt_builder` 两个地方同时成立。

验收：
- ContextAssembler 输出的 source breakdown 显示 authority 排第一
- prompt_builder 最终 prompt 中 authority 在最前面

### 主线 D 验收矩阵

| 检查项 | 预期 |
|--------|------|
| authority 源优先级最高 | 是 |
| token 裁剪不先裁 authority | 是 |
| prompt 中 authority 在 runtime recall 之前 | 是 |
| 三条注入路径都被覆盖 | 是 |

---

## 主线 E：OpenClaw / OpenMind 插件层完善

### 目标
让 OpenClaw 在命中已知项目时稳定携带 project_id，并让插件层的 project 信息贯穿到后端。

### 前置条件
主线 C + D 完成。

### 改动

#### 改动 E1：补齐缺失的 project context 文件

当前状态：
- ✅ `/vol1/1000/projects/planning/两轮车车身业务/_project_context.md` — 存在
- ❌ `/vol1/1000/projects/planning/行星滚柱丝杠/_project_context.md` — 缺失

需要为"行星滚柱丝杠"项目创建 `_project_context.md`，包含：
- YAML frontmatter：project, alias, planning_base, updated
- frozen_facts（需要用户提供）
- current_focus（需要用户提供）
- style_rules（可复用通用规则）
- authority_docs（需要用户指定）

验收：`loadProjectContext("prs")` 成功加载，不再 console warning。

#### 改动 E2：openmind-memory 插件启用 projectId

文件：`openclaw_extensions/openmind-memory/index.ts`

当前 `projectId` 在 config 中声明但未使用。改为：
1. recall 调用时传入 `project_id` 参数
2. capture 调用时传入 `project_id` 参数
3. project_id 来源：从 advisor 的 `projectRef` 映射

验收：memory recall/capture 请求携带 project_id。

#### 改动 E3：openmind-telemetry 插件增加 project_id

文件：`openclaw_extensions/openmind-telemetry/index.ts`

telemetry 事件追加 `project_id` 字段。来源：从 session context 中的 `projectRef` 映射。

验收：telemetry 事件可按 project_id 聚合。

#### 改动 E4：openmind-advisor 的 task_intake 追加 project_id

文件：`openclaw_extensions/openmind-advisor/index.ts`

`buildTaskIntakePayload()` 中追加：
```typescript
payload.context = {
    ...payload.context,
    project_id: projectContext?.registryKey || "",
};
```

验收：advisor 转单时 task_intake.context.project_id 非空。

### 主线 E 验收矩阵

| 检查项 | 预期 |
|--------|------|
| 所有已注册项目有 _project_context.md | 是 |
| memory recall/capture 携带 project_id | 是 |
| telemetry 事件携带 project_id | 是 |
| advisor task_intake 携带 project_id | 是 |

---

## 主线 F：Promotion Pipeline 恢复 + Harness

### 目标
把 active atom 占比从 0.19% 提升到至少 5%，并为 Harness 提供 project-scoped replay 能力。

### 前置条件
主线 B + C 完成。

### 改动

#### 改动 F1：诊断 promotion 停滞根因

需要调查：
1. `promotion_engine.py` 的 groundedness gate 通过率（当前阈值 0.7）
2. promotion 是否有定期调度（cron/scheduler）
3. promotion 触发事件的频率

初步假设（需要数据验证）：
- 假设 1：groundedness gate 阈值 0.7 太严格
- 假设 2：promotion 没有定期调度，只在特定事件触发
- 假设 3：触发事件太少

#### 改动 F2：根据诊断结果调整

可能的调整：
- 降低 groundedness gate 阈值（从 0.7 到 0.5）
- 增加定期 promotion 调度（每日 cron）
- 增加 promotion 触发点

数字目标：active atom 占比从 0.19% 提升到 5%。

#### 改动 F3：Harness 最小字段

确保运行时至少能回答：
1. 这次 authority anchor 注入了什么
2. 这次 project memory 注入了什么
3. 这次 EvoMap knowledge 注入了什么
4. 哪一层最终影响了 prompt

需要的字段：
- `project_id`
- context source breakdown（每个源的 token 数和内容摘要）
- authority hit evidence（authority 内容是否被使用）
- retrieval source counts（每个源返回了多少条）

验收：同一任务 replay 时可以对比 project-scoped context 是否命中。

### 主线 F 验收矩阵

| 检查项 | 预期 |
|--------|------|
| promotion 停滞根因已诊断 | 是 |
| active atom 占比 ≥5% | 是 |
| context source breakdown 可审计 | 是 |
| authority hit evidence 可查 | 是 |

---

## 全局排期建议

```
Week 1:
  主线 A 第一批（contract 投射）— 立即
  主线 B（scope_project 回填 + Atom 修复）— 并行

Week 2:
  主线 A 第二批（advisor_agent_answer + wrapper）
  主线 A 第三批（controller 稳态修复）
  主线 C Batch A（MemoryManager + Signal）

Week 3:
  主线 C Batch B（retrieval + WorkMemoryManager）
  主线 D（authority 优先级合同）— 与 C 并行

Week 4:
  主线 C Batch C+D（ContextAssembler + ContextResolver）
  主线 E（OpenClaw 插件层）

Week 5+:
  主线 F（Promotion + Harness）
```

---

## 风险登记

| 风险 | 影响 | 缓解 |
|------|------|------|
| answer_ready 改动破坏旧客户端 | 中 | 有 answer_state 时用新逻辑，否则回退旧逻辑 |
| scope_project 回填 SQL 性能 | 低 | 103K atoms，一次性操作，可离线执行 |
| _LocalOnlyContextAssembler 签名分叉 | 高 | 必须同时改父类和子类 build() |
| authority token budget 挤占其他源 | 中 | authority_min 设为 2000 tokens，不超过总 budget 25% |
| OpenClaw 项目识别误触发 | 中 | 保留规则优先、模型补充的策略 |
| promotion gate 降低后质量下降 | 中 | 先小批量测试，观察 active atoms 质量 |

---

## 给 Codex 的执行指引

1. 按主线 A → B → C → D → E → F 的顺序执行
2. 主线 A 和 B 可以并行
3. 主线 C 和 D 可以并行
4. 每个主线完成后提交 PR，由 Claude GAC 做红队审核
5. 每个 PR 必须包含对应的验收场景测试
6. 改动 routes_agent_v3.py 时注意文件很大（6388 行），精确定位改动点
7. 改动 context_service.py 时注意父类/子类签名分叉问题
8. 回填 migration 脚本建议先在测试库上跑一遍确认
