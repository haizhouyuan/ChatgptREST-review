# Agent Teams 框架对比研究与 ChatgptREST 统一编排实现方案

> 日期：2026-03-10 | 研究范围：Claude Code Agent Teams, Google A2A, OpenClaw, AutoGen v0.4, CrewAI, LangGraph

---

## 1. 框架深度对比

### 1.1 架构模式总览

| 维度 | Claude Agent Teams | Google A2A (RC v1.0) | OpenClaw A2A | AutoGen v0.4 / Magentic-One | CrewAI | LangGraph 1.0 |
|------|-------------------|---------------------|--------------|---------------------------|--------|---------------|
| **架构哲学** | Lead + Teammates, 进程内 | 跨进程/跨组织的 Task 协议 | Session-based 消息传递 | Event-driven Actor Model | Role-based Crew 协作 | Graph-based 状态机 |
| **通信方式** | JSON 文件 on disk，Lead 轮询 | JSON-RPC / gRPC / HTTP+REST + SSE | sessions_send/spawn (MCP tools) | Async messages (pub-sub + request/response) | 内部 memory 传递 | Shared state + edges |
| **发现机制** | 无（Lead 定义 Teammates） | Agent Cards (`/.well-known/agent.json`) | OpenClaw 的 agent registry | Topic-based subscriptions | 代码中定义 Crew | 代码中定义 Graph |
| **隔离粒度** | 独立 context window | 完全 opaque execution | 独立 session (进程级隔离) | 独立 actor（可跨进程） | 共享 memory（可配隔离） | 共享 state（reducer 控制） |
| **状态管理** | 无持久状态 | Task 有 lifecycle (submitted→working→done) | Session 持久化 | Runtime + external store | 内置 memory | Checkpointing (持久化+回滚) |
| **人类介入** | Terminal 直接交互 | 协议层不涉及 | OpenClaw UI / messaging | AutoGen Studio UI | callbacks / guardrails | interrupt_before/after nodes |
| **学习/进化** | 无 | 无 | 无 | 无 | Agent training (beta) | 无 |
| **生产成熟度** | Production (Opus 4.6) | RC v1.0（协议，非实现） | Production (self-hosted) | AgentChat stable, Core beta | Production（SaaS + OSS） | 1.0 (Oct 2025) |

### 1.2 每个框架的核心设计决策

#### Claude Code Agent Teams
```
Lead Agent ─┬── Teammate A (独立 context window)
             ├── Teammate B
             └── Teammate C

通信：JSON 文件 on disk（~/.claude/projects/*/teams/*)
模式：--teammate-mode in-process | tmux-split-pane | iterm2-split-pane
特点：
  ✅ 最低门槛（CLI flag），与你当前 cc_executor 的 --agents 参数直接对应
  ✅ 每个 Teammate 有完整 tool access（read/write/execute）
  ❌ 无跨进程通信——所有 Teammates 在同一台机器
  ❌ 无持久状态——session 结束全部丢失
  ❌ Lead 的上下文需要装下所有 Teammate 的输出
```

#### Google A2A Protocol
```
Client Agent ──→ POST /tasks/send ──→ Remote Agent
                                        │
                   ←── SSE: TaskStatusUpdateEvent ←──┘
                   ←── SSE: TaskArtifactUpdateEvent

核心概念：
  Task         = 有状态的工作单元 (submitted → working → input-required → completed/failed/canceled)
  Message      = 角色标记的内容容器 (agent/user)
  Artifact     = 任务产物 (file/structured data)
  Agent Card   = 自描述元数据 (capabilities, auth, protocols)
  Push Notif   = Webhook 回调机制

3 层绑定：JSON-RPC 2.0 | gRPC | HTTP+JSON/REST
```

> **关键洞察**：A2A 是**协议**不是**框架**。它不告诉你如何在内部编排 agent，而是定义 agent 之间怎么发现和交换任务。你的系统需要在 A2A 协议**之上**建编排逻辑。

#### OpenClaw A2A
```
Agent A ──sessions_send(session_key, message)──→ Agent B
Agent A ──sessions_spawn(agent_id, instructions)──→ Sub-Agent C (isolated)
Agent A ──session_status(session_key)──→ 查询结果

特点：
  ✅ 你的代码库已经 wire 了（OpenClawAdapter: spawn/send/status）
  ✅ A2A v1.0 compliant（可与标准 A2A 客户端互操作）
  ✅ Session 持久化（OpenClaw 管理）
  ❌ 无编排逻辑——只是传输层
  ❌ Sub-agent 不能再 spawn sub-agent（单层）
  ❌ 无 task lifecycle tracking
```

#### AutoGen v0.4 / Magentic-One
```
Orchestrator (Task Ledger + Progress Ledger)
     ├── WebSurfer
     ├── FileSurfer
     ├── Coder
     └── ComputerTerminal

双循环设计：
  Task Ledger    = 拆解任务、分配子任务
  Progress Ledger = 追踪进展、self-reflection、重新规划

AutoGen Core = Actor 模型（Python / .NET，可跨进程）
AgentChat    = 高层 API（GroupChat + MagenticOneGroupChat）
```

> **关键洞察**：Magentic-One 的"双循环"(Task Ledger + Progress Ledger) 正是你要解决的问题——它在 Orchestrator 内部实现了"拆任务→追进展→发现矛盾→重新规划"的闭环。

#### CrewAI
```
Crew
  ├── Agent: "Researcher" (role, goal, backstory, tools)
  ├── Agent: "Writer" (role, goal, backstory, tools)
  └── Agent: "Reviewer" (role, goal, backstory, tools)
  
执行模式：sequential | parallel | hierarchical (manager agent)
Flows = 事件驱动工作流（状态传递 + 条件分支）
```

#### LangGraph 1.0
```
StateGraph
  ├── Node: research   → (state) → state
  ├── Node: analyze    → (state) → state
  ├── Node: review     → (state) → state
  └── Edges: conditional routing between nodes

特点：
  ✅ 显式状态管理（reducer-driven schemas）
  ✅ Checkpointing（持久化 + time-travel + 断点续跑）
  ✅ interrupt_before / interrupt_after（人类门控）
  ✅ 并行 fan-out + fan-in
  ❌ Python-only
  ❌ 需要预定义 graph topology
```

---

## 2. 你的场景分析：哪些模式适用

### 你的实际场景
```
你有 3-5 个独立 Codex 实例（不同进程、不同机器可能），
它们在不同的 GitHub Issue 上推进不同的子任务，
通过 Git commit + Issue comment 产出工作成果，
你需要：
  1. 知道每个 lane 的进展
  2. 发现 lane 间的矛盾
  3. 在关键 checkpoint 做 approve/redirect
  4. 不用一直盯着
```

### 框架适用性评估

| 框架模式 | 适用度 | 原因 |
|----------|--------|------|
| Claude Agent Teams (in-process) | **20%** | 你的 lane 是独立进程甚至独立机器，不适合 in-process 模式 |
| Google A2A Task Protocol | **85%** | Task lifecycle + streaming status + Agent Card 完美匹配你的需求 |
| OpenClaw sessions_send | **70%** | 通信层已有，但缺编排逻辑 |
| Magentic-One 双循环 | **90%** | Task Ledger + Progress Ledger 就是你需要的 |
| CrewAI Hierarchical | **50%** | Manager agent 模式对，但过于面向 LLM-in-the-loop |
| LangGraph StateGraph | **75%** | Checkpointing + 人类门控很好，但预定义 topology 过于刚性 |

### 结论：最佳组合

**Magentic-One 的双循环模式 + Google A2A 的 Task/Agent Card 协议 + OpenClaw 的通信层 + LangGraph 的 Checkpointing 理念**

各取所需：
- 从 Magentic-One 拿：Task Ledger（任务拆解与分配）+ Progress Ledger（进展追踪与重新规划）
- 从 A2A 拿：Task lifecycle state machine（submitted/working/input-required/completed/failed/canceled） + Agent Card 自描述
- 从 OpenClaw 拿：`sessions_send/spawn/status` 作为通信传输层（已有）
- 从 LangGraph 拿：Checkpoint + 状态持久化 + `interrupt_before` 门控模式

**不需要的**：
- Claude Agent Teams 的 in-process 模式（你的 lane 是跨进程的）
- CrewAI 的 role-based 抽象（你的 lane 已经有明确分工）
- AutoGen 的 Actor runtime（引入依赖过重、你已有 EventBus）

---

## 3. 基于当前代码库的实现架构

### 3.1 代码库已有资产清单

```
已有组件（可直接复用）:
  ├── OpenClawAdapter         → 93L   ✅ sessions_send/spawn/status
  ├── CcExecutor              → 1558L ✅ dispatch/parallel/team/conversation
  ├── CcNativeExecutor        → 618L  ✅ ReAct loop + MCP 工具调用
  ├── AgentDispatcher         → 248L  ✅ ContextPackage + LLM scaffold 生成
  ├── TeamSpec / RoleSpec     → 198L  ✅ 团队定义 + 确定性 team_id
  ├── TeamScorecardStore      → 254L  ✅ SQLite 记分卡 + 排名
  ├── TeamPolicy              → 125L  ✅ 基于记分卡的团队选择 + 探索
  ├── EventBus                → —     ✅ TraceEvent emit/subscribe
  ├── MemoryManager           → —     ✅ episodic stage_and_promote
  ├── EvoMapObserver          → —     ✅ Signal record
  ├── ApprovalQueue           → 329L  ✅ 审批队列
  ├── openclaw_orch_agent.py  → 24K   ✅ agent 对齐 + 健康检查
  ├── openclaw_guardian_run.py → 35K   ✅ 巡查 + incident
  └── PolicyEngine            → —     ✅ 策略检查

需要新建:
  ├── LaneRegistry            → Lane 注册/注销/心跳
  ├── TaskLedger              → 任务拆解与分配
  ├── ProgressLedger          → 进展追踪与重新规划
  ├── CoherenceChecker        → 跨 lane 矛盾检测
  ├── DigestGenerator         → 进展摘要生成
  └── OrchestratorGraph       → 编排状态机
```

### 3.2 架构设计

```
                           ┌────────────────────────────────────┐
                           │     你（人类）                        │
                           │   只在 checkpoint 时被通知             │
                           └──────────┬─────────────────────────┘
                                      │ approve / redirect
                                      ▼
                    ┌────────────────────────────────────────────┐
                    │              OrchestratorGraph              │
                    │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
                    │  │TaskLedger│  │Progress  │  │Coherence │  │
                    │  │          │  │Ledger    │  │Checker   │  │
                    │  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
                    │       │             │             │         │
                    │  ┌────┴─────────────┴─────────────┴────┐   │
                    │  │         LaneRegistry                │   │
                    │  │  lane_id | purpose | status | last  │   │
                    │  └────┬──────────┬──────────┬──────────┘   │
                    │       │          │          │              │
                    └───────┼──────────┼──────────┼──────────────┘
                            │          │          │
                   ┌────────┴──┐ ┌─────┴────┐ ┌──┴────────┐
                   │ KB Codex  │ │ Issue    │ │ Main Repo │
                   │ Lane      │ │ Graph   │ │ Codex     │
                   │ (OpenClaw │ │ Lane    │ │ Lane      │
                   │  session) │ │         │ │           │
                   └───────────┘ └─────────┘ └───────────┘
                        ↕              ↕             ↕
                    sessions_send/status (via OpenClawAdapter)
                    or git/gh API (for non-OpenClaw lanes)
```

### 3.3 核心数据模型

```python
# 新文件: chatgptrest/kernel/lane.py

@dataclass
class LaneSpec:
    """A2A-style Agent Card 的内部表示"""
    lane_id: str                    # 唯一标识
    purpose: str                    # "KB graph pilot", "issue-domain canonical"
    agent_type: str                 # "openclaw_session" | "codex_cli" | "cc_native"
    capabilities: list[str]         # ["code_review", "kb_write", "issue_triage"]
    # 通信 channel 配置
    openclaw_session_key: str = ""  # OpenClaw session key (if applicable)
    github_issue: int = 0          # Tracked via issue comments
    git_branch: str = ""           # Tracked via git log

@dataclass  
class LaneState:
    """Runtime state of a lane (persisted in SQLite)"""
    lane_id: str
    status: str                     # A2A Task States: "idle" | "working" | "input-required" | "completed" | "failed"
    last_heartbeat: float           # Unix timestamp
    last_progress_summary: str      # 最近一次进展摘要
    last_artifact_hash: str         # 最近产出的 hash（用于 diff 检测）
    checkpoint_pending: bool        # 是否有待 approve 的 checkpoint
    created_at: float
    updated_at: float

@dataclass
class TaskAssignment:
    """Task Ledger entry — Magentic-One 模式"""
    task_id: str
    lane_id: str
    description: str
    expected_output: str            # output contract
    dependencies: list[str]         # 依赖的其他 task_id
    status: str                     # "pending" | "assigned" | "in_progress" | "review" | "done" | "blocked"
    priority: int
    gate_type: str                  # "auto" | "human_approve" | "peer_review"
    created_at: float
    completed_at: float = 0.0

@dataclass
class ProgressEntry:
    """Progress Ledger entry — 每次拉取的增量"""
    lane_id: str
    timestamp: float
    source: str                     # "openclaw_status" | "git_log" | "gh_issue_comment" | "heartbeat"
    summary: str                    # 结构化摘要
    raw_data: str                   # 原始数据（JSON）
    delta_from_previous: str        # 与上次的 diff
```

### 3.4 编排状态机 (OrchestratorGraph)

```
采用 LangGraph 风格的显式状态机，但不依赖 LangGraph 库：

     ┌─────────────┐
     │   PLAN      │ ← TaskLedger 拆解任务 + 分配 lane
     └──────┬──────┘
            ▼
     ┌─────────────┐
     │   DISPATCH   │ ← 通过 OpenClaw/CC/gh 分派任务
     └──────┬──────┘
            ▼
     ┌─────────────┐     ┌──────────────┐
     │   MONITOR   │────→│ CHECK_COHER  │ 检测矛盾
     └──────┬──────┘     └──────┬───────┘
            │                    │
            ▼                    ▼
     ┌─────────────┐     ┌──────────────┐
     │   GATE      │←────│ REPLAN       │ 发现矛盾→重新规划
     └──────┬──────┘     └──────────────┘
            │
     ┌──────┴──────┐
     │human approve│ ← interrupt_before 语义
     └──────┬──────┘
            ▼
     ┌─────────────┐
     │   DIGEST    │ ← 生成人类可读摘要
     └──────┬──────┘
            ▼
     ┌─────────────┐
     │   DONE      │
     └─────────────┘

每个状态转移都持久化到 SQLite（checkpointing）
```

### 3.5 Progress Collector 策略

```python
# 三种采集通道，定时轮询：

class ProgressCollector:
    """定时采集各 lane 进展"""
    
    async def poll_openclaw_lane(self, lane: LaneSpec) -> ProgressEntry:
        """通过 session_status 查 OpenClaw session"""
        adapter = OpenClawAdapter(self.mcp_url)
        status = await adapter.session_status(lane.openclaw_session_key)
        return ProgressEntry(...)
    
    async def poll_git_lane(self, lane: LaneSpec) -> ProgressEntry:
        """通过 git log 查最近提交"""
        result = subprocess.run(
            ["git", "log", "--oneline", "-5", f"--since='{last_poll}'", lane.git_branch],
            ...
        )
        return ProgressEntry(...)
    
    async def poll_github_issue(self, lane: LaneSpec) -> ProgressEntry:
        """通过 gh api 查 issue 新 comments"""
        result = subprocess.run(
            ["gh", "api", f"repos/owner/repo/issues/{lane.github_issue}/comments",
             "--jq", f'[.[] | select(.created_at > "{last_poll}")] | length'],
            ...
        )
        return ProgressEntry(...)
```

### 3.6 Gate / Checkpoint 定义

```yaml
# config/orchestrator_gates.yaml

gates:
  - name: scope_change
    trigger: "lane 试图修改不在其 purpose 范围内的文件"
    action: human_approve
    notification: feishu
    
  - name: cross_lane_conflict
    trigger: "CoherenceChecker 检测到两个 lane 对同一文件有矛盾修改"
    action: human_approve
    notification: feishu + github_issue_comment
    
  - name: merge_request
    trigger: "lane 请求 merge 到 master"
    action: human_approve  # 或 peer_review（另一个 lane 审核）
    notification: feishu
    
  - name: milestone_completed
    trigger: "lane 声明完成了一个 phase 的全部 tasks"
    action: auto_continue  # 自动继续，但通知你
    notification: feishu_digest
    
  - name: cost_threshold
    trigger: "lane 的累计 token 消耗超过阈值"
    action: human_approve
    notification: feishu
```

---

## 4. 文件级实现计划

### 新建文件

| 文件 | 用途 | 行数估计 | 优先级 |
|------|------|----------|--------|
| `chatgptrest/kernel/lane.py` | LaneSpec, LaneState, LaneRegistry (SQLite) | ~300 | P0 |
| `chatgptrest/kernel/task_ledger.py` | TaskAssignment CRUD + 依赖解析 | ~250 | P0 |
| `chatgptrest/kernel/progress_ledger.py` | ProgressEntry CRUD + ProgressCollector | ~350 | P0 |
| `chatgptrest/kernel/orchestrator_graph.py` | 编排状态机 + checkpoint 持久化 | ~500 | P1 |
| `chatgptrest/kernel/coherence_checker.py` | 跨 lane diff 检测 + 矛盾标记 | ~200 | P1 |
| `chatgptrest/kernel/digest_generator.py` | LLM 摘要生成 (复用 CcNativeExecutor) | ~150 | P1 |
| `chatgptrest/api/routes_orchestrator.py` | REST API for orchestrator (status/gate/approve) | ~300 | P2 |
| `config/orchestrator_gates.yaml` | Gate 定义配置 | ~50 | P0 |
| `tests/test_lane_registry.py` | LaneRegistry 单元测试 | ~150 | P0 |
| `tests/test_task_ledger.py` | TaskLedger 单元测试 | ~150 | P0 |
| `tests/test_progress_ledger.py` | ProgressLedger 单元测试 | ~150 | P1 |
| `tests/test_orchestrator_graph.py` | 编排状态机测试 | ~200 | P1 |

### 修改文件

| 文件 | 修改内容 | 影响范围 |
|------|----------|----------|
| `chatgptrest/integrations/openclaw_adapter.py` | 添加 `poll_session_progress()` 方法 | 低，新增方法 |
| `chatgptrest/kernel/event_bus.py` | 跨进程事件桥接（可选：写入共享 DB/文件） | 中 |
| `chatgptrest/api/app.py` | 注册 orchestrator routes | 低 |
| `ops/openclaw_orch_agent.py` | 集成 LaneRegistry + ProgressCollector | 中 |

### 总工作量估计

```
新代码：~2600 行
修改代码：~200 行
测试代码：~650 行
配置/文档：~200 行
────────────────────
总计：~3650 行

实现周期：7-10 天（如果你一个人盯一个 Codex 做）
```

---

## 5. 实现分期

### Phase 1: 基础层 (Day 1-3) — "让 main agent 知道有谁在跑"

```
✅ LaneRegistry (SQLite: lane_specs + lane_states)
   - register_lane() / unregister_lane()
   - update_heartbeat()
   - get_active_lanes() / get_lane_state()
   
✅ TaskLedger (SQLite: task_assignments)
   - create_task() / assign_to_lane()
   - update_status() / get_tasks_for_lane()
   - resolve_dependencies()

✅ ProgressLedger + ProgressCollector
   - record_progress() / get_latest_progress()
   - poll_openclaw / poll_git / poll_github_issue

✅ 单元测试

交付物：main agent 可以注册 lane → 分派任务 → 定时拉取进展
```

### Phase 2: 智能层 (Day 4-6) — "让 main agent 能判断"

```
✅ OrchestratorGraph (状态机 + checkpoint 持久化)
   - PLAN → DISPATCH → MONITOR → GATE → DIGEST
   - checkpoint_save() / checkpoint_load()

✅ CoherenceChecker
   - compare_lane_outputs() — git diff 比较两个 lane 最新产出
   - detect_file_conflicts() — 两个 lane 改了同一个文件
   - semantic_conflict_check() — LLM 判断语义矛盾

✅ Gate 配置加载 + 评估
   - load_gates() / evaluate_gate()
   - trigger_human_approval()

✅ 集成测试

交付物：main agent 自动发现矛盾 → 只在需要你决策时通知你
```

### Phase 3: 体验层 (Day 7-10) — "让你真正不用盯着"

```
✅ DigestGenerator
   - generate_digest() — 把 N 个 lane 的 progress 聚合成 1 段文字
   - 复用 CcNativeExecutor / Anthropic API

✅ 推送通道
   - 飞书卡片（复用 feishu_handler.py）
   - GitHub Issue comment（已有 gh CLI）
   - CLI dashboard（可选）

✅ REST API
   - GET /v1/orchestrator/status — 全局状态
   - GET /v1/orchestrator/lanes — lane 列表
   - POST /v1/orchestrator/gates/{gate_id}/approve — 人类审批
   - GET /v1/orchestrator/digest — 最新摘要

✅ orch_agent.py 集成
   - 把 OrchestratorGraph 逻辑嵌入 openclaw_orch_agent.py
   - 作为常驻服务运行

✅ 端到端测试 + 文档

交付物：你只需要看飞书/GitHub 通知 → 在 REST 或 CLI 里 approve → 继续做别的事
```

---

## 6. 与行业框架的对齐映射

```
ChatgptREST 概念              → 行业框架对应
─────────────────────────────────────────────
LaneSpec                     → A2A Agent Card
LaneState.status             → A2A Task State (submitted/working/input-required/completed/failed/canceled)
TaskLedger                   → Magentic-One Task Ledger
ProgressLedger               → Magentic-One Progress Ledger
OrchestratorGraph            → LangGraph StateGraph (但不依赖 LangGraph)
Gate                         → LangGraph interrupt_before
CoherenceChecker             → AutoGen GroupChat "reflection" step
DigestGenerator              → CrewAI Flow "summarize" task
OpenClawAdapter.sessions_send → A2A tasks/send
ProgressCollector            → A2A tasks/get + SSE subscription
TeamScorecard                → (独有——其他框架无学习机制)
TeamPolicy + exploration     → (独有——MAB 探索)
```

---

## 7. 验证计划

### 自动化测试
```bash
# Phase 1
.venv/bin/pytest tests/test_lane_registry.py -v
.venv/bin/pytest tests/test_task_ledger.py -v
.venv/bin/pytest tests/test_progress_ledger.py -v

# Phase 2
.venv/bin/pytest tests/test_orchestrator_graph.py -v

# 全量回归
.venv/bin/pytest -q
```

### 集成验证 (Phase 3)
```bash
# 启动 API
PYTHONPATH=. .venv/bin/python -m uvicorn chatgptrest.api.app:create_app --factory --port 18711

# 注册一个 lane
curl -s http://127.0.0.1:18711/v1/orchestrator/lanes -X POST -H "Content-Type: application/json" \
  -d '{"lane_id": "kb_codex", "purpose": "KB graph pilot", "agent_type": "codex_cli"}'

# 查看状态
curl -s http://127.0.0.1:18711/v1/orchestrator/status

# 获取 digest
curl -s http://127.0.0.1:18711/v1/orchestrator/digest
```

### 人工验证
- 同时开 2 个 Codex lane，让 OrchestratorGraph 把进展推到飞书
- 故意让两个 lane 改同一个文件，验证 CoherenceChecker 触发 gate
- 在 gate 触发后通过 REST API approve，验证 lane 继续执行

---

## 8. 设计决策记录

| 决策 | 选择 | 原因 | 备选 |
|------|------|------|------|
| 状态机实现 | 自写 (不依赖 LangGraph) | 避免引入重依赖；你的状态转移简单 | LangGraph StateGraph |
| 持久化 | SQLite (复用 jobdb.sqlite3) | 单机单用户，SQLite 够用 | Redis / PostgreSQL |
| 跨 lane 通信 | OpenClaw sessions_send + gh CLI | 已有，不需要新基建 | A2A JSON-RPC server |
| 矛盾检测 | git diff + LLM semantic check | 文件级冲突用 diff，语义矛盾用 LLM | 纯 LLM（贵且慢） |
| 人类通知 | 飞书 + GitHub Issue comment | 你已有两个渠道 | Slack / email |
| 学习机制 | 复用 TeamScorecardStore | 已有且经过测试 | 新建 LaneScorecard |
| A2A 兼容 | LaneSpec 可序列化为 Agent Card | 未来可对外暴露 A2A 端点 | 不兼容 |
