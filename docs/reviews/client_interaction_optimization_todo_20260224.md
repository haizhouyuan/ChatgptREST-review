# Client Interaction Optimization TODO — Closed Loop (2026-02-24)

## Background
From the full-route E2E batch (`docs/reviews/router_e2e_full_matrix_investment_agents_20260224.md`), client-side interaction pain points were clear:
- long-poll endpoints can exceed default CLI request timeout and trigger client exceptions;
- timeout exceptions in `jobs run/wait` were raised as hard failures, reducing automation reliability;
- global timeout naming (`--timeout-seconds`) was ambiguous versus job-level timeout flags.

## TODO Plan (and Completion Status)
1. `DONE` Expose explicit global request-timeout flag for client ergonomics.
- Added `--request-timeout-seconds` as first-class global CLI option.
- Kept legacy `--timeout-seconds` global alias for backward compatibility (hidden).

2. `DONE` Harden long-poll interaction behavior in CLI wait paths.
- Added client-timeout fallback for `jobs wait` and `jobs run`:
  - if wait call times out at client side, CLI now fetches `/v1/jobs/{job_id}` snapshot and returns structured output instead of hard crash;
  - output includes `client_wait_timed_out=true` and `client_wait_timeout_error` for diagnosability.

3. `DONE` Improve timeout diagnostics from transport layer.
- `_http_json_request` now catches `TimeoutError`/`socket.timeout` and returns actionable CLI error text:
  - hint to increase `--request-timeout-seconds` for long-poll routes.

4. `DONE` Add regression tests for the above behavior.
- Added tests for:
  - parser support of `--request-timeout-seconds`;
  - `jobs wait` timeout fallback;
  - `jobs run` timeout fallback;
  - existing CLI/skill/contract/wrapper/snapshot suites all green.

## Code Changes
- `chatgptrest/cli.py`
  - added `_is_timeout_like_error` helper
  - added `_wait_job_with_client_timeout_fallback`
  - hardened `_http_json_request` timeout handling
  - switched `jobs wait` / `jobs run` to timeout fallback path
  - added global `--request-timeout-seconds`
- `tests/test_cli_chatgptrestctl.py`
  - new tests for timeout fallback + global timeout flag parsing

## Verification
Executed:
```bash
./.venv/bin/pytest -q \
  tests/test_cli_chatgptrestctl.py \
  tests/test_skill_chatgptrest_call.py \
  tests/test_contract_v1.py \
  tests/test_wrapper_v1.py \
  tests/test_mcp_tool_registry_snapshot.py
```
Result:
- `64 passed`

## Outcome
- CLI interaction layer is now more resilient for AI-agent automation workflows over MCP/REST.
- Long-poll client timeouts are downgraded from crash to structured state handoff.
- Global timeout semantics are clearer, reducing operator misuse.

## Follow-up (Next TODO Batch)
1. Add explicit `client_timeout_policy` fields to CLI JSON output schema (documented contract for wrappers).
2. Add CLI `jobs run --cancel-on-client-timeout` policy switch (auto cleanup policy as opt-in).
3. Add end-to-end smoke that asserts timeout fallback path under simulated network stall.
