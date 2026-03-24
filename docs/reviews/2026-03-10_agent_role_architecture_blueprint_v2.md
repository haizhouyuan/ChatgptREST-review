# Agent 角色架构蓝图 v2 — 基于 GitNexus 全景分析

> 日期：2026-03-10 | GitNexus 图谱验证版 | ChatgptREST (250,476 symbols) + OpenClaw upstream

---

## 0. 方法论

本文档基于 GitNexus 代码智能图谱的 **全量分析**，不是靠猜、不是靠 grep：

- **ChatgptREST 图谱**：250,476 符号、314,325 关系、239 执行流、44 功能社区
- **OpenClaw upstream 图谱**：跨社区索引
- **关键路径追踪**：`AdvisorRuntime → AdvisorGraph → CcExecutor → Memory/KB/EvoMap`
- **360° 符号上下文**：对 `AdvisorRuntime`、`RoleSpec`、`CcExecutor`、`ContextResolveOptions` 等核心符号做了完整的 caller/callee/process 分析

---

## 1. 代码实体全景图（GitNexus 验证）

### 1.1 四层平面的真实代码映射

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AdvisorRuntime (788L)                        │
│                    composition root / singleton                      │
│  初始化 20+ 服务，通过 EventBus 桥接所有平面                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────────┐
         │                   │                       │
         ▼                   ▼                       ▼
┌─────────────────┐ ┌─────────────────┐ ┌──────────────────────┐
│  Memory Plane   │ │   Graph Plane   │ │   Evolution Plane    │
│                 │ │                 │ │                      │
│ MemoryManager   │ │ KBHub(FTS5+Vec) │ │ EvoMapObserver       │
│   681L, 4-tier  │ │ 408L, 813 docs  │ │ 323L, 20+ signals   │
│   agent_id: ✅  │ │ tags: ✅        │ │ source field: ✅     │
│   session_id:✅  │ │ quality: ✅     │ │ TeamScorecard: ✅    │
│                 │ │                 │ │ TeamPolicy MAB: ✅   │
│ ContextAssembler│ │ KBWriteback     │ │ CircuitBreaker       │
│   passes        │ │ PolicyEngine    │ │ KBScorer             │
│   agent_id ✅   │ │ gated ✅        │ │ GateAutoTuner        │
└────────┬────────┘ └────────┬────────┘ └──────────┬───────────┘
         │                   │                      │
         └───────────────────┼──────────────────────┘
                             │
                      ┌──────┴──────┐
                      │   EventBus  │
                      │  bridge all │
                      │   planes    │
                      └──────┬──────┘
                             │
              ┌──────────────┼──────────────────┐
              ▼              ▼                  ▼
        → Observer     → Memory (meta)   → 3 Actuators
        (signals DB)   (event records)   (CB/KBS/GAT)
```

### 1.2 OpenClaw 执行壳的真实代码映射

```
ChatgptREST 侧:                 OpenClaw upstream 侧:
┌──────────────────────┐        ┌────────────────────────────┐
│ CcExecutor (1360L)   │        │ team-dispatcher.tool-      │
│ CcNativeExecutor     │──CLI──▶│ adapter.ts (spawn/send)    │
│   uses TeamPolicy    │        │                            │
│   uses TeamScorecard │        │ AcpGatewayAgent (453L)     │
│                      │        │   A2A 协议网关             │
│ AgentProfile (L184)  │        │                            │
│   system_prompt ✅   │        │ system-prompt.ts            │
│   tools ✅           │        │   buildSkillsSection()     │
│   model ✅           │        │   buildMemorySection()     │
│                      │        │                            │
│ OpenClawAdapter      │        │ EvomapLoopService (730L)   │
│   sessions_send()    │        │   进化循环                 │
│   sessions_spawn()   │        │                            │
│   sessions_status()  │        └────────────────────────────┘
└──────────────────────┘
```

### 1.3 决策路由链

```
用户请求
   │
   ├── /v2/advisor/advise → AdvisorAPI → advisor_fn()
   │      │
   │      ▼
   │   AdvisorGraph (LangGraph StateGraph)
   │      normalize → kb_probe → analyze_intent → route_decision
   │      │                                           │
   │      │   route = quick_ask / deep_research /     │
   │      │           report / funnel                  │
   │      │                                           │
   │      ├── quick_ask   → KB synthesis + LLM        │
   │      ├── deep_research → chatgptrest_ask (MCP)   │
   │      ├── report      → report_graph (7 nodes)    │
   │      └── funnel      → ProjectCard → tasks       │
   │                         → CcNativeExecutor        │
   │                            → TeamPolicy.select()  │
   │                            → TeamSpec + RoleSpec   │
   │                            → CcExecutor.run()     │
   │
   ├── /v2/context/resolve → ContextResolver
   │      │
   │      ▼
   │   ContextResolveOptions { query, agent_id, session_id, ... }
   │      │
   │      ├── Memory (working/episodic/captured/semantic)
   │      │     ← agent_id 过滤已实现 ✅
   │      ├── KB (FTS5 + vector)
   │      │     ← 无 tag 过滤 ❌
   │      ├── EvoMap (atoms retrieval)
   │      │     ← 无 role 过滤 ❌
   │      └── Policy hints
   │            ← 无 role-aware 策略 ❌
   │
   └── /v2/memory/* → MemoryCaptureService
          memory_capture → MemoryCaptureItemResult
```

---

## 2. 已有角色定义基础设施（被忽视的宝藏）

GitNexus 发现了 **3 个已存在的角色定义原型**，它们分散在不同模块里，没有统一连接：

| 原型 | 文件 | 字段 | 当前用途 |
|------|------|------|---------|
| **RoleSpec** | `kernel/team_types.py` L22-50 | `name`, `description`, `prompt`, `tools`, `model` | TeamSpec 组合 → CcExecutor dispatch |
| **AgentProfile** | `kernel/cc_executor.py` L184-191 | `system_prompt`, `tools`, `model` | CcExecutor 内部用 |
| **AgentSpec** | `ops/openclaw_orch_agent.py` L24-28 | ops 层 agent 定义 | orch 巡检 |

**关键发现**：`RoleSpec` 距离完整的 `AgentRole` 只差 4 个字段：

```diff
  @dataclass
  class RoleSpec:
      name: str
      description: str = ""
      prompt: str = ""
      tools: list[str] = field(default_factory=list)
      model: str = "sonnet"
+     memory_namespace: str = ""       # → MemoryManager agent_id
+     kb_scope_tags: list[str] = ()    # → KBHub search filter  
+     signal_domain: str = ""          # → EvoMap signal source
+     policy_profile: str = ""         # → PolicyEngine rules
```

---

## 3. 四个平面的"角色化"接口现状

### 3.1 Memory Plane — **已就绪** ✅

`ContextService.resolve()` 已经在传 `agent_id`：
- `get_episodic(query, agent_id=agent_id)` — 按角色过滤历史任务（L367-370）
- `get_semantic(domain, agent_id=agent_id)` — 按角色过滤稳定知识（L414-415）
- `get_working_context(session_id=session_id)` — 按会话隔离实时上下文（L350-351）
- `get_episodic(category="captured_memory", agent_id=agent_id)` — 跨会话记忆（L387-400）

**只需要**：把 `RoleSpec.memory_namespace` 作为 `agent_id` 传入。

### 3.2 Graph Plane (KB) — **接口有，过滤缺** ⚠️

`KBRetriever.search()` 支持 `tags` 参数（FTS5 索引已打 tag）。
`index_document()` 也支持 `tags` 参数。

**缺失**：
- `KBHub.search()` 没有透传 `tags` 到 `KBRetriever.search()`
- `ContextService` 调用 `kb_hub.search(query, top_k=kb_top_k)` 时没传 tags

**改动量**：~10 行。在 `KBHub.search()` 加 `tags` 参数，在 `ContextService` 从 role 读取。

### 3.3 Evolution Plane — **格式有，语义缺** ⚠️

`Signal` 已有 `source` 字段，已有 `domain` 字段。
`EvoMapObserver.record()` 直接存 signal。
`TeamScorecard` 按 `team_id` 聚合成绩。

**缺失**：
- `source` 没有强制按角色填写（当前随意填 "advisor"、"llm_connector"、"cc_executor"）
- `TeamScorecard` 按 `team_id`（团队组合 hash）聚合，不按 `role_id`
- 没有"角色能力维度"的定义（哪些 signal 代表哪个能力）

**改动量**：在 event emit 时从当前 role 注入 `signal.source = role.signal_domain`，~5 行。按 role_id 追加一个 scorecard 维度需要 ~30 行。

### 3.4 Policy Plane — **引擎有，角色策略缺** ⚠️

`PolicyEngine.run_quality_gate(ctx)` 已运行 content 审查。
`RoutingFabric` 管理模型选择和 fallback。
`AdvisorGraph` 的 `route_decision()` 管路由。

**缺失**：
- `PolicyEngine` 不知道当前角色，策略不区分角色
- 没有 per-role 的 budget tracking
- 没有 per-role 的 gate rules

**改动量**：`QualityContext` 加 `role_id` 字段，`PolicyEngine` 加角色策略加载 ~30 行。

---

## 4. 连接方案：RoleSpec 扩展 + RuntimeContext

### 4.1 不新建系统，扩展已有类型

```python
# 方案 A: 直接扩展 RoleSpec (最小改动)
@dataclass
class RoleSpec:
    # ── 已有字段 (不变) ──
    name: str
    description: str = ""
    prompt: str = ""
    tools: list[str] = field(default_factory=list)
    model: str = "sonnet"
    
    # ── 新增：四平面绑定 ──
    memory_namespace: str = ""            # → agent_id for MemoryManager
    kb_scope_tags: list[str] = field(default_factory=list)  # → KBHub tag filter
    signal_domain: str = ""               # → EvoMap signal source
    policy_profile: str = ""              # → PolicyEngine strategy set
    budget_limit_usd: float = 0.0         # → cost tracking boundary
    gate_actions: list[str] = field(default_factory=list)    # → 需要审批的操作
```

### 4.2 RuntimeContext（传递当前角色）

```python
# 方案：用 contextvars 传递当前 role，零侵入
import contextvars

_current_role: contextvars.ContextVar[RoleSpec | None] = contextvars.ContextVar(
    "current_agent_role", default=None
)

@contextlib.contextmanager
def with_role(role: RoleSpec):
    """Bind role for current execution context."""
    token = _current_role.set(role)
    try:
        yield role
    finally:
        _current_role.reset(token)

def get_current_role() -> RoleSpec | None:
    return _current_role.get()
```

**这个模式已经在 `advisor/graph.py` 的 `bind_runtime_services()` 里用过了**。完全一致的方法。

### 4.3 各平面的接入点

```python
# Memory — ContextService 改 1 行
agent_id = options.agent_id or getattr(get_current_role(), "memory_namespace", "")

# KB — KBHub.search() 改 3 行
def search(self, query, *, tags=None, ...):
    role = get_current_role()
    effective_tags = tags or (role.kb_scope_tags if role else None)
    
# EvoMap — _emit_event 改 2 行
def _emit_event(state, event_type, source, data=None):
    role = get_current_role()
    effective_source = (role.signal_domain if role else source) or source

# Policy — policy_check 改 2 行
def _policy_check(state, effect_type, ...):
    role = get_current_role()
    ctx.role_id = role.name if role else ""
```

---

## 5. 角色配置（YAML + 加载器）

### 5.1 配置文件

```yaml
# config/agent_roles.yaml
roles:
  devops:
    description: "ChatgptREST 系统运维专家"
    prompt: |
      你是 ChatgptREST 系统的运维专家。
      你了解 REST 作业队列、CDP driver、MCP 适配器的全部架构。
      你的决策标准：可用性 > 性能 > 功能。
      你在做任何改动前必须评估 blast radius。
    tools:
      - chatgptrest_*
      - gitnexus_*
      - chrome-devtools
      - run_command
    model: sonnet
    memory_namespace: devops
    kb_scope_tags: [chatgptrest, ops, infra, driver, mcp, runbook]
    signal_domain: devops
    policy_profile: ops_conservative
    budget_limit_usd: 5.0
    gate_actions: [push_to_master, restart_service, delete_data]

  researcher:
    description: "深度研究分析师"
    prompt: |
      你是论文-first 的研究分析师。
      你的产出必须有数据支撑，拒绝无证据的结论。
      你的报告结构：核心发现 → 证据链 → 行动建议。
    tools:
      - chatgptrest_ask
      - chatgptrest_consult
      - web_search
      - read_url_content
      - generate_image
    model: sonnet
    memory_namespace: researcher
    kb_scope_tags: [research, finagent, education, analysis, market]
    signal_domain: research
    policy_profile: research_thorough
    budget_limit_usd: 20.0
    gate_actions: [external_publish, investment_decision]

  coordinator:
    description: "多 Lane 协调员 / 项目管理"
    prompt: |
      你是多 lane 协调员。
      你的职责：追踪各 lane 进展、发现矛盾、在需要时通知人类。
      你不做具体的开发或研究，你管流程。
    tools:
      - chatgptrest_issue_*
      - chatgptrest_ops_*
      - gh_cli
      - git
    model: sonnet
    memory_namespace: coordinator  
    kb_scope_tags: [project, lane, milestone, issue, roadmap]
    signal_domain: coordination
    policy_profile: coordination_lean
    budget_limit_usd: 2.0
    gate_actions: [merge_approval, lane_redirect, budget_override]
```

### 5.2 加载器

```python
# chatgptrest/kernel/role_loader.py (~40L)
import yaml
from chatgptrest.kernel.team_types import RoleSpec

_ROLES: dict[str, RoleSpec] = {}

def load_roles(config_path: str = "config/agent_roles.yaml") -> dict[str, RoleSpec]:
    with open(config_path) as f:
        data = yaml.safe_load(f)
    for name, cfg in data.get("roles", {}).items():
        cfg["name"] = name
        _ROLES[name] = RoleSpec.from_dict(cfg)
    return _ROLES

def get_role(name: str) -> RoleSpec | None:
    return _ROLES.get(name)
```

---

## 6. 和 OpenClaw upstream 的对齐

GitNexus 在 OpenClaw upstream 中发现了以下对应物：

| ChatgptREST 概念 | OpenClaw upstream 对应 | 状态 |
|-------------------|----------------------|------|
| RoleSpec.prompt | `system-prompt.ts:buildSkillsSection()` + `buildMemorySection()` | ✅ 可对接 |
| RoleSpec.tools | `team-dispatcher.tool-adapter.ts:spawn()` 的工具注册 | ✅ 可对接 |
| TeamPolicy MAB | `EvomapLoopService` (730L) 的进化循环 | ✅ 逻辑吻合 |
| ContextResolveOptions | OpenClaw 的 context injection 机制 | ✅ 已通过 `/v2/context/resolve` 对接 |
| AgentRole.gate_actions | `AcpGatewayAgent` (453L) 的 A2A gate 控制 | ⚠️ 协议级对齐待做 |

**关键发现**：OpenClaw upstream 的 `buildMemorySection()` 已经在构建 system prompt 时注入记忆上下文。ChatgptREST 的 `ContextService` 通过 `/v2/context/resolve` 为 OpenClaw 提供上下文包。**角色化的上下文注入路径已经通了**。

---

## 7. 数据流：一个请求的完整角色化生命周期

```
用户: "ChatgptREST driver timeout 排查"
   │
   ├─[1] Advisor 意图分析 → intent = DO_RESEARCH, role_hint = "devops"
   │     (keyword: "ChatgptREST" + "driver" + "timeout" → 命中 devops.kb_scope_tags)
   │
   ├─[2] with_role(devops):         ← contextvars 绑定
   │     │
   │     ├─[3] ContextService.resolve(agent_id="devops")
   │     │      ├── Memory(agent_id="devops"): 过去的 incident 记录
   │     │      ├── KB(tags=["chatgptrest","ops","driver"]): runbook/handoff
   │     │      ├── EvoMap: driver 相关的知识原子
   │     │      └── Policy hints: "devops role, conservative"
   │     │
   │     ├─[4] Route execution (deep_research)
   │     │      → 产出: 分析报告
   │     │
   │     ├─[5] EvoMap record:
   │     │      Signal(source="devops", type="route.completed", domain="advisor")
   │     │      Signal(source="devops", type="kb.artifact_retrieved", domain="kb")
   │     │
   │     ├─[6] Memory write:
   │     │      agent_id="devops", tier=EPISODIC
   │     │      key="incident:driver_timeout:20260310"
   │     │
   │     └─[7] KB writeback:
   │            tags=["chatgptrest","ops","driver","incident"]
   │            → 下次 devops 角色可以检索到这次分析
   │
   └─[8] TeamScorecard.record(role="devops", task="incident_triage", ok=True)
         → 下次 TeamPolicy.select() 时 devops 的 incident_triage 能力分上升
```

---

## 8. 实施路径（按依赖排序）

| 顺序 | 改动 | 文件 | 行数 | 前提 |
|------|------|------|------|------|
| **S1** | `RoleSpec` 增加 4 个字段 | `kernel/team_types.py` | +10L | 无 |
| **S2** | YAML 配置 + 加载器 | `config/agent_roles.yaml` + `kernel/role_loader.py` | +100L | S1 |
| **S3** | `contextvars` role 绑定 | `kernel/role_context.py` | +25L | S1 |
| **S4** | ContextService 透传 role namespace | `cognitive/context_service.py` | +5L | S3 |
| **S5** | KBHub.search() 加 tags 过滤 | `kb/hub.py` + `kb/retrieval.py` | +15L | S3 |
| **S6** | Signal emit 打 role 标签 | `advisor/graph.py` | +5L | S3 |
| **S7** | PolicyEngine 角色策略 | `kernel/policy_engine.py` | +30L | S3 |
| **S8** | Advisor 路由入口绑 role | `advisor/graph.py` / `api/routes_advisor_v3.py` | +20L | S2+S3 |
| **S9** | TeamScorecard 按 role 聚合 | `evomap/team_scorecard.py` | +30L | S6 |
| **S10** | 测试 | `tests/test_role_*.py` | +100L | S1-S9 |

**总改动量：~340L，分布在 10 个文件**

---

## 9. 和上一版 v1 蓝图的关键修正

| 项目 | v1 蓝图（上一版） | v2 蓝图（本版 GitNexus 验证） |
|------|------------------|----------------------------|
| 角色定义载体 | 新建 `AgentRole` dataclass | **扩展已有 `RoleSpec`**（仅加 4 字段） |
| 角色绑定机制 | 未明确 | **`contextvars`（已有先例 `bind_runtime_services`）** |
| Memory 接入 | "改动量 0" | **确认 0 改动，ContextService 已传 agent_id** |
| KB 接入 | "加 tag 过滤 ~10L" | **确认需 ~15L，KBHub.search + KBRetriever** |
| EvoMap 接入 | "signal.source 赋值" | **确认可行，但 TeamScorecard 按 role 聚合需额外 ~30L** |
| 与 OpenClaw 关系 | 未分析 | **已验证 system-prompt.ts + EvomapLoopService 吻合** |
| AdvisorRuntime 角色 | 视为外部 | **确认是 composition root，角色绑定应在此完成** |

---

## 10. 风险与前提

1. **`RoleSpec` 是 `TeamSpec` 的子组件**。扩展它不影响 `TeamSpec` 的 `team_id` 计算（只用 `name:model`），但新增字段不参与 hash，设计上合理。
2. **`contextvars` 在异步场景下的行为**。`AdvisorGraph` 使用 LangGraph 的 `invoke()` 是同步的，`contextvars` 正常工作。如果未来改为 `ainvoke()`，需要确认 Python 的 `contextvars` 在 `asyncio.Task` 间正确传播（默认是）。
3. **KB 的 tag 数据质量**。813 个文档的 tag 覆盖率未验证。如果 tag 稀疏，角色化 KB 过滤会返回空结果。需要先审计 tag 覆盖率。
4. **向后兼容**。所有新字段都有默认值。无 role 时行为与现在完全一致。
