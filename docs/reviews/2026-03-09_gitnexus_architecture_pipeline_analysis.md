# GitNexus Architecture & Pipeline Integrity Analysis

**Date**: 2026-03-09
**Tool**: GitNexus AST Knowledge Graph (KuzuDB)
**Indexed commit**: `96e918e` (8672 nodes, 26262 edges, 612 communities, 300 processes)

---

## 1. Hub Centrality — System Backbone

These are the highest-connectivity nodes. Changes here have the biggest blast radius.

| Rank | Symbol | File | Edges | Role |
|------|--------|------|-------|------|
| 1 | `execute` | `chatgptrest/workflows/__init__.py` | 447 | **Workflow engine** — called by 30+ ops scripts |
| 2 | `connect` | `chatgptrest/core/db.py` | 240 | **Core DB** — shared SQLite connection |
| 3 | `create_app` | `chatgptrest/api/app.py` | 177 | **API factory** — Flask/Quart app assembly |
| 4 | `_run_once` | `chatgptrest/worker/worker.py` | 126 | **Worker loop** — job execution engine (L2669-5022, 2353 lines!) |
| 5 | `get_advisor_runtime` | `chatgptrest/advisor/runtime.py` | 96 | **Runtime bootstrap** — bridges all subsystems |
| 6 | `main` | `ops/maint_daemon.py` | 100 | **Ops daemon** — SRE automation |

> [!IMPORTANT]
> `_run_once` is a **2353-line function** (L2669-5022). This is the single biggest code smell in the entire codebase. It handles job dispatch for all providers (ChatGPT, Gemini, Qwen), all phases (send, wait, export), all repair workflows, and all error handling in one monolithic function. Any bug here affects the entire job pipeline.

### Dual Database Pattern

Two separate `connect` functions exist:
- `chatgptrest/core/db.py:connect` (240 edges) — main application DB
- `chatgptrest/evomap/knowledge/db.py:connect` (86 edges) — EvoMap knowledge DB

These databases are **independently managed** with no shared transaction coordination.

---

## 2. Community Detection — Functional Areas

| Community | Members | Assessment |
|-----------|---------|------------|
| **Tests** | 2534 | Dominant — tests outnumber production code 3:1 |
| **Ops** | 464 | Large ops layer — `maint_daemon`, `guardian`, `monitor`, `export_issue_views` |
| **Gemini** | 274 | Provider layer — Gemini web driver |
| **Executors** | 268 | Job execution — ChatGPT/Gemini/Qwen/Repair executors |
| **Knowledge** | 260 | KB + EvoMap knowledge pipeline |
| **Api** | 177 | HTTP routes — REST contract |
| **Kernel** | 164 | Core abstractions — `EventBus`, `MemoryManager`, `PolicyEngine`, `LLMConnector` |
| **Advisor** | 117 | Advisor/funnel/routing layer |
| **MCP** | 115 | MCP server — external tool surface |
| **Cognitive** | 69 | `ContextService`, `context_resolve`, `graph_query` — OpenClaw bridge |
| **Workflows** | 42 | Workflow engine (only 42 members for 447-edge hub!) |

> [!WARNING]
> **Cognitive community has only 69 members** despite being the stated centerpiece of the OpenClaw/OpenMind integration. The entire cognitive API surface (`context_resolve`, `graph_query`, `knowledge_ingest`, `telemetry_ingest`, `policy_hints`) is smaller than the test infrastructure for any single feature.

---

## 3. Process Flow Analysis — Pipeline Integrity

### 3.1 All processes are short (≤8 steps)

The longest detected execution flows are only **8 steps**:
- `Cancel_route → _now` (8 steps)
- `Run → Init_db` (8 steps)
- `Resolve → _conn` (8 steps)

For comparison, a real end-to-end business flow like "user request → advisor routing → model dispatch → answer collection → memory capture → KB writeback → EvoMap signal" would need **15+ steps**. The graph shows this chain **does not exist as a connected process**.

### 3.2 The `get_advisor_runtime` bridge

`get_advisor_runtime` (96 edges) participates in **40 processes**, all 4 steps long:

```
Entry → Route → get_advisor_runtime → Terminal
```

Where:
- **Entry**: `advisor_ask`, `health`, `cc_dispatch_team`, `dashboard`, `evomap_signals`, `evomap_stats`, `cc_dispatch`, `cc_dispatch_stream`, `cc_dispatch_conversation`, `get_insights`
- **Terminal**: `LLMConfig`, `Resolve_evomap_db_path`, `EvoMapObserver`, `LLMConnector`

This means `get_advisor_runtime` is the **sole bridge** connecting all functional areas. It instantiates: `AdvisorRuntime`, `AdvisorAPI`, `FeishuHandler`, `KBHub`, `KBWritebackService`, `ArtifactRegistry`, `MemoryManager`, `PolicyEngine`, `EventBus`, `EffectsOutbox`, `LLMConnector`, `McpLlmBridge`, `CcExecutor`, `CcNativeExecutor`, `EvoMapObserver`, `KBScorer`, `GateAutoTuner`, `CircuitBreaker`.

> [!CAUTION]
> **Single point of initialization**: If `get_advisor_runtime` fails (550-line function, L225-774), the entire system is down. There is no partial startup, no degraded mode, no circuit breaker on the bootstrap path itself — only on things it bootstraps.

### 3.3 Disconnections: `_run_once` ↔ `get_advisor_runtime`

The worker's `_run_once` (job execution) and the advisor's `get_advisor_runtime` (cognitive pipeline) share **zero processes**. They connect only through:
1. HTTP routes (worker sends jobs → executor calls API endpoint)
2. The shared `execute` function for SQL operations

This means the worker and the cognitive layer are **architecturally decoupled** — which is correct for fault isolation but means there is no graph-traceable path from "user sends a job" to "cognitive context is resolved".

---

## 4. Dead Code & Broken Chains

### 4.1 Uncalled Functions (non-test, non-private)

| Function | File | Concern |
|----------|------|---------|
| `should_continue_after_a` | `chatgptrest/advisor/funnel_graph.py` | 🔴 **Funnel stage gates never called** — D2 need漏斗's core decision logic is dead code |
| `should_continue_after_b` | `chatgptrest/advisor/funnel_graph.py` | 🔴 Same — stage B gate |
| `handle_signal` | `chatgptrest/advisor/feishu_ws_gateway.py` | 🟡 Feishu WebSocket signal handler — unused |
| `mark` | `chatgptrest/advisor/feishu_handler.py` | 🟡 Message mark — Feishu integration gap |
| `seen` | `chatgptrest/advisor/feishu_handler.py` | 🟡 Message seen — Feishu integration gap |
| `to_dict` | `chatgptrest/advisor/__init__.py` | 🟡 Serialization helper |
| `get` / `put` | `chatgptrest/advisor/advisor_api.py` | 🟡 Advisor API CRUD — never called from production code |
| `gemini_web_ask` et al. | `chatgpt_web_mcp/providers/gemini/ask.py` | ⚪ MCP tool functions — called via MCP dispatch, not direct calls |
| `qwen_web_ask` et al. | `chatgpt_web_mcp/providers/qwen_web.py` | ⚪ Same — MCP dispatch |

> [!CAUTION]
> **`should_continue_after_a` and `should_continue_after_b`** are the funnel's stage-gate decision functions — the core logic for deciding whether a requirement should progress from one stage to the next. They are **never called by any code in the repository**. This means the D2 需求漏斗 pipeline has decision logic that was built but **never wired into the execution chain**.

### 4.2 MCP false positives

Functions like `gemini_web_ask`, `qwen_web_ask`, `gemini_web_deep_research` appear uncalled because they are invoked via MCP's dynamic dispatch (`@mcp.tool()`), not through direct Python calls. GitNexus cannot trace MCP decorator-based dispatch. These are **not actual dead code** — they are reachable through the MCP protocol.

---

## 5. Cross-Domain Connectivity Matrix

Based on GitNexus edge analysis, here is how the major subsystems connect:

```
┌─────────────┐     HTTP      ┌──────────────┐     SQL      ┌───────────┐
│   Worker     │─────routes───▶│  API Layer   │────execute──▶│  Core DB  │
│ (_run_once)  │              │ (create_app) │              │ (connect) │
└──────┬───────┘              └──────┬───────┘              └───────────┘
       │                             │
       │ executor dispatch           │ get_advisor_runtime
       ▼                             ▼
┌──────────────┐              ┌──────────────┐
│  Executors   │              │   Advisor     │──▶ LLMConnector
│ (Gemini/     │              │   Runtime     │──▶ MemoryManager
│  ChatGPT/    │              │              │──▶ PolicyEngine
│  Repair)     │              │              │──▶ EventBus
└──────────────┘              │              │──▶ KBHub
                              │              │──▶ EvoMapObserver
                              └──────┬───────┘
                                     │
                          ┌──────────┼──────────┐
                          ▼          ▼          ▼
                    ┌──────────┐ ┌────────┐ ┌─────────┐
                    │ Cognitive│ │  KB    │ │ EvoMap  │
                    │ Service  │ │ Hub    │ │ Observer│
                    └──────────┘ └────────┘ └─────────┘
                         ▲                       │
                         │                       ▼
                    ┌──────────┐           ┌──────────────┐
                    │ OpenClaw │           │ Promotion    │
                    │ Plugins  │           │ Engine       │
                    │ (TS)     │           │ (not wired)  │
                    └──────────┘           └──────────────┘

  DISCONNECTED:
  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
  │ Guardian    │     │ Issue Graph  │     │ Maint Daemon │
  │ (Python)    │     │ (new)        │     │ (standalone) │
  └──────┬──────┘     └──────┬───────┘     └──────┬───────┘
         │                   │                     │
         └───────── SQL/HTTP ┼─────────────────────┘
                   (via execute + API calls, no shared processes)
```

### Key Disconnections

| From | To | Connection Type | Gap |
|------|----|----------------|-----|
| Worker → Cognitive | HTTP only | No code-level process chain; worker dispatches executors which may call cognitive API |
| Guardian → Agent Topology | None | Guardian is a standalone Python script, not routed through OpenClaw agents |
| EvoMap Observer → Promotion Engine | None | Observer collects signals but `PromotionEngine` has **no incoming calls from production code** |
| Funnel Graph → Advisor | Dead code | `should_continue_after_a/b` gates never called — funnel stages don't connect |
| Issue Graph → Guardian | Weak | `_normalize_text` in issue_graph has 1 process (4 steps) — minimal integration |
| Feishu WS Gateway → Advisor | Dead | `handle_signal` never called — WebSocket path inactive |

---

## 6. Architecture Verdict

### ✅ What's Structurally Sound

1. **Core job pipeline** (`_run_once` → executors → DB) is well-connected with 28+ test callers
2. **API layer** (`create_app`) properly composes all route modules
3. **Advisory runtime** (`get_advisor_runtime`) correctly bootstraps all kernel components
4. **Test coverage** is extensive — 2534 test-community members

### 🔴 What's Broken or Disconnected

1. **Funnel stage gates are dead code** — D2 需求漏斗 core logic (`should_continue_after_a/b`) never invoked
2. **EvoMap promotion pipeline is not wired** — observer collects but promotion engine unreachable from production
3. **Guardian runs outside the system** — parallel health management that bypasses agent topology
4. **No end-to-end execution chain** — longest process is 8 steps; real business flows need 15+
5. **`_run_once` is 2353 lines** — single function handling all job types, phases, and errors

### 🟡 Architectural Risks

1. **`get_advisor_runtime` is a god-function for initialization** — single point of failure for the entire cognitive layer, 550 lines
2. **Dual database with no coordination** — `core/db.py` and `evomap/knowledge/db.py` operate independently
3. **Feishu integration is partially dead** — `mark`, `seen`, `handle_signal` never called
4. **Issue graph community label is "Cluster_511"** — GitNexus couldn't determine its functional area, suggesting it's isolated from other components
