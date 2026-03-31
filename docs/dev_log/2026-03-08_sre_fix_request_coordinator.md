# 2026-03-08 SRE Fix Request Coordinator

## What Changed

Implemented an incident-scoped Codex repair coordinator instead of a global `--resume` session:

- added lane-scoped Codex resume support in [`chatgptrest/core/codex_runner.py`](../../chatgptrest/core/codex_runner.py)
- added shared request builders in [`chatgptrest/core/sre_jobs.py`](../../chatgptrest/core/sre_jobs.py)
- added [`chatgptrest/executors/sre.py`](../../chatgptrest/executors/sre.py)
  - accepts `kind=sre.fix_request`
  - keeps one lane per incident/job/symptom
  - stores lane manifest + request/decision history under `state/sre_lanes/<lane_id>/`
  - runs a read-only Codex diagnosis step
  - optionally resumes the prior Codex lane for the same incident
  - routes into existing `repair.autofix` or `repair.open_pr`
  - links the produced report back into Issue Ledger when `issue_id` is provided
- wired `executor_for_job()` to resolve `sre.fix_request` and compatibility alias `sre.diagnose`
- added MCP helper `chatgptrest_sre_fix_request_submit`
- added `ops/start_sre_runner.sh` for a dedicated `sre.` worker
- documented the new job kind and runner in `docs/contract_v1.md` and `docs/runbook.md`

## Why

The goal was to automate the human “router” role:

- client/agent submits a repair request
- coordinator assembles fresh context
- memory is scoped to one incident lane, not the whole repository
- downstream action is explicit and auditable

This avoids building a single long-lived global Codex session while still preserving useful repair memory.

## Validation

Passed:

- `./.venv/bin/pytest -q tests/test_codex_runner.py`
- `./.venv/bin/pytest -q tests/test_sre_fix_request.py tests/test_mcp_sre_submit.py`
- `./.venv/bin/pytest -q tests/test_codex_runner.py tests/test_repair_check.py tests/test_mcp_repair_submit.py tests/test_sre_fix_request.py tests/test_mcp_sre_submit.py`
- `./.venv/bin/python -m py_compile chatgptrest/core/codex_runner.py chatgptrest/core/sre_jobs.py chatgptrest/executors/sre.py chatgptrest/executors/factory.py chatgptrest/mcp/server.py tests/test_sre_fix_request.py tests/test_mcp_sre_submit.py`

## Notes

- The coordinator is read-only by itself. Code-writing still goes through `repair.open_pr`.
- GitNexus use is best-effort and runner-scoped. `ops/start_sre_runner.sh` enables it with a dedicated npm cache path so the main workers are not forced to pay that startup cost.
- `sre.diagnose` remains accepted as an alias so older issue wording does not immediately break callers.
