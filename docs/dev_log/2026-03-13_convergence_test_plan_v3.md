# Product Convergence Validation Program

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Status: design_ready  
Supersedes:

- `docs/dev_log/2026-03-13_convergence_test_plan_v1.md`
- `docs/dev_log/2026-03-13_convergence_test_plan_v2.md`

---

## Executive Summary

This document is the release-grade validation design for the product
convergence effort.

It keeps the governance structure introduced in `v2`:

- environments
- validation waves
- release gates
- evidence model
- execution cadence

It also absorbs the useful, execution-level detail from `v1`:

- a time-bound baseline snapshot of existing test assets
- explicit test fixture infrastructure
- business-flow simulation scenarios
- network-partition and dependency-loss fault classes
- a hard rule that critical tests must be able to fail for the right reason

The program exists to prove three things:

1. **No fake health**  
   The stack must not present broken core capability as healthy.

2. **No fake convergence**  
   Multiple entry surfaces may temporarily coexist, but they must map to one
   coherent lifecycle, one coherent evidence model, and explicit migration
   semantics.

3. **No fake success**  
   A `200` response is not completion. Completion requires consistent status,
   artifacts, traces, lifecycle linkage, and recovery semantics.

---

## What This Revision Adds

Relative to `v2`, this revision adds:

- a baseline snapshot appendix grounded in the current repository
- fixture infrastructure requirements for deterministic integration and
  business-flow testing
- an explicit business-flow scenario catalog
- network-partition and external-dependency-loss simulations
- a "no accidental passes" rule in the definition of test-complete

This revision does **not** absorb the following `v1` assumptions:

- hard-coded route-count limits such as `advise_routes <= 2`
- a forced unified public response envelope before product contract decisions
  are finalized
- an assumption that a public task plane already exists on current master
- week-by-week schedule guesses
- `pytest tests/ -v` as the default release-grade execution path

---

## Inputs and Constraints

### Inputs

- `docs/contract_v1.md`
- `docs/runbook.md`
- `docs/dev_log/2026-03-12_product_convergence_execution_backlog_v1.md`
- `docs/dev_log/2026-03-12_product_convergence_backlog_review_v2.md`
- `docs/dev_log/2026-03-13_convergence_test_plan_v1.md`
- `docs/dev_log/2026-03-13_convergence_test_plan_v2.md`
- current repository test and ops assets under `tests/` and `ops/`

### Current Realities

- The repository already has deep coverage in advisor, contract, and plugin
  areas, but coverage is uneven across startup honesty, cross-entry parity,
  restart durability, and controlled failure recovery.
- `advisor_runs` is already durable in SQLite and should be treated as an
  existing execution spine.
- Some control-plane objects remain process-memory state today, especially
  trace, consult, and rate-limit stores.
- Runtime state and knowledge are still split across repo-local state and
  `~/.openmind/*`; authority must be validated explicitly.
- Live validation depends on real browsers, provider login, and environment
  correctness. It cannot replace deterministic validation.

---

## Validation Principles

### Principle 1: Deterministic Before Live

No live smoke or canary step substitutes for deterministic contract,
auth, and lifecycle coverage.

### Principle 2: Evidence Before Trust

Every wave must emit evidence. A green terminal line without artifacts,
logs, or lifecycle snapshots is not a release-grade result.

### Principle 3: Business Closure Beats Endpoint Closure

The system is validated only when real business flows close:

- ingress accepted
- lifecycle linked
- artifacts created
- answer delivered
- degraded paths surfaced honestly

### Principle 4: Critical Tests Must Be Able To Fail

Every critical validation suite must contain at least one negative or
fault-injection path that proves the assertion is meaningful.

If a test only passes in the happy path but does not demonstrably fail when the
target behavior is broken, it does not count toward release confidence.

---

## System Under Validation

The convergence program validates five planes together:

1. **Ingress Plane**  
   `v1` REST, `v2` REST, MCP adapter, CLI, OpenClaw plugins, Feishu gateway.

2. **Execution Plane**  
   job creation, worker send/wait, `advisor_runs`, artifacts, answer export,
   repair flow.

3. **Knowledge Plane**  
   KB search, memory capture/promotion, EvoMap knowledge, repo-aware retrieval,
   degraded-source signaling.

4. **Control Plane**  
   health/readiness, trace, consult, rate limiting, issue ledger, monitors,
   guardian/watchdog.

5. **Operations Plane**  
   startup scripts, systemd-managed services, canary controls, runbooks,
   evidence bundles, and incident outputs.

Validation is incomplete if any one plane is untested.

---

## Validation Environments

| Environment | Purpose | Browser / Network | Expected Determinism | Typical Use |
| --- | --- | --- | --- | --- |
| `E0-doc` | doc and command sanity | none | high | path checks, command coherence |
| `E1-offline` | deterministic validation | none | high | unit, contract, schema, import |
| `E2-local-int` | local integration | local DB + mocks | high | lifecycle, identity, plugins |
| `E3-local-live` | local live execution | real browser + provider login | medium | smoke, parity, happy path |
| `E4-fault` | controlled breakage | induced failures | medium | restart, dependency loss, chaos |
| `E5-soak` | long-running stability | real local stack | medium | 12h-24h monitoring |
| `E6-shadow` | mirrored real traffic | production-like ingress | low-medium | shadow parity |
| `E7-canary` | controlled live rollout | production ingress | low-medium | allowlist rollout |

Only `E1` and `E2` are mandatory on every change set. `E3-E7` are gate-driven.

---

## Baseline Snapshot Appendix

The following snapshot is useful as a planning baseline, but it must be treated
as time-bound and periodically refreshed:

| Category | Snapshot | Current Judgment |
| --- | --- | --- |
| Advisor / graph / runtime / orchestrate | strong | mature enough for curated regression |
| Report / planning / execution review | strong | good coverage, still not a substitute for live delivery tests |
| OpenClaw / gateway / telemetry | moderate | packaging and smoke exist, parity tests still thin |
| Security / auth / webhook | moderate | useful base, missing some proxy and cross-boundary cases |
| Memory / knowledge authority | weak-to-moderate | tenant isolation exists; authority and promotion behavior still under-specified |
| Startup / health honesty | weak | needs explicit fail-closed and health semantic tests |
| Restart / durable recovery | weak | current gap area |
| Chaos / resilience / migration | weak | current gap area |

This snapshot informs prioritization but is not itself a release gate.

---

## Fixture Infrastructure

The convergence program needs shared fixtures so integration and business-flow
tests remain deterministic and cheap to run.

### F1: `MockLLMConnector`

Purpose:

- deterministic LLM responses
- prompt capture
- controlled delay, timeout, and failure injection

Required capabilities:

- queue scripted responses
- record call log
- inject delay
- inject provider-style failure

### F2: `InMemoryAdvisorClient`

Purpose:

- stand up a FastAPI test client with isolated DB and wired mock runtime

Required capabilities:

- temp DB path or in-memory DB
- injected LLM, runtime, and config overrides
- explicit cleanup between tests

### F3: `FeishuGatewaySimulator`

Purpose:

- simulate inbound Feishu messages and capture outbound replies

Required capabilities:

- duplicate message replay
- delayed callback / ack simulation
- attachment metadata injection
- sent-reply capture for assertions

### F4: `MemoryManagerFixture`

Purpose:

- isolate memory tests from host runtime and persistent side effects

Required capabilities:

- in-memory or temp-file DB
- seeded records
- time manipulation or TTL-expiry hooks

These fixtures are not optional conveniences. They are required to keep business
simulation and failure-path testing stable.

---

## Validation Waves

### Wave 0: Static and Boot Baseline

Goal:

- prove the repo can start honestly before any business-flow testing begins

Checks:

- `py_compile` on critical entry files
- import smoke on core routers and runtime modules
- route inventory generation
- startup fail-closed behavior
- health and readiness semantic checks

Representative assets:

- `tests/test_api_startup_smoke.py`
- `chatgptrest/api/app.py`
- `chatgptrest/api/routes_jobs.py`
- `chatgptrest/api/routes_advisor_v3.py`

Required new tests:

- `livez` semantics when implemented
- boot manifest inventory tests when implemented
- router-load-failure fatal-start tests

Gate:

- no core router failure can be silently masked as ready

---

### Wave 1: Deterministic Contract Validation

Goal:

- lock down request/response semantics, auth, idempotency, and answer
  extraction without provider dependency

Checks:

- `v1` contract stability
- error and metadata consistency
- chunking and UTF-8 behavior
- idempotency collision behavior
- conversation single-flight and duplicate prompt protection
- auth behavior for `strict` vs `open`

Representative assets:

- `tests/test_contract_v1.py`
- `tests/test_contracts.py`
- `tests/test_answers_extract.py`
- `tests/test_chatgpt_web_answer_rehydration.py`
- `tests/test_conversation_single_flight.py`
- `tests/test_routes_advisor_v3_security.py`

Required new tests:

- cross-entry parity snapshots for `/v1/advisor/advise`,
  `/v2/advisor/advise`, `/v2/advisor/ask`
- explicit identity contract assertions across entry types
- dedicated proxy/loopback bypass suite

Gate:

- all deterministic contract assertions pass
- every critical suite has at least one negative case

---

### Wave 2: Durable Lifecycle Validation

Goal:

- prove jobs, runs, steps, events, and artifacts stay coherent across replay,
  retry, and restart

Checks:

- `advisor_runs` replay and reconciliation
- `final_job_id` coherence with child jobs
- artifact survival and addressability
- restart behavior for durable stores
- no false success from in-memory adjunct state

Representative assets:

- `tests/test_advisor_api.py`
- `tests/test_advisor_orchestrate_api.py`
- `tests/test_advisor_runs_replay.py`
- `tests/test_control_plane_helpers.py`
- `ops/run_execution_plane_parity_smoke.py`

Required new tests:

- restart survival tests for upgraded durable stores
- run/job drift tests
- worker-restart answer recovery tests

Gate:

- lifecycle truth reconstructs correctly after restart or replay

---

### Wave 3: Knowledge and Identity Validation

Goal:

- prove memory, KB, EvoMap, and repo-aware context behave correctly under
  complete, partial, and degraded identity conditions

Checks:

- tenant isolation
- partial identity surfaced as partial
- canonical-vs-legacy authority precedence
- repo-aware degraded signaling
- promotion rules do not create misleading state

Representative assets:

- `tests/test_cognitive_api.py`
- `tests/test_memory_tenant_isolation.py`
- `tests/test_evomap_runtime_contract.py`
- `tests/test_evomap_e2e.py`
- `tests/test_role_pack.py`

Required new tests:

- authority resolution between repo-local state and `~/.openmind/*`
- repo-graph availability / absence / stale-state tests
- promotion reachability tests that reflect real system behavior

Gate:

- no silent long-term promotion from degraded identity
- knowledge authority is asserted, not implied

---

### Wave 4: Channel and Entry Convergence Validation

Goal:

- prove all entry surfaces map to one coherent lifecycle and evidence model

Surfaces:

- `v1` REST
- `v2` advisor REST
- MCP
- CLI
- OpenClaw plugins
- Feishu gateway

Representative assets:

- `tests/test_openclaw_cognitive_plugins.py`
- `tests/test_feishu_ws_gateway.py`
- `tests/test_cli_chatgptrestctl.py`
- `tests/test_cli_improvements.py`
- `tests/test_e2e.py`
- `ops/antigravity_router_e2e.py`

Required new tests:

- same-request parity across CLI, MCP, and OpenClaw
- duplicate webhook and delayed callback simulations
- plugin-side auth mismatch tests
- cross-surface evidence comparison snapshots

Gate:

- no surface produces an untraceable logical request

---

### Wave 5: Business-Flow Simulation

Goal:

- prove that full business flows close, not only isolated endpoints

This is the main carry-over from `v1`, promoted into the core validation plan.

#### BF-01: Feishu -> Advisor -> Answer Delivery

Flow:

1. simulate Feishu message ingress
2. create canonical request identity
3. execute advisor path
4. store artifacts and answer
5. deliver reply
6. capture conversation turn / memory side effect

Assert:

- request is traceable end-to-end
- one logical reply is sent
- lifecycle closes cleanly
- memory capture happens with correct provenance

#### BF-02: Deep Research -> Drafts -> Delivery

Flow:

1. create deep research request
2. generate internal and external draft chain
3. pass through redact / delivery logic
4. outbox and artifact paths settle

Assert:

- draft chain exists
- outbox actions are idempotent
- delivery IDs are stable

#### BF-03: OpenClaw Async Flow

Flow:

1. submit via OpenClaw plugin to `/v2/advisor/ask`
2. wait via `/v1/jobs/{job_id}/wait`
3. fetch via `/v1/jobs/{job_id}/answer`

Assert:

- cross-entry submit/wait/answer semantics remain coherent
- identity metadata survives
- answer is complete and traceable

#### BF-04: Multi-Turn Memory Continuity

Flow:

1. submit an initial conceptual question
2. submit a follow-up dependent on prior context
3. verify prompt assembly uses prior turn
4. exercise working-memory capacity

Assert:

- turn-to-turn context continuity exists
- oldest turns evict correctly at capacity
- no cross-session bleed

#### BF-05: Planning Lane Lifecycle

Flow:

1. create planning-oriented request
2. execute evidence -> draft -> review -> gate
3. simulate approval and rejection path

Assert:

- checkpointing exists
- gate result is recorded
- revision loop is auditable

Gate:

- at least one canonical business flow per critical epic must pass before live
  enablement

---

### Wave 6: Live Provider Validation

Goal:

- exercise real browser-backed execution paths before cutover

Representative assets:

- `ops/run_execution_plane_parity_smoke.py`
- `ops/smoke_test_chatgpt_auto.py`
- `ops/smoke_test_qwen.sh`
- `tests/test_advisor_v3_end_to_end.py`
- `tests/test_attachment_contract_preflight.py`

Checks:

- submit/wait/answer on real provider paths
- long-answer rehydration
- attachment or Drive attach flow
- no duplicate sends during slow or deferred provider behavior

Gate:

- two consecutive live smoke passes per enabled provider path

---

### Wave 7: Fault Injection and Recovery

Goal:

- prove the system fails visibly and recovers correctly under realistic faults

Representative assets:

- `ops/maint_daemon.py`
- `ops/openclaw_guardian_run.py`
- `ops/viewer_watchdog.py`
- `ops/repair_truncated_answers.py`

#### Fault Class A: Process and Worker Failures

- API restart during active wait
- wait worker crash while answer is already visible
- driver unavailable or CDP disconnected

#### Fault Class B: Storage and Locking

- SQLite lock contention
- read-only DB path
- missing or stale artifact path

#### Fault Class C: Network Partition and Dependency Loss

This is the second major carry-over from `v1`.

Simulate:

- provider API unreachable
- Feishu API unreachable
- KB retrieval timeout
- Google Docs / email delivery dependency unavailable

Expected outcomes:

- explicit `error`, `blocked`, `cooldown`, `needs_followup`, or degraded state
- queued/retried delivery when side-effect channel is unavailable
- no silent success and no orphaned lifecycle state

Gate:

- every injected fault ends in recovery, explicit degradation, or explicit
  terminal failure with evidence

---

### Wave 8: Soak, Shadow, and Canary

Goal:

- validate long-running stability and safe production introduction

Representative assets:

- `ops/run_soak.sh`
- `ops/run_monitor_12h.sh`
- `ops/monitor_chatgptrest.py`
- `ops/openclaw_guardian_run.py`
- `docs/runbook.md`

Checks:

- 12h minimum soak
- shadow parity on selected ingress paths
- limited allowlist canary
- predefined rollback thresholds

Gate:

- no unresolved P0/P1 incident during soak window
- no channel-specific contract drift during canary

---

## Simulation Catalog

| ID | Scenario | Environment | Expected Outcome |
| --- | --- | --- | --- |
| `SIM-01` | core router import failure | `E1` | startup fails closed |
| `SIM-02` | proxy loopback bypass | `E1` | 403 without control key |
| `SIM-03` | idempotency collision | `E1` | 409 with collision metadata |
| `SIM-04` | duplicate webhook | `E2` | no duplicate logical request |
| `SIM-05` | wait worker crash | `E4` | recovery or explicit degraded state |
| `SIM-06` | UTF-8 long-answer rehydration | `E1` | correct final answer and offsets |
| `SIM-07` | DB lock contention | `E4` | explicit not-ready/degraded state |
| `SIM-08` | driver unavailable | `E4` | honest blocked/cooldown/error |
| `SIM-09` | canonical knowledge unavailable | `E2/E4` | explicit fallback or degraded path |
| `SIM-10` | partial identity capture | `E2` | partial provenance, no silent promotion |
| `SIM-11` | stale repo graph | `E2` | repo-aware path marked partial |
| `SIM-12` | delayed callback or ack | `E3/E4` | no orphaned lifecycle state |
| `SIM-13` | provider network partition | `E4` | explicit provider failure semantics |
| `SIM-14` | Feishu network partition | `E4` | queued/retryable delivery semantics |
| `SIM-15` | Docs / email dependency outage | `E4` | outbox retry or explicit failed effect |

`SIM-01`, `SIM-02`, `SIM-05`, `SIM-06`, `SIM-07`, `SIM-08`, and at least one
network/dependency-loss simulation are mandatory before release cutover.

---

## Evidence Model

Every wave must emit evidence.

Minimum evidence by wave:

- Wave 0: startup/import logs and route inventory
- Wave 1: deterministic test report and response-shape snapshots
- Wave 2: replay/reconcile snapshots and artifact linkage
- Wave 3: memory / KB / degraded-path evidence
- Wave 4: per-surface parity table
- Wave 5: business-flow run artifacts and lifecycle linkages
- Wave 6: live smoke job IDs and output paths
- Wave 7: injected-fault evidence, repair or issue-ledger outputs
- Wave 8: soak summary, shadow comparison, canary decision note

Preferred storage:

- deterministic and integration outputs: CI or `artifacts/monitor/test_runs/`
- live runs: `artifacts/jobs/<job_id>/`
- long-running monitoring: `artifacts/monitor/`
- release validation bundle: `artifacts/release_validation/<release_id>/`

---

## Release Gates

### Gate A: Merge Gate

- Wave 0 pass
- Wave 1 pass
- relevant Wave 2 subset pass

### Gate B: Integration Gate

- Gate A pass
- full Wave 2 pass
- Wave 3 and Wave 4 pass

### Gate C: Pre-Live Gate

- Gate B pass
- Wave 5 business-flow simulations pass
- Wave 6 live provider checks pass
- Wave 7 mandatory fault simulations pass

### Gate D: Release Gate

- Gate C pass
- Wave 8 soak, shadow, and canary complete
- no open P0
- no open P1 without explicit risk acceptance

---

## Execution Cadence

| Trigger | Required Validation |
| --- | --- |
| every PR | Wave 0, Wave 1, relevant Wave 2 subset |
| merge to integration branch | full Wave 2 and relevant Wave 3/4 |
| pre-live enablement | full Wave 0-7 |
| pre-cutover | full Wave 0-8 |
| post-cutover regression | Wave 6 smoke + Wave 8 monitoring subset |

---

## Initial Command Set

### Deterministic Baseline

```bash
python3 -m py_compile chatgptrest/api/app.py chatgptrest/api/routes_advisor_v3.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_api_startup_smoke.py \
  tests/test_contract_v1.py \
  tests/test_routes_advisor_v3_security.py \
  tests/test_advisor_api.py \
  tests/test_advisor_orchestrate_api.py \
  tests/test_advisor_runs_replay.py \
  tests/test_cognitive_api.py \
  tests/test_openclaw_cognitive_plugins.py
```

### Live and Operational Validation

```bash
PYTHONPATH=. ./.venv/bin/python ops/run_execution_plane_parity_smoke.py
PYTHONPATH=. ./.venv/bin/python ops/antigravity_router_e2e.py
bash ops/run_soak.sh
bash ops/run_monitor_12h.sh
```

These commands are the starting point, not the whole program.

---

## Definition of Test-Complete

The convergence effort is not validation-complete until all of the following are
true:

- required wave and gate evidence exists
- critical business-flow simulations pass
- fault injection does not result in fake success
- knowledge and identity degradation are surfaced honestly
- channel parity is proven with evidence
- soak / shadow / canary results are recorded with explicit go/no-go reasoning
- critical tests are capable of failing when target behavior is broken

Progress without these conditions is useful, but it is not release readiness.
