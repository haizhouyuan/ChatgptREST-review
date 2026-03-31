# 2026-03-23 Phase28 Premium Agent Blueprint Scoped Launch Gate Walkthrough v2

## Why v2 Exists

`report_v1` failed because the gate assumed the live maintenance direct-REST escape hatch would be available and that coding-agent blocking would surface as one specific error code.

The live system is stricter than that:

- coding-agent direct REST is blocked at the live public surface
- the observable error can be either `client_not_allowed` or `coding_agent_direct_rest_blocked`
- maintenance direct REST is not part of the blueprint scoped-launch guarantee

That means the correct scoped gate is:

- prove coding agents are technically blocked from direct REST
- do not require a live maintenance exception to stay open

## v2 Outcome

`report_v2` is `8/8` green and matches the real blueprint boundary:

- northbound public MCP default
- live coding-agent REST block
- live workspace auth readiness
- heavy execution explicit-only closure
- public-agent live cutover
- public-agent effects/delivery surface
- premium default-path regression

## Interpretation

This is the final scoped-launch proof for the blueprint itself.
