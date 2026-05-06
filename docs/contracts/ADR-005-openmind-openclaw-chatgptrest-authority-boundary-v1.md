# ADR-005: OpenMind / OpenClaw / ChatgptREST Authority Boundary

**Status**: Draft v1  
**Date**: 2026-04-09  
**Depends on**: ADR-001 (State Model), ADR-003 (Identity), ADR-004 (Path SLA)

## Context

The current runtime topology is easy to misread if inspected at repo granularity only.

Code-verified facts on 2026-04-09:

- ChatgptREST ships the OpenClaw-side plugin packages in `openclaw_extensions/`.
- `openmind-advisor` is no longer a thin `/v2/advisor/*` bridge. The current plugin calls the public agent facade rooted at `POST /v3/agent/turn`, plus planning/session helper APIs.
- `openmind-memory` occupies the OpenClaw memory slot and bridges only recall/capture hooks. It is not a standalone durable-memory runtime.
- `openmind-graph` and `openmind-telemetry` are similarly bridge plugins into ChatgptREST APIs.
- historical integration docs still describe the 2026-03-08 shape and therefore understate the current authority split.

The architectural confusion is not primarily about missing infrastructure. It is about authority drift:

- which layer produces durable truth
- which layer consumes and presents that truth
- which layer defines audit/policy/trace contracts

## Decision

Authority is frozen by **object role and lifecycle stage**, not by repo name alone.

### Primary authority split

| Authority role | System | Scope |
|---|---|---|
| Fact production authority | ChatgptREST | structured memory, advisor runtime, planning tasks/checkpoints/handoff, evidence/artifacts, promotion/groundedness chain |
| Fact consumption authority | OpenClaw | user-facing session lifecycle, tool/executor orchestration, local memory assist, document-layer routing, answer delivery |
| Constitutional / audit authority | OpenMind | event schema, artifact ledger expectations, policy receipts, trace contract, naming of the cognitive substrate |

### Important refinement

For **front-end interactive runtime**, OpenClaw remains authoritative for:

- local session flow
- tool invocations
- orchestration of user-visible execution

For **slow-path durable records**, ChatgptREST remains authoritative for:

- task/session objects created through `/v3/agent/turn`
- planning task state
- durable memory / writeback receipts
- artifact and provenance surfaces

OpenMind does **not** currently imply a standalone runtime that supersedes ChatgptREST. In the present system it is the constitutional layer that defines how the substrate should be named, audited, and constrained.

## Object ownership

| Object | Produce / canonical write | Consume / present | Audit / policy |
|---|---|---|---|
| Slow-path advisor turn | ChatgptREST `/v3/agent/turn` | OpenClaw `openmind-advisor` | OpenMind trace/policy contract |
| Planning task / checkpoint / handoff | ChatgptREST | OpenClaw task/session tools | OpenMind artifact/receipt expectations |
| Durable memory | ChatgptREST memory services | OpenClaw memory plugin recall/capture hooks | OpenMind capture policy + provenance expectations |
| Graph query result | ChatgptREST graph services | OpenClaw graph tool | OpenMind query/policy semantics |
| Telemetry event | OpenClaw emits, ChatgptREST ingests/normalizes | dashboards / runtime consumers | OpenMind event schema / receipts |
| Project authority anchor (`_project_context.md`) | human-maintained source | ChatgptREST packet compiler, then OpenClaw consumes projection | OpenMind only defines receipt/provenance expectations |

## Rules that follow from this split

### 1. `openmind-*` plugins are bridges, not brain owners

- `openmind-advisor` is an OpenClaw bridge to ChatgptREST public agent surfaces.
- `openmind-memory` is a bridge for recall/capture hooks and the OpenClaw memory slot.
- `openmind-graph` and `openmind-telemetry` are bridge plugins as well.

They may format, scope, or guard requests, but they must not become the primary durable-memory or planning authority.

### 2. Human authority anchor stays above automatic recall

The priority order is frozen as:

```text
authority anchor > project memory > EvoMap knowledge > runtime heuristics
```

This applies whether the consumer is OpenClaw, ChatgptREST advisor runtime, or a later coding-agent wake-up packet.

### 3. OpenMind scope must be explicit

OpenMind should be described as:

- constitutional layer
- policy / trace / audit layer
- substrate naming layer

It should not claim independent ownership of advisor or memory runtime behavior unless a separate runtime is actually implemented.

### 4. Public agent facade is the current canonical slow-path bridge

For OpenClaw integration, the canonical advisor bridge is now:

- `POST /v3/agent/turn`
- related planning/session read surfaces
- session cancel surface

Legacy `/v2/advisor/*` endpoints remain part of ChatgptREST history and compatibility, but they are not the canonical OpenClaw slow-path contract anymore.

## Consequences

### Documentation

- canonical OpenClaw integration docs must describe the `/v3/agent/*` bridge and the new authority split
- older 2026-03-08 integration docs are historical snapshots, not current runtime truth

### Runtime design

- wake-up packet compilation belongs in ChatgptREST advisor/runtime surfaces, not inside OpenClaw plugins
- OpenClaw should consume packets and state, not become the durable memory owner
- project-scoped memory and recall improvements should enter the ChatgptREST substrate first

### Future work

- MemPalace-style wake-up packet discipline is compatible with this ADR
- Hermes-style skill crystallization is later-stage work and must consume audited substrate outputs rather than bypass them

## Non-goals

- deleting legacy `/v2/advisor/*` surfaces immediately
- claiming OpenMind is already a fully independent runtime
- moving all project intelligence into OpenClaw
