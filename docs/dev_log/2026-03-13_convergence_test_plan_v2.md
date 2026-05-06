# Product Convergence Validation Program

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Status: design_ready  
Supersedes: `docs/dev_log/2026-03-13_convergence_test_plan_v1.md`

---

## Executive Summary

This document defines the release-grade validation program for the product convergence effort. It is not a generic QA outline. It is an execution design for proving that the converged system is:

- structurally healthy, not just bootable
- contract-consistent across `v1`, `v2`, MCP, CLI, OpenClaw, and Feishu
- durable under restart, replay, and partial failure
- explicit about degraded knowledge and identity gaps
- operationally honest about readiness and breakage

The validation program is built around three governing principles:

1. **No fake health**  
   A failed core router, missing runtime, dead driver, or broken channel must not surface as "ok".

2. **No fake convergence**  
   Multiple entrypoints may coexist during migration, but they must map to one coherent lifecycle and one coherent evidence model.

3. **No fake success**  
   A request is not "done" because an endpoint returned `200`. It is done only when lifecycle state, artifacts, traces, notifications, and recovery semantics all agree.

---

## Inputs and Constraints

### Inputs

- `docs/contract_v1.md`
- `docs/runbook.md`
- `docs/dev_log/2026-03-12_product_convergence_execution_backlog_v1.md`
- `docs/dev_log/2026-03-12_product_convergence_backlog_review_v2.md`
- `docs/dev_log/2026-03-13_convergence_test_plan_v1.md`
- current repository test and ops assets under `tests/` and `ops/`

### Current Realities This Program Must Respect

- The repository already contains broad module and integration coverage, but coverage is uneven across startup, cross-entry contract compliance, restart durability, and chaos/recovery.
- `advisor_runs` is already durable in SQLite. Validation must treat it as an existing core spine, not as greenfield.
- Some control-plane components remain process-memory state today, especially trace, consult, and rate-limit stores.
- Live validation depends on real browser automation, provider quotas, and environment correctness. The plan must distinguish deterministic suites from live/operator-gated checks.
- Runtime data exists in both repo-local state and `~/.openmind/*`. The plan must validate authority and fallback behavior explicitly instead of assuming a single store.

---

## Scope

### In Scope

- API startup and readiness semantics
- public entry contract convergence
- auth and trust-boundary correctness
- identity chain continuity
- job / run / artifact lifecycle consistency
- control-plane durability and restart behavior
- knowledge retrieval and degraded-path signaling
- OpenClaw / Feishu / MCP / CLI integration
- repair and self-healing behavior
- live smoke, fault injection, soak, and canary rollout
- evidence collection and release gates

### Out of Scope

- full product implementation of the convergence backlog itself
- provider-side correctness beyond what the system can observe and assert
- large-scale load testing beyond single-host operational limits
- subjective answer quality review unrelated to lifecycle correctness

---

## System Under Validation

The validation program treats the product as five interacting planes:

1. **Ingress Plane**  
   `v1` REST, `v2` REST, MCP adapter, CLI, OpenClaw plugins, Feishu gateway.

2. **Execution Plane**  
   job creation, worker send/wait, `advisor_runs`, artifacts, answer export, repair flow.

3. **Knowledge Plane**  
   KB search, memory capture/promotion, EvoMap knowledge, repo-aware retrieval, degraded-source signaling.

4. **Control Plane**  
   health/readiness, trace, consult, rate limiting, issue ledger, monitors, guardian/watchdog.

5. **Operations Plane**  
   startup scripts, systemd-managed services, canary controls, runbooks, evidence and incident outputs.

Validation is considered incomplete if any one plane is untested.

---

## Validation Environments

| Environment | Purpose | Network / Browser | Expected Determinism | Allowed Tests |
| --- | --- | --- | --- | --- |
| `E0-doc` | static doc and command validation | none | high | reference and path verification |
| `E1-offline` | pure unit and contract validation | none | high | unit, contract, schema, import, migration |
| `E2-local-int` | single-host integration | local DB + mocked services | high | API integration, lifecycle, replay, plugin package tests |
| `E3-local-live` | single-host live provider validation | real browser + real provider login | medium | smoke, parity, end-to-end happy path |
| `E4-fault` | controlled breakage | induced process/DB/network failures | medium | restart, chaos, recovery, degraded-mode |
| `E5-soak` | long-running stability | real local stack | medium | 12h-24h monitoring, incident surface checks |
| `E6-shadow` | non-user-impact real traffic mirror | production-like ingress | low-medium | shadow parity, response/evidence comparison |
| `E7-canary` | limited live cutover | production ingress | low-medium | limited-account/channel rollout |

Only `E1` and `E2` are required for every commit. `E3-E7` are release gates.

---

## Validation Waves

### Wave 0: Static and Boot Baseline

**Goal**: prove the repo can start honestly before any runtime or business-flow testing begins.

**Entry Criteria**

- branch is clean enough to isolate the intended changes
- no unresolved merge markers
- required Python environment exists

**Required Checks**

- `py_compile` on critical entry files
- import smoke for core routers and runtime modules
- route inventory generation
- startup in failure mode must fail-closed for core router failure
- health endpoint semantics check

**Representative Assets**

- `tests/test_api_startup_smoke.py`
- `chatgptrest/api/app.py`
- `chatgptrest/api/routes_jobs.py`
- `chatgptrest/api/routes_advisor_v3.py`

**New Coverage Required**

- `livez` behavior once implemented
- boot manifest / startup inventory once implemented
- explicit "router failed to load" fatal-start tests

**Exit Gate**

- no import/compile failures
- startup semantics are explicit and testable
- no core router failure can be silently masked as ready

---

### Wave 1: Deterministic Contract Validation

**Goal**: lock down request/response semantics, auth, idempotency, and answer extraction without depending on live providers.

**What Must Be Proven**

- `v1` contract stability as defined in `docs/contract_v1.md`
- consistent error envelopes and response metadata
- correct answer chunking, offsets, and UTF-8 handling
- idempotency collision behavior
- duplicate prompt protections and conversation single-flight
- auth behavior for `strict` vs `open` modes

**Representative Assets**

- `tests/test_contract_v1.py`
- `tests/test_contracts.py`
- `tests/test_answers_extract.py`
- `tests/test_chatgpt_web_answer_rehydration.py`
- `tests/test_conversation_single_flight.py`
- `tests/test_conversation_url_conflict.py`
- `tests/test_client_ip.py`
- `tests/test_routes_advisor_v3_security.py`

**Required New Tests**

- cross-entry envelope compliance between `/v1/advisor/advise`, `/v2/advisor/advise`, and `/v2/advisor/ask`
- explicit identity contract assertions across entry types
- dedicated loopback/proxy bypass tests for cc-control

**Exit Gate**

- all deterministic contract tests pass
- every public error shape is asserted, not only happy paths
- no auth path relies on implicit transport assumptions

---

### Wave 2: Durable Lifecycle Validation

**Goal**: prove that jobs, runs, steps, events, and artifacts remain consistent across replay, retry, and restart boundaries.

**What Must Be Proven**

- `advisor_runs` state transitions are durable and replayable
- run metadata and `final_job_id` stay consistent with child jobs
- artifacts remain addressable and auditable after reconciliation
- restart does not lose durable state
- in-memory adjunct state does not create false success

**Representative Assets**

- `tests/test_advisor_api.py`
- `tests/test_advisor_orchestrate_api.py`
- `tests/test_advisor_runs_replay.py`
- `tests/test_control_plane_helpers.py`
- `ops/run_execution_plane_parity_smoke.py`

**Required New Tests**

- restart survival tests for any store upgraded from in-memory to durable
- run/job drift tests:
  - run says `completed`, job says `error`
  - job says `completed`, run remains `WAITING_GATES`
- artifact survival and answer-path recovery tests after worker restart

**Exit Gate**

- lifecycle assertions pass after forced process restart
- replay/reconcile changes are deterministic
- durable stores and artifacts can reconstruct the last known truth

---

### Wave 3: Knowledge and Identity Validation

**Goal**: prove that memory, KB, EvoMap, and repo-aware context behave correctly under complete, partial, and degraded identity conditions.

**What Must Be Proven**

- memory capture respects tenant isolation
- partial identity is surfaced as partial, not silently promoted
- repo-aware requests degrade honestly when graph context is absent
- canonical read precedence beats legacy fallback where intended
- promotion rules do not create hidden or misleading state

**Representative Assets**

- `tests/test_cognitive_api.py`
- `tests/test_memory_tenant_isolation.py`
- `tests/test_evomap_runtime_contract.py`
- `tests/test_evomap_e2e.py`
- `tests/test_role_pack.py`
- `chatgptrest/cognitive/context_service.py`
- `chatgptrest/kernel/memory_manager.py`

**Required New Tests**

- canonical-vs-legacy resolution tests for `state/*` vs `~/.openmind/*`
- repo-graph hot-path tests for:
  - graph available
  - graph missing
  - graph stale or empty
- promotion reachability tests that capture current semantic-tier behavior without requiring test-only workarounds

**Exit Gate**

- every degraded path produces explicit degraded evidence
- no cross-tenant memory leakage
- knowledge authority precedence is tested, not assumed

---

### Wave 4: Channel and Entry Convergence Validation

**Goal**: prove that all user-facing entry surfaces map to a coherent lifecycle and evidence model.

**Entry Surfaces**

- `v1` REST
- `v2` advisor REST
- MCP adapter
- CLI
- OpenClaw plugins
- Feishu gateway

**What Must Be Proven**

- the same logical request can be traced across surfaces
- identity metadata is preserved or degraded consistently
- wait/answer recovery behavior matches submit semantics
- channel-specific wrappers do not bypass core controls

**Representative Assets**

- `tests/test_openclaw_cognitive_plugins.py`
- `tests/test_feishu_ws_gateway.py`
- `tests/test_cli_chatgptrestctl.py`
- `tests/test_cli_improvements.py`
- `tests/test_e2e.py`
- `ops/antigravity_router_e2e.py`
- `ops/run_openclaw_telemetry_plugin_live_smoke.py`

**Required New Tests**

- same-request parity tests across CLI, MCP, and OpenClaw
- Feishu duplicate webhook / delayed callback / attachment edge cases
- MCP and plugin-side auth mismatch tests
- cross-entry envelope comparison snapshots

**Exit Gate**

- no surface produces an untraceable request
- no surface bypasses the intended auth or lifecycle contract
- all channel-specific deviations are documented and tested

---

### Wave 5: Live Provider Validation

**Goal**: exercise the real execution path through browser automation and provider behavior without yet taking production traffic.

**Providers / Modes**

- ChatGPT Web
- Gemini Web
- Qwen Web
- Deep research paths where available

**What Must Be Proven**

- end-to-end submit/wait/answer works on real browsers
- long answers rehydrate correctly
- attachments or Drive-based attach flows work on supported paths
- slow-path provider flows do not lead to duplicate sends or false completion

**Representative Assets**

- `ops/run_execution_plane_parity_smoke.py`
- `ops/smoke_test_chatgpt_auto.py`
- `ops/smoke_test_qwen.sh`
- `tests/test_advisor_v3_end_to_end.py`
- `tests/test_answer_quality_completion_guard.py`
- `tests/test_attachment_contract_preflight.py`

**Operational Rules**

- use non-trivial prompts that still have deterministic acceptance criteria
- avoid expensive or ambiguous provider usage when a lower-cost path can prove the same invariant
- record all live jobs and artifacts for audit

**Exit Gate**

- two consecutive live smoke passes for each enabled provider path
- no manual cleanup needed to get terminal state
- artifacts, wait behavior, and exported answers agree with final status

---

### Wave 6: Fault Injection and Recovery

**Goal**: prove the system fails visibly and recovers correctly under realistic fault conditions.

**Fault Classes**

- process crash
- worker crash during send or wait
- driver unavailable
- CDP disconnected
- DB lock / contention
- provider wait stall
- duplicate delivery
- artifact truncation or missing export
- reverse-proxy IP ambiguity

**Representative Assets**

- `ops/maint_daemon.py`
- `ops/openclaw_guardian_run.py`
- `ops/viewer_watchdog.py`
- `ops/repair_truncated_answers.py`
- issue-ledger and repair tests already present in the repo

**Required New Scenarios**

- kill API during active wait, then restart and reconcile
- kill wait worker with answer already visible in browser and verify autofix/export recovery
- force SQLite lock contention and verify explicit degraded/non-ready signals
- replay duplicated Feishu/OpenClaw events and verify dedup semantics

**Exit Gate**

- every injected fault ends in one of:
  - successful recovery
  - explicit degraded state
  - explicit terminal failure with evidence
- no injected fault results in false `ok` or orphaned lifecycle state

---

### Wave 7: Soak, Shadow, and Canary

**Goal**: prove the system remains operational over time and can be introduced safely to real traffic.

**Soak Requirements**

- 12h minimum single-host soak
- 24h preferred before real canary
- monitor:
  - `ops/status`
  - UI canary
  - stuck waits
  - issue ledger growth
  - worker health
  - DB lock or contention symptoms

**Shadow Requirements**

- mirror selected requests without user-visible side effects
- compare route decision, job lifecycle, and artifact completeness

**Canary Requirements**

- low-volume rollout by explicit account/channel allowlist
- rollback criteria defined before start
- issue-family thresholds and stuck-wait thresholds predeclared

**Representative Assets**

- `ops/run_soak.sh`
- `ops/run_monitor_12h.sh`
- `ops/monitor_chatgptrest.py`
- `ops/openclaw_guardian_run.py`
- `docs/runbook.md`

**Exit Gate**

- no unresolved P0/P1 incident during soak window
- no channel-specific contract drift during canary
- rollback path validated before cutover

---

## Simulation Catalog

Each simulation must produce both a pass/fail result and evidence artifacts.

| ID | Scenario | How to Simulate | Expected Outcome | Evidence |
| --- | --- | --- | --- | --- |
| `SIM-01` | core router import failure | monkeypatch router factory to raise | startup fails closed; no ready state | startup logs, test output |
| `SIM-02` | loopback bypass via reverse proxy | set `X-Forwarded-For`, proxy host loopback | request rejected unless control key is present | response body, auth logs |
| `SIM-03` | duplicate idempotency key | same key, different payload | HTTP 409 with collision detail | API response, events |
| `SIM-04` | duplicate webhook delivery | replay same webhook twice | deduped lifecycle; no double artifact | events, issue ledger |
| `SIM-05` | wait worker crash | stop wait worker during active job | recovery on restart or explicit degraded state | job events, recovery report |
| `SIM-06` | UTF-8 long answer rehydration | staged multibyte answer chunks | correct final text and offsets | answer artifact, chunk metadata |
| `SIM-07` | DB lock contention | concurrent writers or forced lock | explicit `not_ready/degraded`, no false success | logs, health output |
| `SIM-08` | driver unavailable | stop driver / break CDP | request blocks or degrades honestly; no duplicate send | status output, issue ledger |
| `SIM-09` | canonical knowledge unavailable | move or mask canonical DB | fallback path explicit or query degraded | retrieval response, logs |
| `SIM-10` | partial identity memory capture | omit `thread_id` or `account_id` | capture marked partial; no silent long-term escalation | memory record, provenance |
| `SIM-11` | stale repo graph | disable graph injection or stale snapshot | repo-aware answer marked partial/degraded | response hints, trace |
| `SIM-12` | channel callback lag | delay Feishu/OpenClaw callback | request remains traceable; no orphan state | gateway logs, run state |

No release may skip `SIM-01`, `SIM-02`, `SIM-05`, `SIM-06`, `SIM-07`, or `SIM-08`.

---

## Evidence Model

Every wave must emit evidence into a stable place. A test pass without evidence is not release-grade.

### Required Evidence Types

- command transcript or CI log
- structured test result
- artifacts for live or recovery checks
- issue / incident references when faults are injected
- route or lifecycle snapshots when parity is asserted

### Preferred Storage

- unit and integration logs: CI artifacts or `artifacts/monitor/test_runs/`
- live smoke artifacts: `artifacts/jobs/<job_id>/`
- soak outputs: `artifacts/monitor/`
- release bundle: `artifacts/release_validation/<release_id>/`

### Minimum Evidence Per Wave

- Wave 0: startup/import logs and route inventory snapshot
- Wave 1: contract test report and response shape snapshots
- Wave 2: lifecycle replay snapshots and artifact-path assertions
- Wave 3: memory / KB / degraded-path evidence
- Wave 4: per-surface parity table with run/job/artifact linkage
- Wave 5: live job IDs, answer artifacts, and provider notes
- Wave 6: injected fault records, recovery traces, issue ledger entries
- Wave 7: soak summary, ops status history, canary decision record

---

## Release Gates

### Gate A: Merge Gate

Required for merging into the convergence branch:

- Wave 0 pass
- Wave 1 pass
- Wave 2 pass
- any code or contract change must update the relevant tests

### Gate B: Integration Gate

Required before enabling new entrypoints or new lifecycle behavior:

- Gate A pass
- Wave 3 pass
- Wave 4 pass

### Gate C: Live Gate

Required before turning on real browser-backed execution for the new path:

- Gate B pass
- Wave 5 pass twice consecutively
- Wave 6 mandatory simulations pass

### Gate D: Release Gate

Required before user-facing cutover:

- Gate C pass
- Wave 7 soak and canary complete
- no open P0 issue
- no known P1 issue without explicit risk acceptance

---

## Execution Cadence

| Cadence | Required Waves |
| --- | --- |
| every PR | Wave 0, Wave 1, relevant Wave 2 subset |
| merge-to-integration | full Wave 2, relevant Wave 3/4 |
| pre-live enablement | full Wave 0-6 |
| pre-cutover | full Wave 0-7 |
| post-cutover regression | Wave 5 smoke + Wave 7 monitoring subset |

---

## Ownership Model

| Role | Responsibilities |
| --- | --- |
| core implementation owner | deterministic tests, lifecycle tests, code-fix follow-through |
| integration owner | CLI/MCP/OpenClaw/Feishu parity and channel simulations |
| ops owner | live smoke environment, soak, canary, rollback readiness |
| reviewer | release gate adjudication based on evidence, not anecdotes |

No single person should approve Gate C or Gate D based only on local happy-path smoke.

---

## Initial Command Set

### Deterministic Baseline

```bash
python3 -m py_compile chatgptrest/api/app.py chatgptrest/api/routes_advisor_v3.py

./.venv/bin/pytest -q \
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

These commands are the starting point, not the full program. The matrix document defines how they map to waves and gates.

---

## Known Gaps at Time of Writing

- `v1` and `v2` entry convergence is still real work; current validation must compare them, not assume one authoritative public contract yet.
- control-plane durability is uneven; some stores remain process-memory state.
- live-provider validation is environmentally fragile by nature; release evidence must separate code regressions from environment breakage.
- knowledge authority remains partially split between repo-local state and `~/.openmind/*`; validation must explicitly assert precedence and degraded behavior.

---

## Definition of Done

The convergence effort is considered validation-complete only when:

- the full wave set has evidence attached
- release gates are satisfied in sequence
- fault injection does not yield fake success
- channel parity is proven, not assumed
- knowledge and identity degradation are surfaced honestly
- canary results are recorded with explicit go/no-go reasoning

Anything short of that is progress, but not release readiness.
