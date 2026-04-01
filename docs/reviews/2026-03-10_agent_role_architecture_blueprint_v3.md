# Agent 角色架构蓝图 v3 — 可执行收敛版

> 日期：2026-03-10 | 基于主库 codex 对 v2 的评审反馈收敛
> 前序：v2（GitNexus 全景分析） → 主库 codex 评审 → 本版

---

## 0. v2 → v3 变更摘要

| 项目 | v2 判断 | 主库 codex 纠偏 | v3 定论 |
|------|---------|-----------------|---------|
| Memory Plane | "已就绪 ✅" | identity gaps 未打通，不是只差传 namespace | **待打通**，先修 identity 再接角色 |
| KB 接入 | "~15 行" | 技术入口 15 行，但 tag 治理/覆盖率/写入纪律是真正难点 | **技术层 + 治理层**分开处理 |
| EvoMap 角色化 | "改 signal.source ~5 行" | 讲早了，当前 EvoMap 更适合做观察层 | **第二阶段** |
| Policy 角色化 | "PolicyEngine 加 role_id ~30 行" | 同上 | **第二阶段** |
| coordinator 角色 | 三角色之一 | 会重新长出 pmagent/orch 包袱 | **砍掉** |
| 自动 role_hint | Advisor 意图分析推断角色 | 太像隐式角色路由器 | **砍掉**，role 显式选 |
| 角色数量 | 3 个 (devops/researcher/coordinator) | coordinator 是历史包袱 | **2 个** (devops/research) |

---

## 1. 保留的内核（只做这三件事）

1. **扩展 `RoleSpec`**（`kernel/team_types.py`）
2. **`contextvars` 绑定当前 role**（`kernel/role_context.py`）
3. **先做 memory + KB 两平面的 role pack**

其他全部后置。

---

## 2. RoleSpec 扩展（最小字段）

```python
# kernel/team_types.py — 只加第一阶段需要的字段
@dataclass
class RoleSpec:
    # ── 已有字段 (不变) ──
    name: str
    description: str = ""
    prompt: str = ""
    tools: list[str] = field(default_factory=list)
    model: str = "sonnet"
    
    # ── 第一阶段：只加这两个 ──
    memory_namespace: str = ""                                  # → agent_id for MemoryManager
    kb_scope_tags: list[str] = field(default_factory=list)      # → KBHub tag filter
    
    # ── 第二阶段（暂不加，等第一阶段验证后再考虑）──
    # signal_domain: str = ""
    # policy_profile: str = ""
    # budget_limit_usd: float = 0.0
    # gate_actions: list[str] = field(default_factory=list)
```

**原则**：只加当前阶段要用的字段，不预埋。

---

## 3. contextvars 绑定

```python
# kernel/role_context.py (~20L)
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
```

**调用方式**：workflow 显式选 role → `with_role(devops_role):` → 该上下文内所有平面自动读取角色。

---

## 4. 角色配置（只定义 2 个）

```yaml
# config/agent_roles.yaml
roles:
  devops:
    description: "ChatgptREST 系统运维与代码开发"
    prompt: |
      你是 ChatgptREST 系统的运维与开发专家。
      你了解 REST 作业队列、CDP driver、MCP 适配器的全部架构。
      决策标准：可用性 > 性能 > 功能。
      改动前必须评估 blast radius。
    tools:
      - chatgptrest_*
      - gitnexus_*
      - chrome-devtools
      - run_command
    model: sonnet
    memory_namespace: devops
    kb_scope_tags: [chatgptrest, ops, infra, driver, mcp, runbook]

  research:
    description: "深度研究与分析"
    prompt: |
      你是论文-first 的研究分析师。
      产出必须有数据支撑，拒绝无证据的结论。
      报告结构：核心发现 → 证据链 → 行动建议。
    tools:
      - chatgptrest_ask
      - chatgptrest_consult
      - web_search
      - read_url_content
    model: sonnet
    memory_namespace: research
    kb_scope_tags: [research, finagent, education, analysis, market]
```

**不做 coordinator**。项目协调继续由 main 做。需要 lane control 时，做 lane control plane，不做人格 agent。

---

## 5. Memory 接入：先修 identity，再接角色

### 5.1 问题现状

v2 说"Memory Plane 已就绪"是过头了。实际情况：

- `ContextService.resolve()` 确实在传 `agent_id` 参数
- 但 live verifier 显示 `identity_gaps` 仍存在（`missing_session_key`、`missing_agent_id`、`missing_account_id`）
- identity 不通，传 `memory_namespace` 进去也是空转

### 5.2 执行顺序

```
Step 1: 审计 identity 打通率
        → 跑 ContextResolver 在真实请求中有多少次 identity_gaps 非空
        → 确认 agent_id 实际被使用的比例

Step 2: 修 identity 缺失
        → 确保调用链上的调用方真正传入 agent_id
        → 至少保证 Advisor 入口和 MCP 入口两条路径

Step 3: 然后才接 role.memory_namespace → agent_id
        → ContextService 改 1 行
        → 但前提是 Step 1-2 已验证
```

---

## 6. KB 接入：技术层 + 治理层

### 6.1 技术层（确实 ~15 行）

```python
# kb/hub.py — search() 加 tags 参数
def search(self, query, *, tags=None, top_k=5, auto_embed=True):
    role = get_current_role()
    effective_tags = tags or (role.kb_scope_tags if role else None)
    return self._retriever.search(query, tags=effective_tags, top_k=top_k, ...)
```

### 6.2 治理层（这才是真正的工作量）

技术入口 15 行能改完，但以下问题不解决，角色化 KB 就是脆弱过滤：

| 治理项 | 状态 | 必须先做 |
|--------|------|---------|
| 813 个文档的 tag 覆盖率审计 | ❓未知 | ✅ 先跑一次统计 |
| tag 写入纪律（新文档必须打 tag） | ❓未规定 | ✅ 加入 KB 写入检查 |
| tag 词表（哪些 tag 合法） | ❓未定义 | ✅ 定义受控词表 |
| KB writeback 自动打 tag | ❓未实现 | ⚠️ 第一阶段手动，第二阶段自动 |

### 6.3 执行顺序

```
Step 1: 审计 KB tag 覆盖率
        → SELECT doc_id, tags FROM kb_documents → 统计有 tag 的比例

Step 2: 定义 tag 受控词表
        → 对齐 agent_roles.yaml 中的 kb_scope_tags

Step 3: 补打 tag（批量）
        → 对现有 813 个文档按内容打初始 tag

Step 4: 加 tag 过滤到 KBHub.search()（技术层 15 行）

Step 5: 加 tag 写入检查到 KB writeback pipeline
```

---

## 7. 明确不做的事（第一阶段）

| 事项 | 理由 |
|------|------|
| coordinator 角色 | 会长出 pmagent/orch 历史包袱；main 仍是唯一 controller |
| 自动 role_hint（Advisor 推断角色） | 太像隐式路由器；先让 workflow 显式选 |
| EvoMap signal.source 角色化 | EvoMap 当前适合做观察层，不适合做 role runtime contract |
| PolicyEngine role_id 策略 | 第二阶段 |
| TeamScorecard 按 role 聚合 | 第二阶段 |
| budget_limit_usd | 第二阶段 |
| gate_actions | 第二阶段 |

---

## 8. 阶段划分

### 第一阶段：Role Pack（memory + KB）

```
目标：main 控制下的按需 devops/research role packs
      只接 memory + KB，显式选角色

改动清单：
├── kernel/team_types.py        +2 字段 (~5L)
├── kernel/role_context.py      新文件 (~20L)
├── kernel/role_loader.py       新文件 (~40L)  
├── config/agent_roles.yaml     新文件 (~30L)
├── cognitive/context_service.py 改 1 行（agent_id fallback to role）
├── kb/hub.py                   改 3 行（tags 透传）
├── kb/retrieval.py             确认 tags 过滤已支持
└── tests/test_role_pack.py     新文件 (~60L)

前提条件：
├── identity gaps 审计 + 修复
└── KB tag 覆盖率审计 + tag 词表 + 批量补打

总改动量：~160L 代码 + 治理工作
```

### 第二阶段：观察 + 策略（待第一阶段验证）

```
考虑项（不承诺）：
├── signal_domain → EvoMap
├── policy_profile → PolicyEngine
├── budget tracking
├── gate_actions
└── route 层给 role 建议（但不自动决定）
```

---

## 9. 控制模型

```
人类 (main controller)
   │
   ├── 显式选择 role: "用 devops 排查这个问题"
   │
   ├── main agent (唯一 controller)
   │     │
   │     ├── with_role(devops):
   │     │     ├── memory(namespace=devops): 拿到 devops 上下文
   │     │     ├── KB(tags=[chatgptrest,ops,...]): 拿到 ops 知识
   │     │     └── 执行任务
   │     │
   │     └── with_role(research):
   │           ├── memory(namespace=research): 拿到 research 上下文
   │           ├── KB(tags=[research,finagent,...]): 拿到研究知识
   │           └── 执行任务
   │
   └── maintagent (watchdog，不变)

不存在 coordinator agent。
不存在自动角色选择。
role 是 main 的一把工具，不是独立人格。
```
