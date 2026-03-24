# 2026-03-17 Agent V3 Auth And BI Validation Rerun v1

## Scope

Repair the `public advisor-agent` business-validation blockers that were still preventing sign-off:

- `/v3/agent/*` auth had been disabled for testing
- `agent_turn()` initialized advisor runtime before validating `message`
- `tests/test_routes_agent_v3.py` and `tests/test_bi14_fault_handling.py` were not hermetic
- `BI-06` same-session follow-up continuity still lacked automated coverage
- `tests/test_bi09_mcp_business_pass.py` still emitted `PytestReturnNotNoneWarning`

Then rerun the business validation locally and via `cc-sessiond`.

## Code Changes

### 1. Restore public auth on `/v3/agent/*`

File:
- `chatgptrest/api/routes_agent_v3.py`

Change:
- restored router dependencies to include `_require_agent_auth`
- retained `_require_agent_rate_limit`

Result:
- `/v3/agent/turn` now correctly distinguishes:
  - `503` when no auth secret is configured
  - `401` when auth is configured but credentials are missing/invalid

### 2. Validate `message` before initializing advisor runtime

File:
- `chatgptrest/api/routes_agent_v3.py`

Change:
- moved `state = _advisor_runtime()` below the `message is required` guard

Result:
- empty-body requests now return the intended `400 {"error":"message is required"}`
- route smoke tests no longer depend on a fully initialized advisor runtime just to validate request shape

### 3. Make `agent_v3` and `BI-14` tests hermetic

Files:
- `tests/test_routes_agent_v3.py`
- `tests/test_bi14_fault_handling.py`
- `tests/test_agent_v3_routes.py`

Changes:
- added fake controller/runtime helpers
- stubbed direct-job / consultation / cancel pathways in route smoke tests
- removed dependence on live advisor runtime for business-surface verification

Result:
- these tests now validate public contract behavior rather than timing out inside real runtime initialization

### 4. Add automated BI-06 continuity coverage

File:
- `tests/test_agent_v3_routes.py`

New test:
- `test_agent_turn_same_session_followup_preserves_continuity`

What it verifies:
- a second `/v3/agent/turn` with the same `session_id` stays on the same session
- controller receives the same `session_id` twice
- session status reflects the latest answer after follow-up

### 5. Remove MCP BI-09 pytest warnings

File:
- `tests/test_bi09_mcp_business_pass.py`

Change:
- removed explicit `return True` from the pytest test functions

Result:
- `PytestReturnNotNoneWarning` no longer appears during the MCP business pass

## Local Validation

Important environment note:

- the worktree-local `.venv` at `/vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317/.venv` is incomplete for broader app tests
- it is missing at least:
  - `jinja2`
  - `langgraph.checkpoint.sqlite`
- therefore broader verification used the shared main-repo environment:
  - `/vol1/1000/projects/ChatgptREST/.venv`

### Route and business-surface gate

Command:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_routes_agent_v3.py \
  tests/test_agent_v3_routes.py \
  tests/test_bi14_fault_handling.py \
  tests/test_bi09_mcp_business_pass.py \
  tests/test_openclaw_cognitive_plugins.py
```

Result:
- pass

### Broader OpenClaw/OpenMind gate

Command:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_mcp_advisor_tool.py \
  tests/test_advisor_v3_end_to_end.py \
  tests/test_skill_chatgptrest_call.py \
  tests/test_cli_improvements.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_routes_advisor_v3_security.py
```

Result:
- pass

## cc-sessiond Rerun

Execution backend:
- `sdk_official`

Runner environment:
- Python: `/vol1/1000/projects/ChatgptREST/.venv/bin/python`
- worktree cwd: `/vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317`
- test commands inside Claude Code used the shared main-repo `.venv`

Artifacts:
- root: `/tmp/cc-sessiond-agent-validation-oa2pe_qc`
- cc-sessiond session id: `cf8a8a589338`
- Claude Code backend session id: `4dbba560-b9df-4ec0-a5b6-5fa1331c5983`

Claude Code result summary:
- status: `passed`
- both test batches completed with `EXIT_CODE: 0`
- Claude independently validated:
  - `/v3/agent` auth now distinguishes `503` vs `401`
  - BI-06 continuity is now covered
  - BI-14 is hermetic
  - BI-09 no longer emits `PytestReturnNotNoneWarning`
  - OpenClaw plugin still targets `/v3/agent/turn` and forwards `account_id/thread_id/agent_id`

SDK usage/cost:
- total cost: `$0.9918675`
- turns: `11`

## Outcome

This repair round closes the blockers from the earlier BI review:

- auth is back on
- empty request validation is correct
- BI-06 is automated
- BI-14 no longer depends on real runtime
- BI-09 runs cleanly
- both local and `cc-sessiond` validation passed

Remaining non-product caveat:
- the feature worktree’s private `.venv` is still incomplete for broader app tests; shared `.venv` was used instead
