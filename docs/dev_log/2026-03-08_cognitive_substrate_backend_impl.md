# Cognitive Substrate Backend Implementation Walkthrough

Date: 2026-03-08
Branch: `codex/openmind-cognitive-substrate-impl-20260308`
Worktree: `/vol1/1000/projects/ChatgptREST-cognitive-substrate-impl-20260308`
Blueprint baseline: issue `#97`

## Goal

Implement the backend half of the OpenMind cognitive-substrate contract set proposed in `#97`, so OpenClaw can integrate against explicit APIs instead of importing OpenMind runtime internals.

Implemented API set:

- `POST /v2/context/resolve`
- `POST /v2/graph/query`
- `POST /v2/knowledge/ingest`
- `POST /v2/kb/upsert`
- `POST /v2/telemetry/ingest`
- `POST /v2/policy/hints`
- `GET /v2/cognitive/health`

## Design Rules Kept Intact

1. OpenClaw remains the execution shell.
2. OpenMind remains the cognition substrate.
3. No endpoint imports `get_advisor_runtime()` into another process; all new contracts stay HTTP-facing.
4. `context.resolve` stays hot-path and retrieval-only by default.
5. `repo_graph` is explicit federation, not fake in-process reimplementation.

## Step 1: Hot-path Context Resolve

Commit: `d31446a` `feat(cognitive): add hot-path context resolve api`

Files:

- `chatgptrest/cognitive/context_service.py`
- `chatgptrest/api/routes_cognitive.py`
- `chatgptrest/api/app.py`
- `tests/test_cognitive_api.py`

What was implemented:

- Added `ContextResolver` over the existing `ContextAssembler`.
- Added `POST /v2/context/resolve`.
- Added `GET /v2/cognitive/health`.
- Mounted the cognitive router in `create_app()`.

Important implementation choices:

- Wrapped `KBHub` with `_NoEmbedKBHub` so hot-path recall uses `auto_embed=False`.
- Temporarily disabled `GoogleWorkspace` and `ObsidianClient` inside `ContextResolver.resolve()` to keep the route local and deterministic.
- Preserved explicit degrade signaling for `repo_graph` in hot-path context.
- Added route-local auth/rate-limit behavior aligned with OpenMind v3:
  - `OPENMIND_API_KEY`
  - `OPENMIND_AUTH_MODE`
  - `OPENMIND_RATE_LIMIT`

Why:

- The blueprint calls for a cheap, prompt-safe context surface.
- The existing `ContextAssembler` already knew how to merge working memory, episodic memory, KB, and EvoMap.
- The risk was accidentally turning `context.resolve` into another hidden control plane by allowing external integrations or embeddings on every turn.

## Step 2: Graph Query Surface

Commit: `f9bd618` `feat(cognitive): add graph query api`

Files:

- `chatgptrest/cognitive/graph_service.py`
- `chatgptrest/api/routes_cognitive.py`
- `tests/test_cognitive_api.py`

What was implemented:

- Added `GraphQueryService`.
- Added `POST /v2/graph/query`.
- Exposed structured personal-graph retrieval:
  - atoms
  - episodes
  - documents
  - entities
  - evidence
  - edges
  - one-hop paths

How personal graph works:

- Uses EvoMap `retrieve()` to get high-signal atoms.
- Expands matched atoms to episode/document context.
- Loads related `entities` through direct SQLite query.
- Expands graph neighbors via `KnowledgeDB.get_edges_from()` / `get_edges_to()`.
- Returns normalized node/edge/path/evidence payloads.

How repo graph works right now:

- Introduced an explicit adapter seam instead of pretending repo graph exists in-process.
- `GitNexusCliAdapter` is opt-in:
  - `OPENMIND_ENABLE_GITNEXUS_CLI=1`
  - optional `OPENMIND_GITNEXUS_QUERY_CMD`
  - optional `OPENMIND_GITNEXUS_TIMEOUT_SECONDS`
- Default behavior is explicit degrade with `degraded_sources=["repo_graph"]`.

Why:

- The blueprint says GitNexus should be federated, not flattened into a fake local graph.
- This implementation gives us a real contract now, without smuggling MCP assumptions into runtime code.

## Step 3: Ingest, Telemetry, and Policy

Commit: `9546796` `feat(cognitive): add ingest telemetry and policy apis`

Files:

- `chatgptrest/cognitive/ingest_service.py`
- `chatgptrest/cognitive/telemetry_service.py`
- `chatgptrest/cognitive/policy_service.py`
- `chatgptrest/api/routes_cognitive.py`
- `tests/test_cognitive_api.py`

### `POST /v2/knowledge/ingest`

What it does:

- Runs content through `PolicyEngine.run_quality_gate()`.
- Writes accepted content through the existing `KBWritebackService`.
- Mirrors accepted content into EvoMap `KnowledgeDB` as:
  - document
  - episode
  - atom
  - evidence
- Optionally seeds named entities and links them to the primary atom.
- Emits `kb.writeback` to the shared `EventBus`.

Important implementation details:

- Added `POST /v2/kb/upsert` as an alias to the same write path.
- Output root is configurable by:
  - `OPENMIND_COGNITIVE_INGEST_DIR`
- Default output path:
  - `artifacts/cognitive_ingest/<para_bucket>/...`

Why:

- This keeps all durable knowledge writes inside existing KB governance.
- It also lets OpenClaw skill outputs land in both KB retrieval and graph retrieval without inventing a second ingest stack.

### `POST /v2/telemetry/ingest`

What it does:

- Normalizes OpenClaw execution events into canonical EvoMap signal names.
- Publishes them into the shared `EventBus`.
- Falls back to `observer.record_event()` if no bus is available.
- Mirrors selected outcome types into episodic memory:
  - `tool.completed`
  - `tool.failed`
  - `workflow.completed`
  - `workflow.failed`
  - `user.feedback`

Why:

- The blueprint’s EvoMap integration only matters if execution outcomes reach the substrate.
- Reusing `EventBus` means observer/memory/actuator behavior stays inside existing runtime wiring instead of duplicating telemetry persistence.

### `POST /v2/policy/hints`

What it does:

- Reuses `ContextResolver` to build evidence-aware hints.
- Runs pure advisor routing primitives:
  - `normalize`
  - `kb_probe`
  - `analyze_intent`
  - `compute_all_scores`
  - `select_route`
- Applies the same intent override semantics the advisor graph uses for:
  - `WRITE_REPORT -> report`
  - `DO_RESEARCH -> deep_research`
  - `BUILD_FEATURE -> funnel`
- Runs `PolicyEngine.run_quality_gate()` on the incoming request text.

Why:

- OpenClaw needs advisory routing and safety hints without giving execution authority away.
- This endpoint stays pure and side-effect-light. It does not call the full advisor graph and does not enqueue jobs.

## Testing

Primary regression suite used during implementation:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_cognitive_api.py \
  tests/test_routes_advisor_v3_security.py \
  tests/test_api_startup_smoke.py
```

Broader verification before closeout:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_cognitive_api.py \
  tests/test_routes_advisor_v3_security.py \
  tests/test_api_startup_smoke.py \
  tests/test_advisor_runtime.py \
  tests/test_kb.py
```

Compile sanity:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python -m py_compile \
  chatgptrest/api/routes_cognitive.py \
  chatgptrest/cognitive/context_service.py \
  chatgptrest/cognitive/graph_service.py \
  chatgptrest/cognitive/ingest_service.py \
  chatgptrest/cognitive/policy_service.py \
  chatgptrest/cognitive/telemetry_service.py \
  tests/test_cognitive_api.py
```

New behavioral coverage added in `tests/test_cognitive_api.py`:

- hot-path context assembly returns memory/knowledge/graph/policy blocks
- repo-graph degrade is explicit
- personal graph returns nodes/edges/evidence/paths
- knowledge ingest writes to KB and mirrors into graph
- telemetry ingest reaches event bus, observer, and episodic memory
- policy hints returns route recommendation, retrieval plan, and quality gate
- auth behavior still works for the cognitive router

## GitNexus Usage Notes

GitNexus was used for:

- pre-edit impact on `create_app`
- graph/EvoMap concept discovery
- execution-flow lookup around advisor routing and knowledge retrieval

Observed limitation:

- `gitnexus_detect_changes()` does not reliably see new files inside this isolated worktree.
- Pre-commit scope verification therefore used both:
  - GitNexus
  - `git status --short --branch`

## Known Explicit Limitations

1. `repo_graph` federation is an adapter seam, not full structured GitNexus graph hydration yet.
2. `GitNexusCliAdapter` is opt-in and best-effort; default behavior is degrade, not hidden shell-outs.
3. `knowledge.ingest` currently mirrors a primary atom per artifact instead of running the full extractor/refiner pipeline.
4. `policy.hints` computes route advice from pure routing primitives, not from the full long-running advisor graph.

These are intentional boundaries, not accidental omissions. They keep the substrate contracts stable without turning this implementation into another god-runtime.

## Result

The backend now exposes the contract set required for:

- OpenClaw slow-path advisor integration
- OpenClaw memory-slot integration
- OpenClaw execution telemetry ingestion
- OpenClaw skill/plugin output ingestion
- graph-aware retrieval and routing hints

In short:

- shell concerns stay outside
- cognition concerns stay inside
- integration happens through explicit APIs

## Review Follow-up (PR #98)

After the first review round, the following corrections were applied:

1. `policy.hints` no longer imports or runs `advisor.graph` node functions.
   - It now uses local, pure helpers for:
     - normalization
     - cheap KB probe (`auto_embed=False`)
     - intent analysis
   - This keeps the endpoint aligned with the "no frontier LLM on hot path" rule.
2. `context.resolve` no longer monkey-patches `GoogleWorkspace` / `ObsidianClient`.
   - A local-only assembler variant now performs memory + KB + EvoMap retrieval without touching module globals.
   - This removes the thread-safety hazard under concurrent requests.
3. `knowledge.ingest` now mirrors artifacts into EvoMap as staged low-trust knowledge.
   - removed the previous high fixed scores
   - primary atoms are stored as `candidate`
   - graph refs now report conservative derived scores and `trust_level=staged_low_trust`
4. Added missing route hardening tests:
   - rate limit `429`
   - `cognitive_health` runtime failure path
