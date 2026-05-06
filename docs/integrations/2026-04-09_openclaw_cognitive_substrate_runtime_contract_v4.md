# OpenClaw Cognitive-Substrate Runtime Contract v4

Date: 2026-04-09  
Status: current canonical integration contract after production-readiness PR-5

## Why this version exists

v3 froze the packet path and scope split after the first execution cycle.

v4 adds:

- packet contract v2 as the current packet reference
- crystallized-learning governance contract as a canonical companion
- scope inventory v2 as the authoritative surface matrix
- explicit statement that current crystal projection remains shadow-only

Historical files retained:

- `docs/integrations/openclaw_cognitive_substrate.md`
- `docs/integrations/2026-04-09_openclaw_cognitive_substrate_runtime_contract_v2.md`
- `docs/integrations/2026-04-09_openclaw_cognitive_substrate_runtime_contract_v3.md`

Use v4 as the canonical runtime contract after PR-5.

## Current topology

```text
OpenClaw runtime
  -> openmind-* plugins
  -> ChatgptREST APIs
  -> substrate truth assembly
  -> wake-up packet compiler
  -> compiled prompt / execution lane delivery
```

This is still **not** a claim that OpenClaw owns durable project memory or planning truth.

## Canonical authority model

Short version:

- OpenClaw is the consumption/orchestration shell
- ChatgptREST is the production/truth substrate
- OpenMind is the constitutional / trace / policy layer

Canonical references:

- `docs/contracts/ADR-005-openmind-openclaw-chatgptrest-authority-boundary-v1.md`
- `docs/contracts/2026-04-09_openmind_scope_surface_inventory_v2.md`

## Plugin contract summary

| Plugin | Current role | Current backend | Classification |
|---|---|---|---|
| `openmind-advisor` | slow-path public agent bridge + packet consumer | `POST /v3/agent/turn` plus planning/session helper APIs | bridge only |
| `openmind-memory` | OpenClaw memory-slot bridge for recall/capture | `POST /v2/context/resolve`, `POST /v2/memory/capture` | bridge only |
| `openmind-graph` | graph retrieval bridge | `POST /v2/graph/query` | bridge only |
| `openmind-telemetry` | execution telemetry bridge | `POST /v2/telemetry/ingest` | bridge only + audit coupling |

## Wake-up packet runtime contract

Current canonical packet contract:

- `docs/contracts/2026-04-09_wakeup_packet_contract_v2.md`

Current behavior:

- ChatgptREST compiles a wake-up packet inside `/v3/agent/turn`
- the packet is attached to `task_intake.available_inputs.wake_up_packet`
- prompt assembly renders a compact packet projection
- backend execution lanes receive the same packetized truth through the compiled prompt

This means OpenClaw does **not** need to become the durable-memory organizer in order to consume layered project truth.

## Crystallized learning status

Current canonical contract:

- `docs/contracts/2026-04-09_crystallized_learning_governance_contract_v1.md`

Current status:

- interaction-learning writeback exists in ChatgptREST
- stable cross-session preferences can be projected into packet `crystallized_learning`
- current projection mode is `shadow`
- the crystal remains advisory only and explicitly lower priority than the authority anchor

This is a bounded Hermes-style borrowing, not a self-evolution runtime.

## Reserved surfaces

The following remain explicitly reserved / not implemented:

- standalone OpenMind advisor runtime
- standalone OpenMind durable-memory runtime
- standalone OpenMind graph runtime
- standalone OpenMind policy runtime

Any documentation that implies those runtimes already exist is incorrect.
