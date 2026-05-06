# Agent 角色架构蓝图 v4 — 综合收敛版

> 日期：2026-03-10
> 输入：v3 蓝图 + v3 addendum(生产数据验证) + 交叉验证(kb_codex/issue_codex) + 主库 codex 评审 + GitNexus 影响分析
> 方法：独立调查 + gitnexus impact/context + 生产库直查

---

## 0. v3 → v4 变更摘要

| 项目 | v3 做法 | 问题 | v4 修正 |
|------|---------|------|---------|
| Memory identity | 先修 identity gaps 再开始 | 过度前置，阻断了 1A | **并行推进**，不阻断 |
| `source.agent` | 复用承载 role | 丢失组件归因维度 | **新增 `source.role`**，`source.agent` 保持组件语义 |
| KB tag 过滤 | 加在 `KBRetriever.search()` | 放在 retrieval 层做了 router 的事 | 过滤入口在 **ContextResolver**（router 层），KB 提供能力但不默认开启 |
| KB 903 文档 = 全量 | 隐含假设 | 755MB evomap_knowledge.db 才是大体量 | 明确 FTS5 是**检索表面** |
| kb_scope_tags | hard filter | 无条件限定降低召回率 | **soft hint**（默认推荐，非强制过滤） |
| KB 批量标注 | "一次性 LLM 标注" | 缺粗可持续性 | 受控词表 + 可重复脚本 + write-path 校验 |
| 验证策略 | 单元测试 | 不够覆盖面 | 加 **cold role acceptance** 验收 |

---

## 1. 核心设计决定

### 1.1 component identity ≠ role identity（最重要的修正）

**现状**（生产数据 2026-03-10）：

```json
// memory_records 中的 source JSON
{"type": "system", "agent": "advisor", "task_id": "deb6..."}
{"type": "system", "agent": "openclaw", "task_id": "..."}
{"type": "system", "agent": "deep_research", "task_id": "..."}
```

`source.agent` = **谁写的**（组件身份）。不是**以什么角色写的**（业务角色）。

**v4 设计**：

```python
@dataclass
class MemorySource:
    type: str = "system"
    agent: str = "aios"     # 组件身份：advisor | openclaw | report_graph（不变）
    role: str = ""           # 业务角色：devops | research（新增，默认空）
    session_id: str = ""
    task_id: str = ""
```

- `source.agent` 继续表示写入组件 → 保留归因
- `source.role` 表示当时活跃的业务角色 → 角色隔离
- 历史 572 条记录 `role` = NULL → 不回改，自然向前兼容
- 新写入通过 `contextvars` 自动注入当前 role

**GitNexus 影响分析**（`MemorySource` upstream, minConfidence≥0.8）：

```
risk: CRITICAL（8 impacted symbols, 16 processes, 3 modules）
但：新增可选字段 = 纯增量变更，d=1 调用方不会 break

d=1 (需review，不会break):
  - add_conversation_turn (memory_manager.py:500)
  - _mirror_feedback_memory (telemetry_service.py:96)
  - _capture_one (memory_capture_service.py:83)

d=2:
  - telemetry_service.ingest (telemetry_service.py:42)
  - memory_capture_service.capture (memory_capture_service.py:79)

d=3 (API endpoints):
  - knowledge_ingest (routes_cognitive.py:276)
  - memory_capture (routes_cognitive.py:318)
  - telemetry_ingest (routes_cognitive.py:344)
```

**查询路径**（GitNexus `get_episodic` context）：

```
get_episodic ← context_service.py:build (L332)   ← role 注入点
             ← context_assembler.py:build (L161) ← kernel 层备选注入点
             ← 7 个 substrate contract tests     ← 已有 agent 隔离测试
```

### 1.2 KB 过滤在 router 层，不在 retrieval 层

**kb_codex 的架构原则**：

> "router decide what the agent actually sees"

**v4 设计**：

```
KBRetriever.search(tags=...)   ← 技术能力存在（FTS5 有 tags 列）
                                  但不在这里做角色化决定

ContextResolver.build()        ← role 的 kb_scope_tags 在这里作为 hint 传入
                                  可选择使用或忽略

角色化 KB 限定 = router 层决定，retrieval 层只提供能力
```

### 1.3 FTS5 (903 docs) 是检索表面，不是知识全量

```
kb_search.db (FTS5):           903 docs, 0 tags
.openmind/evomap_knowledge.db:  2727 atoms, 2700 evidence, 239 episodes
data/evomap_knowledge.db:       755MB（主体量历史语料）
```

角色化 KB tag 过滤只影响 FTS5 表面。长期方案需要和 kb_codex 的 canonical plane 对齐。

---

## 2. 执行方案（三条线并行）

### 阶段 1A：立刻做（代码变更，~120L）

```
├── kernel/team_types.py         RoleSpec +2 字段                    ~5L
├── kernel/memory_manager.py     MemorySource +role 字段              ~2L
│                                get_episodic/get_semantic 加
│                                json_extract(source,'$.role') 过滤   ~10L
├── kernel/role_context.py       contextvars 绑定 (新文件)            ~25L
├── kernel/role_loader.py        YAML 加载器 (新文件)                 ~40L
├── config/agent_roles.yaml      两个角色定义 (新文件)                 ~30L
├── cognitive/context_service.py role fallback：
│                                get_current_role().memory_namespace
│                                → 作为 role_id（非 agent_id）         ~5L
└── cognitive/memory_capture_service.py
                                 _capture_one: 自动注入 source.role   ~3L
```

**关键区别**：

- `ContextService.build()` 查询 memory 时用 `role_id` 参数（新的），不覆盖 `agent_id`
- `_capture_one` 写入时自动从 `contextvars` 读当前 role，写入 `source.role`
- `source.agent` 继续由各组件自己设置，不变

### 阶段 1B：并行做（identity 治理）

```
├── 审计 identity 缺失率
│     → 跑 ContextResolver live 请求中 identity_gaps 频率
├── 修高频缺失路径
│     → 确保 Advisor 入口和 MCP 入口两条路径正确传 agent_id/session_id
└── 这不阻塞 1A（但会让 memory 查询更可靠）
```

### 阶段 1C：先做 KB 治理，再开过滤

```
Step 1: 定义受控词表
         → 对齐 agent_roles.yaml 中的 kb_scope_tags
         → 词表：chatgptrest, ops, infra, driver, mcp, runbook,
                  research, finagent, education, analysis, market

Step 2: 可重复 backfill 脚本
         → scripts/backfill_kb_tags.py
         → 基于标题+前500字推荐 tag，人工审核
         → 可重跑（幂等）

Step 3: 903 文档批量补打 tag

Step 4: write-path 校验
         → KBHub.index_text() 加 tag 检查
         → 新文档必须有 tag

Step 5: 启用 role-based KB hint（在 ContextResolver 层）
         → 在 Step 3 完成后
         → 默认 fail-open（无 tag 不限定）
```

**1C 完成前的行为**：
- role config 可以有 `kb_scope_tags`，runtime 忽略它
- 等于 role memory 先跑起来，KB 角色化后到

---

## 3. RoleSpec 扩展

```python
# kernel/team_types.py — v4 字段
@dataclass
class RoleSpec:
    # ── 已有字段 (不变) ──
    name: str
    description: str = ""
    prompt: str = ""
    tools: list[str] = field(default_factory=list)
    model: str = "sonnet"

    # ── 第一阶段 ──
    memory_namespace: str = ""          # → source.role for MemoryManager
    kb_scope_tags: list[str] = field(default_factory=list)  # → ContextResolver hint

    # ── 第二阶段（暂不加）──
    # signal_domain: str = ""
    # policy_profile: str = ""
```

---

## 4. contextvars 绑定

```python
# kernel/role_context.py (~25L)
from __future__ import annotations
import contextlib
import contextvars
from chatgptrest.kernel.team_types import RoleSpec

_current_role: contextvars.ContextVar[RoleSpec | None] = contextvars.ContextVar(
    "current_agent_role", default=None
)

@contextlib.contextmanager
def with_role(role: RoleSpec):
    token = _current_role.set(role)
    try:
        yield role
    finally:
        _current_role.reset(token)

def get_current_role() -> RoleSpec | None:
    return _current_role.get()

def get_current_role_name() -> str:
    role = _current_role.get()
    return role.memory_namespace if role else ""
```

---

## 5. 角色配置

```yaml
# config/agent_roles.yaml
roles:
  devops:
    description: "ChatgptREST 系统运维与代码开发"
    prompt: |
      你是 ChatgptREST 系统的运维与开发专家。
      改动前必须评估 blast radius。决策标准：可用性 > 性能 > 功能。
    tools: [chatgptrest_*, gitnexus_*, chrome-devtools, run_command]
    model: sonnet
    memory_namespace: devops
    kb_scope_tags: [chatgptrest, ops, infra, driver, mcp, runbook]

  research:
    description: "深度研究与分析"
    prompt: |
      你是 thesis-first 的研究分析师。
      产出必须有证据支撑。报告结构：核心发现 → 证据链 → 行动建议。
    tools: [chatgptrest_ask, chatgptrest_consult, web_search, read_url_content]
    model: sonnet
    memory_namespace: research
    kb_scope_tags: [research, finagent, education, analysis, market]
```

---

## 6. Memory 查询路径变更

```python
# MemoryManager — 新增 role_id 参数（不改 agent_id 语义）

def get_episodic(self, query="", category="", limit=10,
                 agent_id="", session_id="",
                 role_id="") -> list[MemoryRecord]:        # ← 新增
    # ...existing filters...
    if agent_id:
        clauses.append("json_extract(source, '$.agent') = ?")
        params.append(agent_id)
    if role_id:                                             # ← 新增
        clauses.append("json_extract(source, '$.role') = ?")
        params.append(role_id)
```

```python
# ContextService.build() — 注入 role

from chatgptrest.kernel.role_context import get_current_role

# 在 build episodic memory 时
role = get_current_role()
episodic = self._mm.get_episodic(
    query=...,
    agent_id=agent_id,                     # 保持原有组件过滤
    role_id=role.memory_namespace if role else "",  # 新增角色过滤
    session_id=session_id,
)
```

---

## 7. Memory 写入路径变更

```python
# memory_capture_service.py:_capture_one — 自动注入 role

from chatgptrest.kernel.role_context import get_current_role_name

source = MemorySource(
    type=...,
    agent=...,                    # 保持组件名
    role=get_current_role_name(), # 从 contextvars 自动注入
    session_id=...,
    task_id=...,
)
```

---

## 8. 验证计划

### 8.1 单元测试

```python
# tests/test_role_pack.py — 核心场景
class TestRoleMemoryIsolation:
    def test_role_write_and_read(self):
        """role=devops 写入 → role=devops 查询能拿到"""

    def test_role_isolation(self):
        """role=devops 写入 → role=research 查询拿不到"""

    def test_agent_preserved(self):
        """role=devops 写入时 source.agent 仍为组件名"""

    def test_no_role_returns_all(self):
        """不指定 role_id → 返回所有记录（向后兼容）"""

    def test_cold_start_empty(self):
        """新 role 冷启动 → 返回空列表（不报错）"""
```

### 8.2 Cold Role Acceptance（复用 cold client 模式）

```
cold role acceptance:
  1. 起新 session
  2. with_role(devops): 写 1 条 memory
  3. with_role(devops): 查，验证拿到
  4. with_role(research): 查，验证拿不到
  5. 不指定 role: 查，验证两条都拿到
  6. 验证 source.agent 仍为组件名
```

---

## 9. 明确不做的事

| 事项 | 理由 |
|------|------|
| coordinator 角色 | 历史包袱，main 继续做 controller |
| 自动 role_hint | 先让 workflow 显式选 |
| EvoMap/Policy 角色化 | 后置到第二阶段，与 kb_codex import contract 对齐 |
| 回改历史 572 条 memory records | 不需要，source.role=NULL 表示"无角色上下文" |
| KBRetriever.search() 默认按 role 过滤 | 过滤在 router 层，不在 retrieval 层 |
| 改 `source.agent` 语义 | agent = 组件身份，保持不变 |

---

## 10. 控制模型

```
人类 (main controller)
   │
   ├── 显式选择 role: "用 devops 排查这个问题"
   │
   ├── main agent (唯一 controller)
   │     │
   │     ├── with_role(devops):
   │     │     ├── memory(role_id=devops): 拿到 devops 上下文
   │     │     │   └── source.agent 仍为 advisor/openclaw（组件归因保留）
   │     │     ├── KB: 暂不按 tag 过滤（等 1C 完成）
   │     │     └── 执行任务
   │     │
   │     └── with_role(research):
   │           ├── memory(role_id=research): 拿到 research 上下文
   │           ├── KB: 暂不按 tag 过滤
   │           └── 执行任务
   │
   └── maintagent (watchdog，不变)

不存在 coordinator agent。
不存在自动角色选择。
role 是 main 的一把工具，不是独立人格。
```

---

## 附录：与各方判断的对齐表

| 论点 | v2 | v3 | addendum | codex 评审 | 交叉验证 | **v4** |
|------|----|----|----------|-----------|---------|--------|
| Memory 就绪 | ✅ | ❌先修 | ✅冷启动 | ✅但不复用 agent | — | ✅冷启动 + source.role |
| 复用 source.agent | 隐含 | 隐含 | ✅直接复用 | ❌必须分开 | — | **❌新增 source.role** |
| KB ~15行 | ✅ | 治理层更大 | 0%冷启动 | 治理先行 | 在错误层 | **router hint，不在 retrieval** |
| KB 903=全量 | 隐含 | 隐含 | 隐含 | 未提及 | ❌755MB 才是 | **FTS5=检索表面** |
| coordinator | ✅ | ❌ | ❌ | ❌ | — | **❌** |
| auto role_hint | ✅ | ❌ | ❌ | ❌ | — | **❌** |
| EvoMap | P0 | P2 | P2 | P2 | 与 import contract 对齐 | **P2** |
| identity 前提 | 未提及 | 顺序前提 | 不需要 | 并行治理 | — | **并行治理** |
