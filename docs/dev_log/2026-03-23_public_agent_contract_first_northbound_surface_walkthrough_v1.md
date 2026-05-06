# Public Agent Contract-First Northbound Surface Walkthrough v1

## What I changed

I exposed the existing canonical ingress objects on the northbound surfaces instead of adding more ad hoc top-level request fields.

The public MCP `advisor_agent_turn` tool now forwards:

- `task_intake`
- `contract_patch`

The repo CLI and the skill wrapper now accept JSON/file inputs for the same two objects and pass them through to `/v3/agent/turn`.

## Why this slice comes first

The backend already knows how to consume canonical intake and structured contract data.

The missing piece was northbound exposure:

- public MCP was still message-first
- CLI and the skill wrapper could not express canonical task contracts

This slice fixes that mismatch without changing runtime decision semantics yet.

## What is intentionally not solved here

- no same-session contract patch merge yet
- no clarify-policy changes yet
- no message parser yet
- no new observability fields yet

Those are handled in later slices of the package.
