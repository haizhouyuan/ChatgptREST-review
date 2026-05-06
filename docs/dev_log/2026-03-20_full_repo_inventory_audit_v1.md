# 2026-03-20 Full Repo Inventory Audit v1

## Scope

This audit inventories the entire current `ChatgptREST` repository as a living
system, not just as a Python package tree.

The audit covers:

1. top-level code domains
2. API and service surfaces
3. execution stacks
4. cognitive / KB / graph substrate
5. OpenClaw integration layer
6. Finbot vertical line
7. ops / automation estate
8. test estate
9. durable state and live SQLite footprint
10. overlap, drift, and likely legacy zones

Method:

- repository structure audit
- line-count / file-count inventory
- FastAPI route inventory
- targeted module header and runtime assembly audit
- live SQLite snapshot inspection on `2026-03-20`

This document explicitly separates four questions:

- does code exist
- is it wired into runtime
- is there live data behind it
- should it still be treated as strategic

That separation matters because this repository now contains multiple
overlapping generations of system design.

## Executive Summary

The current repository is not one system. It is at least **seven overlapping
systems plus a large ops estate**:

1. original REST job queue and worker system
2. merged ChatGPT/Gemini/Qwen web driver runtime
3. OpenMind advisor and cognitive substrate
4. controller / team / execution-collaboration stack
5. dashboard / run-ledger / investor surface
6. Finbot vertical product line
7. OpenClaw plugin and guard integration layer
8. large standalone ops / systemd / maintenance automation layer

The repo is large enough that structure is now the primary problem, not raw
functionality.

### High-level verdict

| Area | Code status | Runtime status | Live data status | Strategic verdict |
|---|---|---|---|---|
| REST job queue + worker | strong | active | active | still foundational |
| Embedded web driver (`chatgpt_web_mcp`) | strong | active | active | critical execution substrate |
| Advisor / OpenMind v3 | strong | active | active | main cognitive core inside this repo |
| Cognitive API (`/v2/context`, memory, graph, ingest) | medium-strong | active | active | real substrate, not a stub |
| Controller / team / collaborator stack | medium-strong | partially active | active but fragmented | important, not yet converged |
| `cc_sessiond` | medium | partially active | low live activity | legacy/transition execution branch |
| Dashboard control plane | medium | active | lightly populated | read-model / projection, not authoritative |
| Finbot | strong but monolithic | active | active | separate vertical line living inside repo |
| OpenClaw extensions | medium | active integration surface | active by usage pattern | important boundary layer |
| Ops / maintenance / review scripts | extremely large | active | active | effectively a second platform inside repo |
| Old `data/kb/*` local KB path | weak relative to new path | partially wired | tiny live footprint | likely legacy mirror |
| `state/knowledge_v2.sqlite3` | weak | not meaningfully active | empty | dead or abandoned migration stub |

### Core conclusion

The main structural risk is **parallel truth sources and parallel control
planes**, not lack of capabilities.

The most important overlaps are:

- multiple model-routing stacks
- multiple execution orchestration stacks
- multiple knowledge / graph stores
- multiple control-plane projections
- multiple API generations in one server

## Repository Size Snapshot

Current repository scale from direct scan on `2026-03-20`:

| Root | Files | Lines |
|---|---:|---:|
| `chatgptrest/` | 271 | 113635 |
| `chatgpt_web_mcp/` | 46 | 21970 |
| `ops/` | 166 | 38613 |
| `tests/` | 386 | 74668 |
| `openclaw_extensions/` | 17 | 1665 |
| `scripts/` | 404 | 17570 |

Interpretation:

- the main product code is large
- the ops estate is also large enough to be treated as a first-class subsystem
- tests are not symbolic; they are a major body of repo weight
- OpenClaw extensions are small but strategically important

## Top-Level Surface

The repo root contains all of these at once:

- core product packages: `chatgptrest/`, `chatgpt_web_mcp/`
- operations platform: `ops/`, `scripts/`, `ops/systemd/`
- integration assets: `openclaw_extensions/`
- runtime state: `state/`, `data/`, `artifacts/`, `logs/`
- knowledge corpus: `knowledge/`, `docs/`
- many historical or active worktrees under `.worktrees/`

This is not a library repo. It is a **combined application + execution runtime +
ops automation + evidence archive repo**.

## API and Service Surface

`chatgptrest/api/app.py` currently assembles one FastAPI app with multiple API
generations and product surfaces at once.

Current route count snapshot from app construction:

- `total_routes = 158`
- `jobs_v1 = 9`
- `advisor_v1 = 11`
- `issues_v1 = 14`
- `ops_v1 = 11`
- `cognitive_v2 = 6`
- `dashboard_v2 = 47`
- `advisor_v3 = 30`
- `agent_v3 = 5`
- `other = 25`

Interpretation:

- the server is not a single clean public API
- it is a combined compatibility shell for at least 4 eras:
  - original jobs API
  - v1 advisor / consult / ops family
  - v2 cognitive / dashboard / evomap family
  - v2 advisor v3 and v3 public agent facade

### Important API surfaces

1. `routes_jobs.py`
   The original durable job API. It is still the queueing backbone and remains
   tied to idempotency, file path normalization, prompt policy, and cancel
   semantics.

2. `routes_advisor_v3.py`
   The OpenMind v3 advisor entrypoint. It fronts the LangGraph-based advisor
   pipeline and controller engine.

3. `routes_agent_v3.py`
   The public session-first advisor-agent facade. It wraps controller-backed or
   job-backed execution into a client-friendly session contract.

4. `routes_cognitive.py`
   The cognitive substrate API. It exposes context resolution, graph query,
   knowledge ingest, memory capture, policy hints, and telemetry ingest.

5. `routes_dashboard.py`
   A large presentation surface over a separate dashboard control plane.

6. `routes_consult.py`
   An older but still real consultation and recall surface. It includes
   parallel multi-model consult submission, but its consultation store is
   in-memory and therefore weaker than the durable job systems.

## Major Code Domains

### 1. Original REST Job Queue Core

This is still the oldest and one of the most real parts of the repo.

Primary files:

- `chatgptrest/core/job_store.py`
- `chatgptrest/core/state_machine.py`
- `chatgptrest/worker/worker.py`
- `chatgptrest/api/routes_jobs.py`

What it does:

- durable job creation
- idempotency and collision handling
- send/wait split execution
- artifact and conversation export management
- cancel and retry semantics
- repair and SRE work submission

Current live snapshot from `state/jobdb.sqlite3`:

- jobs = `7924`
- controller_runs embedded here = `130`
- controller_work_items = `436`
- controller_artifacts = `63`
- advisor_runs = `201`
- advisor_steps = `507`
- job_events = `1481412`
- client_issues = `386`
- incidents = `6055`

Job status distribution:

- `completed = 6989`
- `error = 623`
- `canceled = 276`
- `in_progress = 15`
- `queued = 14`
- `needs_followup = 6`
- `cooldown = 1`

Top live job kinds:

- `repair.check = 3186`
- `chatgpt_web.ask = 2795`
- `gemini_web.ask = 1098`
- `repair.autofix = 539`
- `gemini_web.generate_image = 120`
- `qwen_web.ask = 37`

Verdict:

- active
- foundational
- now also carries non-job concerns like advisor/controller traces and issue data
- becoming a general operational truth store, not just a job DB

### 2. Embedded Web Driver Runtime

This lives mostly under `chatgpt_web_mcp/` and `chatgptrest/executors/`.

Primary files:

- `chatgpt_web_mcp/server.py`
- `chatgpt_web_mcp/_tools_impl.py`
- `chatgptrest/executors/chatgpt_web_mcp.py`
- `chatgptrest/executors/gemini_web_mcp.py`
- `chatgptrest/executors/qwen_web_mcp.py`

What it does:

- Playwright / CDP web execution
- ChatGPT Web ask flow
- Gemini web flow and attachments workaround
- Qwen web flow
- MCP tool registration
- rate limiting, locking, evidence capture, answer extraction

This is not a toy sidecar anymore. It is a production-significant execution
substrate merged directly into this repo.

Verdict:

- active
- strategically important
- one of the hardest real dependencies of the whole system

### 3. OpenMind Advisor Runtime

The advisor runtime is concentrated in:

- `chatgptrest/advisor/runtime.py`
- `chatgptrest/advisor/graph.py`
- `chatgptrest/api/routes_advisor_v3.py`
- `chatgptrest/api/routes_agent_v3.py`

What exists:

- LangGraph-based advisor pipeline
- runtime bundle assembly
- KB, memory, event bus, policy engine, writeback, EvoMap, routing, CC executor
- controller-backed execution handoff
- strategist / contract / prompt build / post-review pipeline on the agent facade

`advisor/runtime.py` is the assembly point that wires together:

- `LLMConnector`
- `ArtifactRegistry`
- `KBHub`
- `MemoryManager`
- `EventBus`
- `PolicyEngine`
- `EvoMapObserver`
- `KnowledgeDB`
- `RoutingFabric`
- `CcExecutor`
- `CcNativeExecutor`
- `KBWritebackService`
- `TeamControlPlane`
- team policy / scorecard support

Verdict:

- this is already the real cognitive core inside the repo
- not a sketch
- but runtime assembly density is high enough that dependency ownership is blurry

### 4. Cognitive Substrate

This layer is smaller than advisor runtime but real.

Primary files:

- `chatgptrest/cognitive/context_service.py`
- `chatgptrest/cognitive/memory_capture_service.py`
- `chatgptrest/cognitive/graph_service.py`
- `chatgptrest/cognitive/ingest_service.py`
- `chatgptrest/cognitive/policy_service.py`
- `chatgptrest/api/routes_cognitive.py`

What it does:

- memory capture and recall
- KB and graph-backed context resolution
- knowledge ingest
- policy hints
- telemetry ingest

This is important because it is a substrate layer distinct from the public ask
surfaces.

Verdict:

- active
- well worth preserving as a layer
- should not be confused with the user-facing advisor routes

### 5. Knowledge, Memory, and Graph Stack

This area was already audited in detail on `2026-03-19`, and the conclusion
still stands: the repo has a **real text-and-structure knowledge substrate**.

Current live data:

- `~/.openmind/memory.db`
  - `episodic = 2936`
  - `meta = 305`
  - `working = 156`
  - `staging = 4`
  - `semantic = 1`

- `~/.openmind/kb_search.db`
  - `kb_fts_meta = 938`
  - `kb_fts = 938`

- `~/.openmind/kb_registry.db`
  - `artifacts = 132`

- `~/.openmind/kb_vectors.db`
  - `vectors = 148`

- `~/.openmind/events.db`
  - `trace_events = 6528`

- `data/evomap_knowledge.db`
  - `documents = 7863`
  - `episodes = 47857`
  - `atoms = 99493`
  - `evidence = 81210`
  - `entities = 96`
  - `edges = 90611`

Interpretation:

- memory is active
- KB is active
- event bus is active
- EvoMap knowledge is large and active
- the weak point is still semantic consolidation in memory

Important caution:

there are **multiple knowledge-storage generations** in the repo:

- active `~/.openmind/*` stores
- active `data/evomap_knowledge.db`
- tiny old `data/kb/*` stores
- `state/knowledge_v2.sqlite3` which is empty
- `state/knowledge_v2/canonical.sqlite3` which is populated

This means the knowledge layer is real, but the storage topology is not yet
fully converged.

### 6. Controller / Team / Execution Collaboration Stack

This is one of the most structurally important but still not fully converged
areas.

Primary files:

- `chatgptrest/controller/engine.py`
- `chatgptrest/controller/store.py`
- `chatgptrest/controller/contracts.py`
- `chatgptrest/kernel/team_control_plane.py`
- `chatgptrest/kernel/team_types.py`
- `chatgptrest/kernel/cc_native.py`
- `chatgptrest/kernel/cc_executor.py`
- `chatgptrest/kernel/cc_sessiond/*`

What exists:

- durable controller runs, work items, checkpoints, artifacts
- team run and role run abstractions
- native CC-oriented dispatch
- a separate `cc_sessiond` session service subtree

Important live-state evidence:

- `state/controller_lanes.sqlite3` does not contain controller runs
  - it only contains `lanes = 4`, `lane_events = 6`
- the actual `controller_runs` and `controller_work_items` are currently stored
  in `state/jobdb.sqlite3`
- `state/cc_sessiond/registry.sqlite3` has only `sessions = 3`

Interpretation:

- controller is active
- team abstractions are real
- `cc_sessiond` exists but has low live centrality right now
- storage ownership in this area is fragmented

Verdict:

- strategically important
- not converged
- high risk of duplicate orchestration concepts

### 7. Dashboard / Run Ledger / Investor Surface

This is larger than it first appears.

Primary files:

- `chatgptrest/dashboard/control_plane.py`
- `chatgptrest/dashboard/service.py`
- `chatgptrest/api/routes_dashboard.py`

What it does:

- identity map across systems
- canonical event normalization
- run index and run timeline
- incident and component-health surfaces
- investor-specific dashboard pages
- graph and cognitive dashboard pages

Current live snapshot from `state/dashboard_control_plane.sqlite3`:

- `identity_map = 8`
- `canonical_events = 10`
- `run_index = 4`
- `run_timeline = 10`
- `cognitive_snapshot = 5`
- `component_health = 7`

Interpretation:

- the dashboard layer is live
- but it is very lightly populated relative to the underlying systems
- it is clearly a projection / read-model layer, not a primary truth store

Verdict:

- active
- useful
- should stay a projection layer, not become another control authority

### 8. Finbot Vertical Line

Finbot is still very much inside this repository.

Primary files:

- `chatgptrest/finbot.py`
- `chatgptrest/finbot_modules/*`
- `ops/openclaw_finbot.py`

What exists:

- a large finbot monolith
- some extracted helpers for claim logic, source scoring, market inference
- artifact-heavy dossier and theme-run flow
- OpenClaw-side operation wrappers for daily work and theme batch runs

Live evidence:

- many `artifacts/finbot/.../finagent.sqlite` run states exist
- daily and theme run systemd units exist under `ops/systemd/`

Verdict:

- active
- clearly a vertical product line, not just an experiment
- still monolithic enough to deserve its own boundary

### 9. OpenClaw Integration Layer

This repo contains explicit OpenClaw integration assets and runtime guards.

Primary files:

- `openclaw_extensions/README.md`
- `openclaw_extensions/openmind-advisor/*`
- `openclaw_extensions/openmind-memory/*`
- `openclaw_extensions/openmind-graph/*`
- `openclaw_extensions/openmind-telemetry/*`
- `ops/openclaw_runtime_guard.py`
- `ops/openclaw_guardian_run.py`
- `ops/openclaw_orch_agent.py`

What exists:

- OpenClaw plugin packages for advisor, memory, graph, telemetry
- runtime guard for workflow / telemetry / planning-runtime-pack integrity
- guardian and orch-side health / wake / probe tooling

Verdict:

- this repo is not merely callable by OpenClaw
- it contains an actual OpenClaw boundary layer
- that boundary layer is now part of the real system shape

### 10. Ops / Maintenance / Review Automation Estate

This is a major subsystem on its own.

Size:

- `166` files
- `38613` counted lines

Biggest files include:

- `maint_daemon.py = 5001`
- `verify_openclaw_openmind_stack.py = 1605`
- `chatgpt_agent_shell_v0.py = 1192`
- `openclaw_guardian_run.py = 1115`
- `openclaw_runtime_guard.py = 940`
- `sync_review_repo.py = 937`

Ops scope includes:

- service start/stop scripts
- monitoring
- self-heal and guardian flows
- review pack generation
- EvoMap build and ingestion utilities
- planning-review and execution-review cycle tooling
- systemd unit estate

The repo contains dozens of user services and timers:

- API
- driver
- MCP
- workers
- dashboard
- guardian
- OpenClaw runtime guard
- orch doctor
- viewer watchdog
- issue sync/export
- finbot daily work and theme timers

Verdict:

- extremely active
- useful
- large enough to distort architecture if left undocumented
- should be treated as an operational platform, not an accessory folder

## Monolith Hotspots

Largest Python hotspots inside `chatgptrest/`:

| File | Lines | Comment |
|---|---:|---|
| `worker/worker.py` | 5292 | original queue/runtime hotspot |
| `mcp/server.py` | 4046 | large adapter and background-wait surface |
| `finbot.py` | 3190 | vertical product monolith |
| `executors/gemini_web_mcp.py` | 2610 | heavy provider executor |
| `dashboard/control_plane.py` | 2211 | dense projection store logic |
| `executors/repair.py` | 2201 | repair/autofix plane |
| `dashboard/service.py` | 2187 | large dashboard service layer |
| `controller/engine.py` | 1843 | collaboration/execution controller |
| `api/routes_advisor_v3.py` | 1824 | OpenMind advisor entrypoint |
| `api/routes_agent_v3.py` | 1712 | public agent facade |
| `core/job_store.py` | 1605 | durable queue core |
| `core/issue_canonical.py` | 1596 | issue normalization plane |
| `cli.py` | 1567 | large CLI surface |
| `kernel/cc_executor.py` | 1561 | CC execution layer |
| `api/routes_advisor.py` | 1541 | older advisor surface |

Interpretation:

- complexity is not concentrated in one place
- there are several large monoliths, each corresponding to a different era or
  subsystem

## Test Estate

Current test snapshot:

- total test files = `383`
- total counted lines in `tests/` = `74668`

Largest tests include:

- `test_evomap_e2e.py = 1985`
- `test_dashboard_routes.py = 1506`
- `test_cognitive_api.py = 1384`
- `test_advisor_v3_end_to_end.py = 1202`
- `test_cc_executor.py = 1030`
- `test_worker_and_answer.py = 1029`
- `test_llm_connector.py = 940`
- `test_routing_scenarios.py = 856`
- `test_team_integration.py = 806`

Approximate category counts from file-name inventory:

- `build = 27`
- `gemini = 21`
- `execution = 17`
- `mcp = 15`
- `evomap = 12`
- `run = 10`
- `issue = 8`
- `openclaw = 7`
- `advisor = 7`
- `report = 7`
- `team = 6`
- `finbot = 3`

Interpretation:

- test coverage is substantial
- but coverage is distributed across many historical layers, which mirrors the
  structural sprawl

## Durable State Inventory

### Active or near-active stores

1. `state/jobdb.sqlite3`
   Real hot-path durable store. Most central runtime DB.

2. `~/.openmind/memory.db`
   Real memory substrate.

3. `~/.openmind/kb_search.db`
   Real KB search substrate.

4. `~/.openmind/kb_registry.db`
   Real KB artifact registry.

5. `~/.openmind/kb_vectors.db`
   Real vector store.

6. `~/.openmind/events.db`
   Real event bus store.

7. `data/evomap_knowledge.db`
   Real large knowledge graph / atom store.

8. `state/dashboard_control_plane.sqlite3`
   Real but lightly populated projection store.

### Partial, transitional, or low-centrality stores

1. `state/controller_lanes.sqlite3`
   Active but very small. Holds lane metadata, not main controller truth.

2. `state/cc_sessiond/registry.sqlite3`
   Exists and has data, but centrality is low.

3. `state/knowledge_v2/canonical.sqlite3`
   Populated canonical store with:
   - `canonical_objects = 8738`
   - `canonical_relations = 58237`
   - `object_sources = 9231`
   - `projection_targets = 9539`

   This looks real enough to matter, but it is not yet clearly the main
   knowledge truth source for the rest of the system.

### Empty, tiny, or likely legacy stores

1. `state/knowledge_v2.sqlite3`
   empty

2. `data/kb/kb.db`
   tiny: only `5` docs

3. `data/kb/kb_vec.db`
   tiny: only `5` vectors

4. `data/kb/kb_versions.db`
   tiny: only `5` versions

5. `data/kb/memory.db`
   empty

6. `data/kb/evomap.db`
   empty

7. `data/jobs.db`
   empty file

8. `data/chatgptrest.db`
   empty file

Interpretation:

- there is clear evidence of older storage layouts being superseded but not
  fully removed

## Parallel Stacks and Structural Conflicts

### 1. Multiple model-routing stacks

At least these routing layers exist:

- `kernel/routing/fabric.py`
- `kernel/model_router.py`
- `kernel/routing_engine.py`
- `kernel/llm_connector.py` selection path
- `advisor/preset_recommender.py` for front-door preset recommendations

Verdict:

- this is a real duplication zone
- there is still no single unquestioned model-routing authority

### 2. Multiple execution-orchestration stacks

Execution is spread across:

- original job queue + worker
- controller engine
- team control plane
- CC native execution
- `cc_sessiond`
- MCP surface background wait / auto-repair helper layer

Verdict:

- this is the highest architectural overlap area in the repo

### 3. Multiple control planes

There are at least these distinct control-like ledgers:

- `jobdb` core tables
- embedded controller tables inside `jobdb`
- lane DB
- dashboard control plane DB
- team control plane
- issue / incident ledgers

Verdict:

- several are valid
- but they do not yet form a clean hierarchy of truth vs projection

### 4. Multiple knowledge / graph stores

There are at least these:

- OpenMind memory
- OpenMind KB
- EvoMap knowledge DB
- canonical knowledge v2 store
- issue graph
- GitNexus external repo graph adapter surface

Verdict:

- the knowledge substrate is powerful
- but graph and knowledge ownership are not fully converged

### 5. API generation drift

The app exposes:

- v1 jobs and ops
- v1 advisor / consult
- v2 cognitive / dashboard / evomap
- v2 advisor v3
- v3 agent

Verdict:

- compatibility is valuable
- but API surface sprawl is now an architectural cost center

## Classification Matrix

### Clearly active and worth investing in

- REST job queue and worker
- embedded web driver stack
- OpenMind advisor runtime
- cognitive substrate
- KB / memory / event bus / EvoMap knowledge
- OpenClaw integration layer
- ops and monitoring estate
- Finbot as a distinct vertical

### Active but should be treated as projection or support layers

- dashboard control plane
- controller lanes DB
- investor dashboard views

### Important but not yet converged

- controller / team / CC native collaboration stack
- model routing
- canonical knowledge v2 store

### Likely legacy or transitional

- `cc_sessiond` as a primary future runtime
- old `data/kb/*` storage path
- `state/knowledge_v2.sqlite3`
- older advisor v1 consult-era patterns that remain in-memory or lightly durable

## Strategic Conclusions

### 1. This repo already contains the main OpenMind runtime

Not all of it should remain here forever, but the current reality is that
`ChatgptREST` is already:

- an execution substrate
- a cognitive runtime host
- a knowledge runtime host
- an OpenClaw integration host

### 2. The problem is convergence, not blank space

You do not primarily suffer from missing modules.
You primarily suffer from:

- too many partial authorities
- too many compatible-but-different runtime surfaces
- old storage paths that still exist
- execution concepts that were not retired after the next layer was built

### 3. The highest-payoff cleanup targets are obvious

If this repo is going to be rationalized, the first convergence work should
focus on:

1. model routing authority
2. execution control-plane authority
3. knowledge-store authority
4. API generation rationalization
5. monolith splitting at the worst hotspots

### 4. The repo has real assets worth preserving

The biggest mistake would be to treat this codebase as a pile of failed
experiments. It is not.

It contains several strong assets:

- durable queue / worker core
- real web execution substrate
- real KB / memory / graph substrate
- real advisor runtime
- real ops automation depth
- real OpenClaw integration

The problem is that these assets now coexist without a tight enough system
contract.

## Priority Findings

1. `state/jobdb.sqlite3` has become the de facto central operational truth
   store, absorbing jobs, controller runs, advisor runs, issues, and incidents.
   This is powerful, but also a sign of boundary compression.

2. The repo contains two strong execution branches at once:
   the original queue/worker branch and the controller/team/CC branch.
   `cc_sessiond` is present but no longer looks like the main center of gravity.

3. The knowledge layer is real and valuable, but storage topology is fragmented.
   `~/.openmind/*`, `data/evomap_knowledge.db`, and `state/knowledge_v2/canonical.sqlite3`
   all matter; old `data/kb/*` still exists as residue.

4. The dashboard plane is not authoritative. Its current live row counts are
   too small to treat it as the central truth source.

5. `ops/` is large enough to deserve architectural treatment. If ignored, it
   will continue to function as an unacknowledged second platform.

## Recommended Next Document

The next useful artifact should not be another inventory.

It should be a **convergence map** that explicitly chooses:

- which store is canonical for execution
- which store is canonical for knowledge
- which routing layer survives
- which API surfaces are strategic vs compatibility-only
- which subsystems should stay inside `ChatgptREST` vs move outward

