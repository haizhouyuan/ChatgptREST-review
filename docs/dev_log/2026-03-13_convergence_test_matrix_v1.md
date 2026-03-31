# Convergence Test Matrix

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`

This matrix operationalizes `2026-03-13_convergence_test_plan_v2.md`.

---

## Wave Matrix

| Wave | Domain | Environment | Existing Assets | New Assets / Gaps | Gate |
| --- | --- | --- | --- | --- | --- |
| W0 | startup and health honesty | E1-offline | `tests/test_api_startup_smoke.py` | `test_startup_fail_closed.py`, `test_health_endpoints.py` | A |
| W1 | `v1` contract | E1-offline | `tests/test_contract_v1.py`, `tests/test_contracts.py` | cross-entry envelope tests | A |
| W1 | answer extraction and UTF-8 | E1-offline | `tests/test_answers_extract.py`, `tests/test_chatgpt_web_answer_rehydration.py` | explicit multibyte long-answer parity | A |
| W1 | auth and IP trust boundary | E1-offline | `tests/test_routes_advisor_v3_security.py`, `tests/test_client_ip.py` | dedicated proxy/loopback bypass suite | A |
| W2 | advisor run lifecycle | E2-local-int | `tests/test_advisor_api.py`, `tests/test_advisor_orchestrate_api.py`, `tests/test_advisor_runs_replay.py` | drift/restart lifecycle suite | A |
| W2 | control-plane helpers | E2-local-int | `tests/test_control_plane_helpers.py` | durable trace/consult/rate-limit suites when implemented | A |
| W3 | cognitive and memory | E2-local-int | `tests/test_cognitive_api.py`, `tests/test_memory_tenant_isolation.py` | canonical-vs-legacy authority tests | B |
| W3 | EvoMap and KB runtime | E2-local-int | `tests/test_evomap_runtime_contract.py`, `tests/test_evomap_e2e.py` | repo-graph hot-path degradation suite | B |
| W4 | OpenClaw plugin packaging and parity | E2-local-int / E3-local-live | `tests/test_openclaw_cognitive_plugins.py`, `ops/run_openclaw_telemetry_plugin_live_smoke.py` | same-request parity snapshots | B |
| W4 | Feishu gateway | E2-local-int / E3-local-live | `tests/test_feishu_ws_gateway.py` | duplicate webhook and delayed callback simulations | B |
| W4 | CLI and MCP entry parity | E2-local-int | `tests/test_cli_chatgptrestctl.py`, `tests/test_cli_improvements.py` | cross-surface envelope and identity parity | B |
| W5 | live execution parity | E3-local-live | `ops/run_execution_plane_parity_smoke.py`, `tests/test_advisor_v3_end_to_end.py` | provider-specific rerun playbooks | C |
| W5 | attachment flows | E3-local-live | `tests/test_attachment_contract_preflight.py` | live attach/Drive evidence bundle | C |
| W6 | repair and recovery | E4-fault | `ops/repair_truncated_answers.py`, issue-ledger and repair suites | process crash / DB lock / worker kill scenarios | C |
| W6 | watcher and guardian | E4-fault / E5-soak | `ops/openclaw_guardian_run.py`, `ops/viewer_watchdog.py`, `ops/maint_daemon.py` | explicit fault-injection playbook | C |
| W7 | soak and monitor | E5-soak | `ops/run_soak.sh`, `ops/run_monitor_12h.sh`, `ops/monitor_chatgptrest.py` | release bundle aggregation | D |
| W7 | shadow/canary | E6-shadow / E7-canary | `docs/runbook.md`, `ops/openclaw_guardian_run.py` | account/channel allowlist rollout procedure | D |

---

## Simulation Matrix

| Simulation | Target Plane | Environment | Trigger | Expected Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| `SIM-01` core router import failure | ingress / control | E1 | monkeypatch router import | startup failure, not ready | startup log, test result |
| `SIM-02` proxy loopback bypass | ingress / security | E1 | forwarded IP + loopback transport | 403 without control key | auth response snapshot |
| `SIM-03` idempotency collision | ingress / execution | E1 | same key, different payload | 409 with collision metadata | API response |
| `SIM-04` duplicate webhook | ingress / execution | E2 | replay identical event | one logical request only | gateway events |
| `SIM-05` wait worker crash | execution | E4 | stop wait worker mid-flight | recover or explicit degraded state | job events, repair report |
| `SIM-06` UTF-8 long answer rehydration | execution | E1 | multibyte chunked answer | correct final answer and offsets | answer artifact |
| `SIM-07` DB lock contention | execution / control | E4 | concurrent writers | explicit not-ready/degraded | logs, health output |
| `SIM-08` driver unavailable | ingress / execution | E4 | stop driver or CDP | honest blocked/cooldown/error | ops status, issue ledger |
| `SIM-09` canonical knowledge unavailable | knowledge | E2/E4 | mask canonical DB path | explicit fallback or degraded path | retrieval response |
| `SIM-10` partial identity capture | knowledge / identity | E2 | omit account or thread fields | partial provenance, no silent promotion | memory evidence |
| `SIM-11` stale repo graph | knowledge | E2 | disable graph injection | repo-aware path marked partial | trace / hints |
| `SIM-12` channel callback lag | ingress / channel | E3/E4 | delayed callback or ack | no orphaned task/run/job state | channel logs |

---

## Evidence Checklist by Gate

### Gate A

- compile/import output
- deterministic pytest report
- auth / contract snapshots

### Gate B

- Gate A artifacts
- lifecycle replay artifacts
- knowledge degradation evidence
- cross-entry parity notes

### Gate C

- Gate B artifacts
- live smoke job IDs and output paths
- fault injection outputs
- issue ledger entries for injected faults

### Gate D

- Gate C artifacts
- soak summary
- canary decision record
- explicit go/no-go note with rollback condition

---

## Default Execution Order

1. W0 startup honesty
2. W1 deterministic contract
3. W2 durable lifecycle
4. W3 knowledge and identity
5. W4 channel and entry convergence
6. W5 live execution parity
7. W6 fault injection and recovery
8. W7 soak, shadow, canary

Do not reorder W5 before W0-W4. Live validation is not a substitute for deterministic coverage.
