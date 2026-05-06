# OpenMind Scope Surface Inventory v2

Date: 2026-04-09  
Status: canonical scope inventory after production-readiness PR-5

## Purpose

This file closes the remaining naming drift by classifying every major OpenMind/OpenClaw-facing surface as one of:

- implemented runtime
- bridge only
- audit / policy only
- reserved / not implemented

v2 supersedes v1 by:

- aligning the scope matrix with packet contract v2
- marking crystallized learning as shadow-only packet projection
- explicitly naming graph and policy standalone runtimes as reserved, not implemented

Historical file retained:

- `docs/contracts/2026-04-09_openmind_scope_surface_inventory_v1.md`

## Surface table

| Surface | Current authority | Classification | Canonical write / truth path | Runtime status | Notes |
|---|---|---|---|---|---|
| `openmind-advisor` plugin | ChatgptREST runtime truth, OpenClaw session consumption | bridge only | `POST /v3/agent/turn` and related planning/session helper APIs | live | not a standalone advisor brain |
| `openmind-memory` plugin | ChatgptREST memory services | bridge only | `/v2/context/resolve`, `/v2/memory/capture` | live | occupies the OpenClaw memory slot but does not own durable memory |
| `openmind-graph` plugin | ChatgptREST graph services | bridge only | `/v2/graph/query` | live | bridge is live even when graph recall is empty on a given host |
| `openmind-telemetry` plugin | ChatgptREST ingest + OpenMind schema expectations | bridge only + audit coupling | `/v2/telemetry/ingest` | live | event producer is external; normalization lives in ChatgptREST |
| authority anchor (`_project_context.md`) | human-maintained project authority | implemented runtime dependency | planning repo `_project_context.md` | live | highest-priority substrate input |
| wake-up packet compiler | ChatgptREST advisor/runtime plane | implemented runtime | `/v3/agent/turn` -> `task_intake.available_inputs.wake_up_packet` | live | OpenClaw consumes the projection; it does not own the compiler |
| crystallized learning artifact | ChatgptREST interaction-learning projection | implemented runtime | interaction-learning memory -> packet `crystallized_learning` | shadow-only | advisory packet projection only; wider reuse remains blocked |
| OpenMind constitutional layer | OpenMind naming / audit / policy contract | audit / policy only | ADRs, trace/event contracts, receipt expectations | live | not proof of a separate durable runtime |
| standalone OpenMind advisor runtime | none | reserved / not implemented | none | reserved | do not claim current ownership |
| standalone OpenMind durable-memory runtime | none | reserved / not implemented | none | reserved | do not claim current ownership |
| standalone OpenMind graph runtime | none | reserved / not implemented | none | reserved | current graph surface is only the bridge into ChatgptREST |
| standalone OpenMind policy runtime | none | reserved / not implemented | none | reserved | current policy role is constitutional/audit, not a separate runtime |

## Canonical references

- `docs/contracts/ADR-005-openmind-openclaw-chatgptrest-authority-boundary-v1.md`
- `docs/contracts/2026-04-09_wakeup_packet_contract_v2.md`
- `docs/contracts/2026-04-09_crystallized_learning_governance_contract_v1.md`
- `docs/integrations/2026-04-09_openclaw_cognitive_substrate_runtime_contract_v4.md`

## Consequences

1. Canonical docs may describe `openmind-*` plugins as bridge families, but must not describe them as proof of a separate durable-memory runtime.
2. OpenClaw remains the user-facing orchestration shell.
3. ChatgptREST remains the production/truth substrate.
4. OpenMind remains the constitutional / audit naming layer unless and until an actual runtime is implemented.
