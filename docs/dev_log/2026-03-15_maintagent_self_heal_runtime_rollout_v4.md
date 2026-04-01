## Scope

This follow-up closed a live failure discovered during maintagent business validation:

- `sre.fix_request` for issue `iss_2460873ff05e4261bd2af58411b56637`
- repeated every 120 seconds
- never produced a final report

The issue itself already said the problem was an `IdempotencyCollision` against an existing downstream repair job, but the executor still escalated into the slow Codex path.

## Root Cause

`chatgptrest/executors/sre.py` only had heuristic fast paths for runtime/UI signatures such as:

- `TargetClosedError`
- blocked network state
- attachment contract failures
- wait stalls

For issue-ledger entries whose `raw_error` already includes:

- `IdempotencyCollision`
- `existing_job_id=<repair job>`

the executor still built a full Codex diagnosis prompt. On live traffic this repeatedly hit the 120-second worker execution window and got reclaimed, creating a pseudo-stuck `sre.fix_request`.

## Change

Updated:

- `chatgptrest/executors/sre.py`

to add an issue-payload fast path:

- parse `existing_job_id` from issue `raw_error`
- verify that the referenced job still exists and is `repair.autofix` or `repair.open_pr`
- short-circuit to a heuristic decision
- reuse the existing downstream repair/open_pr job directly instead of creating another one

Added regression coverage in:

- `tests/test_sre_fix_request.py`

for the exact shape of this failure.

## Validation

Regression suite:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_sre_fix_request.py \
  tests/test_maint_daemon_stuck_watchdog.py \
  tests/test_repair_autofix_codex_fallback.py \
  tests/test_issue_targets.py \
  tests/test_maint_bootstrap_memory.py
```

Expected result:

- `20 passed`

## Operational Outcome

This removes an entire class of fake-stuck `sre.fix_request` jobs. When an issue already points at an equivalent downstream repair job, maintagent now:

- answers quickly
- preserves lane memory
- avoids redundant Codex work
- avoids creating duplicate repair jobs
- returns the existing downstream job as the correct next action
