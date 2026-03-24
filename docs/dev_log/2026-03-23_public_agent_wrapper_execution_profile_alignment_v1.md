# 2026-03-23 Public Agent Wrapper Execution Profile Alignment v1

## Summary

Aligned the repo's built-in `chatgptrest cli agent turn` surface and the `skills-src/chatgptrest-call` wrapper with the new high-level `execution_profile` contract for the public agent surface.

This closes the remaining adapter gap after `execution_profile=thinking_heavy` was added to the public MCP and `/v3/agent/turn`.

## Changes

- `chatgptrest/cli.py`
  - Added `--execution-profile` to `chatgptrest agent turn`
  - Updated `--depth` help text to include the `heavy` compatibility alias
  - Forwarded `execution_profile` into the `/v3/agent/turn` payload
- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
  - Added `--execution-profile`
  - Expanded `--depth` choices to accept `heavy` and `thinking_heavy`
  - Forwarded `--execution-profile` into the delegated `chatgptrest cli agent turn` command
- Tests
  - Added CLI coverage for `--execution-profile`
  - Added wrapper coverage for `--execution-profile` and `--depth heavy`

## Validation

Passed:

```bash
./.venv/bin/pytest -q tests/test_cli_improvements.py tests/test_skill_chatgptrest_call.py
python3 -m py_compile chatgptrest/cli.py skills-src/chatgptrest-call/scripts/chatgptrest_call.py tests/test_cli_improvements.py tests/test_skill_chatgptrest_call.py
PYTHONPATH=. ./.venv/bin/python ops/run_public_agent_mcp_validation.py
```

## Outcome

The public MCP-only high-level contract is now usable through:

- `chatgptrest agent turn --execution-profile thinking_heavy`
- `chatgptrest agent turn --depth heavy`
- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py --execution-profile thinking_heavy`
- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py --depth heavy`

This does not relax the low-level direct live ChatGPT ask guard.
