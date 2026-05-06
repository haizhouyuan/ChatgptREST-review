# Phase 12 Core Ask Launch Gate v1

## Goal

Aggregate the completed validation phases into a single launch gate for the
 current `planning/research` ask stack.

This phase answers a narrower question than overall product launch:

> Is the current core ask path validated strongly enough to ship, excluding
> public agent MCP usability and strict ChatGPT Pro smoke enforcement?

## Scope

This launch gate checks:

- Phase 7 front-door business-sample semantic validation
- Phase 8 multi-ingress business-sample semantic validation
- Phase 9 `/v3/agent/turn` public-route validation
- Phase 10 controller parity for covered canonical pack routes
- Phase 11 targeted branch-family validation
- live health on:
  - `GET /healthz`
  - `GET /v2/advisor/health`

## Explicit Exclusions

- public agent MCP usability gate
- strict ChatGPT Pro smoke blocking
- OpenClaw dynamic replay
- full-stack execution delivery validation

## Implementation

Core gate:

- [core_ask_launch_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/core_ask_launch_gate.py)

Runner:

- [run_core_ask_launch_gate.py](/vol1/1000/projects/ChatgptREST/ops/run_core_ask_launch_gate.py)

Tests:

- [test_core_ask_launch_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_core_ask_launch_gate.py)

## Acceptance

Phase 12 passes only when:

- every required validation artifact has `num_failed=0`
- each artifact also satisfies its expected coverage floor
- live API health checks return healthy status
- all exclusions remain explicit, not silently assumed covered
