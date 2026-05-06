# OpenMind Scope Surface Inventory v1

Date: 2026-04-09  
Status: canonical scope inventory for Phase 6

## Purpose

This file closes the naming drift problem by classifying every major OpenMind/OpenClaw-facing surface as one of:

- implemented runtime
- bridge only
- audit / policy only
- reserved / not implemented

## Surface table

| Surface | Current authority | Classification | Canonical write / truth path | Notes |
|---|---|---|---|---|
| `openmind-advisor` plugin | ChatgptREST runtime truth, OpenClaw session consumption | bridge only | `POST /v3/agent/turn` and related planning/session helper APIs | not a standalone advisor brain |
| `openmind-memory` plugin | ChatgptREST memory services | bridge only | `/v2/context/resolve`, `/v2/memory/capture` | occupies OpenClaw memory slot but does not own durable memory |
| `openmind-graph` plugin | ChatgptREST graph services | bridge only | `/v2/graph/query` | retrieval bridge only |
| `openmind-telemetry` plugin | ChatgptREST ingest + OpenMind schema expectations | bridge only + audit coupling | `/v2/telemetry/ingest` | event producer is external; normalization lives in ChatgptREST |
| authority anchor (`_project_context.md`) | human-maintained project authority | implemented runtime dependency | planning repo `_project_context.md` | highest-priority substrate input |
| wake-up packet compiler | ChatgptREST advisor/runtime plane | implemented runtime | `/v3/agent/turn` -> `task_intake.available_inputs.wake_up_packet` | OpenClaw consumes the projection; it does not own the compiler |
| crystallized learning artifact | ChatgptREST interaction-learning projection | implemented runtime | interaction-learning memory -> packet `crystallized_learning` | advisory only, with invalidation |
| OpenMind constitutional layer | OpenMind naming / audit / policy contract | audit / policy only | ADRs, trace/event contracts, receipt expectations | not proof of a separate durable runtime |
| standalone OpenMind advisor runtime | none | reserved / not implemented | none | do not claim current ownership |
| standalone OpenMind durable-memory runtime | none | reserved / not implemented | none | do not claim current ownership |

## Consequences

1. Canonical docs may describe `openmind-*` plugins as bridge families, but must not describe them as proof of a separate durable-memory runtime.
2. OpenClaw remains the user-facing orchestration shell.
3. ChatgptREST remains the production/truth substrate.
4. OpenMind remains the constitutional / audit naming layer unless and until an actual runtime is implemented.
