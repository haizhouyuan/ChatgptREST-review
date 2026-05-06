# OpenClaw Cognitive-Substrate Runtime Contract v3

Date: 2026-04-09  
Status: current canonical integration contract

## Why this version exists

v2 froze the authority split and corrected the `/v3/agent/*` bridge description.

v3 adds the now-live wake-up packet path and the clarified scope inventory:

- wake-up packet compilation now exists in the ChatgptREST runtime plane
- `openmind-advisor` consumes packetized truth through the public agent facade
- crystallized interaction learning now exists as an advisory packet field

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

## Plugin contract summary

| Plugin | Current role | Current backend |
|---|---|---|
| `openmind-advisor` | slow-path public agent bridge + packet consumer | `POST /v3/agent/turn` plus planning/session helper APIs |
| `openmind-memory` | OpenClaw memory-slot bridge for recall/capture | `POST /v2/context/resolve`, `POST /v2/memory/capture` |
| `openmind-graph` | graph retrieval bridge | `POST /v2/graph/query` |
| `openmind-telemetry` | execution telemetry bridge | `POST /v2/telemetry/ingest` |

## Authority model

See also:

- `docs/contracts/ADR-005-openmind-openclaw-chatgptrest-authority-boundary-v1.md`
- `docs/contracts/2026-04-09_openmind_scope_surface_inventory_v1.md`

Short version:

- OpenClaw is the consumption/orchestration shell
- ChatgptREST is the production/truth substrate
- OpenMind is the constitutional / trace / policy layer

## Wake-up packet runtime contract

The canonical packet contract is:

- `docs/contracts/2026-04-09_wakeup_packet_contract_v1.md`

Current behavior:

- ChatgptREST compiles a wake-up packet inside `/v3/agent/turn`
- the packet is attached to `task_intake.available_inputs.wake_up_packet`
- prompt assembly renders a compact packet projection
- backend execution lanes receive the same packetized truth through the compiled prompt

This means OpenClaw does **not** need to become the durable-memory organizer in order to consume layered project truth.

## Crystallized learning status

Current status:

- interaction-learning writeback exists in ChatgptREST
- stable cross-session preferences can now be projected into `crystallized_learning`
- the crystal remains advisory only and explicitly lower priority than the authority anchor

This is a bounded Hermes-style borrowing, not a self-evolution runtime.

## Historical note

Older files remain historical:

- `docs/integrations/openclaw_cognitive_substrate.md`
- `docs/integrations/2026-04-09_openclaw_cognitive_substrate_runtime_contract_v2.md`

Use v3 as the canonical runtime contract after Phase 2/5 execution.
