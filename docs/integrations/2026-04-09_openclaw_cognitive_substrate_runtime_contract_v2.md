# OpenClaw Cognitive-Substrate Runtime Contract v2

Date: 2026-04-09
Status: current canonical integration contract

## Why this file exists

The older integration note from 2026-03-08 captured an earlier topology.

It is still useful as history, but it is no longer the canonical description of
the current runtime. In particular:

- `openmind-advisor` is no longer described accurately if treated as a `/v2/advisor/*` bridge
- plugin authority is easy to overstate unless current ownership is spelled out explicitly

This file is the current canonical contract. The older file remains as a
historical snapshot.

## Current topology

The current chain is:

```text
OpenClaw runtime -> openmind-* plugins -> ChatgptREST APIs -> execution / memory / graph / telemetry substrate
```

This is not a claim that OpenClaw owns durable memory or planning truth.

## Plugin contract summary

| Plugin | Current role | Current backend |
|---|---|---|
| `openmind-advisor` | slow-path public agent bridge | `POST /v3/agent/turn` plus planning/session helper APIs |
| `openmind-memory` | OpenClaw memory-slot bridge for recall/capture | `POST /v2/context/resolve`, `POST /v2/memory/capture` |
| `openmind-graph` | graph retrieval bridge | `POST /v2/graph/query` |
| `openmind-telemetry` | execution telemetry bridge | `POST /v2/telemetry/ingest` |

## Authority model

See also:

- `docs/contracts/ADR-005-openmind-openclaw-chatgptrest-authority-boundary-v1.md`

Short version:

- OpenClaw is the consumption/orchestration shell
- ChatgptREST is the production/truth substrate
- OpenMind is the constitutional / trace / policy layer

That means:

- OpenClaw remains authoritative for front-end session flow and user-visible orchestration
- ChatgptREST remains authoritative for durable slow-path task/session/checkpoint/memory truth
- OpenMind naming and policy should not be read as proof of an independent runtime unless one is actually implemented

## Plugin-specific notes

### `openmind-advisor`

- canonical plugin README: `openclaw_extensions/openmind-advisor/README.md`
- current role is broader than "research/report" only
- the plugin now participates in:
  - session continuity
  - planning task continuation/status
  - session lookup/cancel
  - public answer-first slow-path delivery

### `openmind-memory`

- occupies the OpenClaw memory slot
- performs recall on `before_agent_start`
- performs bounded capture on `agent_end`
- does **not** become the durable-memory authority

### `openmind-graph`

- exposes first-class graph query to OpenClaw
- should be treated as a retrieval bridge, not as a separate graph system

### `openmind-telemetry`

- sends execution events to ChatgptREST ingest
- should be treated as a bridge into the audit substrate

## Installation / rebuild entrypoints

Primary install staging:

- `scripts/install_openclaw_cognitive_plugins.py`

Current rebuild/source of truth:

- `scripts/rebuild_openclaw_openmind_stack.py`

Current plugin load snapshot:

- `openmind-advisor`
- `openmind-memory`
- `openmind-graph`
- `openmind-telemetry`

## Historical note

The older file:

- `docs/integrations/openclaw_cognitive_substrate.md`

is retained as a 2026-03-08 historical snapshot. Do not use it as the primary
reference for current runtime ownership or current `openmind-advisor` backend
shape.
