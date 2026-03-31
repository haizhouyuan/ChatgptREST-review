# Phase 18 Execution Delivery Gate Pack

## Goal

Add a scoped execution-delivery gate for the public `/v3/agent/*` facade so release readiness is not limited to:

- semantic validation
- route validation
- auth / trace validation

This phase proves the public facade can still carry covered requests through terminal delivery behavior.

## Covered Checks

1. `controller_wait_to_terminal_delivery`
   - delayed controller result
   - final answer delivery
   - terminal session projection
2. `direct_image_job_delivery`
   - direct image job branch
   - provenance job id
3. `consult_delivery_completion`
   - consultation completion response
   - consultation provenance
4. `deferred_stream_terminal_done`
   - deferred turn acceptance
   - SSE `done` terminal session payload
5. `persisted_session_rehydration`
   - persisted session survives router recreation

## Explicit Boundary

This pack is intentionally scoped to the public facade delivery chain.

It is not:

- external provider replay proof
- OpenClaw dynamic replay proof
- heavy execution approval
- full-stack deployment proof
