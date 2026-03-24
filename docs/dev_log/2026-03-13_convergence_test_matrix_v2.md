# Convergence Test Matrix

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`

This matrix operationalizes `2026-03-13_convergence_test_plan_v3.md`.

---

## Existing Asset Matrix

| Domain | Existing Assets | Current Use | Missing Layer |
| --- | --- | --- | --- |
| startup and health | `tests/test_api_startup_smoke.py` | baseline import/startup smoke | fail-closed and health-honesty suite |
| `v1` contract | `tests/test_contract_v1.py`, `tests/test_contracts.py` | deterministic contract assertions | cross-entry parity |
| answer extraction | `tests/test_answers_extract.py`, `tests/test_chatgpt_web_answer_rehydration.py` | answer-path correctness | long UTF-8 parity bundle |
| security and auth | `tests/test_routes_advisor_v3_security.py`, `tests/test_client_ip.py` | route auth and IP helpers | explicit reverse-proxy bypass suite |
| advisor lifecycle | `tests/test_advisor_api.py`, `tests/test_advisor_orchestrate_api.py`, `tests/test_advisor_runs_replay.py` | durable run spine | restart drift and artifact recovery |
| cognitive and memory | `tests/test_cognitive_api.py`, `tests/test_memory_tenant_isolation.py`, `tests/test_role_pack.py` | isolation and base cognition | authority and promotion-behavior coverage |
| EvoMap and KB | `tests/test_evomap_runtime_contract.py`, `tests/test_evomap_e2e.py` | retrieval and runtime behavior | repo-graph hot-path degradation |
| OpenClaw and plugins | `tests/test_openclaw_cognitive_plugins.py`, `ops/run_openclaw_telemetry_plugin_live_smoke.py` | package/smoke validation | same-request parity and auth alignment |
| Feishu gateway | `tests/test_feishu_ws_gateway.py` | gateway logic | duplicate delivery and callback lag |
| CLI and MCP | `tests/test_cli_chatgptrestctl.py`, `tests/test_cli_improvements.py` | surface-specific behavior | cross-surface evidence comparison |
| live execution | `ops/run_execution_plane_parity_smoke.py`, `tests/test_advisor_v3_end_to_end.py` | provider-backed happy path | curated provider rerun playbooks |
| long-run monitoring | `ops/run_soak.sh`, `ops/run_monitor_12h.sh`, `ops/monitor_chatgptrest.py` | soak and observation | release-bundle aggregation |

---

## Fixture Matrix

| Fixture | Purpose | Needed By |
| --- | --- | --- |
| `MockLLMConnector` | deterministic prompt/response control and negative injection | Wave 1, Wave 4, Wave 5 |
| `InMemoryAdvisorClient` | isolated FastAPI integration client | Wave 1, Wave 2, Wave 4 |
| `FeishuGatewaySimulator` | inbound/outbound gateway simulation | Wave 4, Wave 5, Wave 7 |
| `MemoryManagerFixture` | isolated memory and TTL behavior | Wave 3, Wave 5 |

These fixtures should be implemented as shared test infrastructure, not copied
test by test.

---

## Business-Flow Scenario Matrix

| Scenario | Entry Surface | Core Assertions | Gate |
| --- | --- | --- | --- |
| `BF-01` Feishu -> answer | Feishu gateway | one logical reply, lifecycle closure, memory capture | C |
| `BF-02` deep research -> delivery | `v2` advisor / report path | draft chain, redact/delivery stability, outbox idempotency | C |
| `BF-03` OpenClaw async flow | OpenClaw plugin + `v1` wait/answer | cross-entry coherence, full answer retrieval, identity continuity | C |
| `BF-04` multi-turn continuity | REST or plugin | prompt continuity, working-memory eviction, no cross-session bleed | C |
| `BF-05` planning lane lifecycle | planning-oriented path | checkpointing, gate recording, revision visibility | C |

At least one passing scenario is required for every critical user-facing lane
before release cutover.

---

## Fault Matrix

| Simulation | Fault Type | Plane | Expected Result | Gate |
| --- | --- | --- | --- | --- |
| `SIM-01` core router import failure | startup | ingress/control | fail-closed startup | A |
| `SIM-02` proxy loopback bypass | auth | ingress | reject without control key | A |
| `SIM-03` idempotency collision | request consistency | ingress/execution | explicit 409 collision | A |
| `SIM-04` duplicate webhook | duplicate delivery | ingress/channel | one logical request only | B |
| `SIM-05` wait worker crash | process failure | execution | recovery or explicit degraded state | C |
| `SIM-06` UTF-8 answer rehydration | artifact integrity | execution | correct final text and offsets | A |
| `SIM-07` DB lock contention | storage failure | execution/control | explicit not-ready/degraded state | C |
| `SIM-08` driver unavailable | runtime dependency | ingress/execution | blocked/cooldown/error, not false success | C |
| `SIM-09` canonical knowledge unavailable | authority loss | knowledge | fallback or degraded response | B |
| `SIM-10` partial identity capture | identity degradation | knowledge | partial provenance, no silent escalation | B |
| `SIM-11` stale repo graph | stale context | knowledge | repo-aware path marked partial | B |
| `SIM-12` delayed callback | channel lag | ingress/channel | no orphaned lifecycle | B |
| `SIM-13` provider network partition | external dependency loss | execution | explicit provider failure semantics | C |
| `SIM-14` Feishu API outage | channel dependency loss | ingress/channel | queued or retryable reply semantics | C |
| `SIM-15` Docs/email outage | side-effect dependency loss | execution/ops | outbox retry or explicit failed effect | C |

---

## Gate Matrix

| Gate | Required Waves | Required Evidence |
| --- | --- | --- |
| A | Wave 0, Wave 1, relevant Wave 2 subset | compile/import output, deterministic pytest report, auth/contract snapshots |
| B | Gate A + full Wave 2 + Wave 3 + Wave 4 | lifecycle replay artifacts, knowledge degradation evidence, cross-entry parity notes |
| C | Gate B + Wave 5 + Wave 6 + Wave 7 | business-flow outputs, live smoke job IDs, fault-injection evidence |
| D | Gate C + Wave 8 | soak summary, shadow/canary decision record, explicit rollback condition |

---

## Anti-Accidental-Pass Matrix

| Test Class | Positive Proof Needed | Negative Proof Needed |
| --- | --- | --- |
| startup honesty | startup succeeds when healthy | startup fails when core router is broken |
| auth | valid token/key passes | missing/invalid/proxy-bypassed access fails |
| lifecycle | run/job/artifact chain closes | induced drift is detected and reconciled |
| memory / knowledge | correct retrieval and promotion | degraded identity / missing authority does not silently pass |
| channel integration | reply delivered when channel is healthy | duplicate delivery / delayed callback does not double-complete |
| live execution | provider-backed request completes | provider outage does not surface as success |

Any gate review should reject suites that only provide the positive side.
