# 2026-03-23 Public Agent Wrapper Execution Profile Alignment Walkthrough v1

## Why

The public MCP and `/v3/agent/turn` already supported `execution_profile=thinking_heavy`, but the repo's own CLI and skill wrapper still only exposed `depth=light|standard|deep`.

That meant the core public contract worked, but local wrapper callers could not explicitly trigger it.

## What I changed

1. Extended `chatgptrest agent turn` with a new `--execution-profile` flag.
2. Left `depth` in place, but documented `heavy` as the compatibility alias.
3. Extended `chatgptrest_call.py` to accept both:
   - `--execution-profile thinking_heavy`
   - `--depth heavy`
4. Added regression tests for both adapters.
5. Re-ran public MCP live validation to ensure the wrapper-only change did not regress the service.

## Scope

This is an adapter-surface alignment only.

It does not:

- change public MCP auth
- change `/v3/agent/turn` routing semantics
- open low-level `/v1/jobs` direct live ask
- change heavy execution lane policy
