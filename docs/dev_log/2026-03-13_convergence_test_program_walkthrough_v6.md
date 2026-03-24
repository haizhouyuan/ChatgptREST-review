# Convergence Test Program Walkthrough

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Worktree: `/vol1/1000/projects/ChatgptREST/.worktrees/convergence-validation-program-20260313`  
Status: complete

This short follow-up walkthrough records one runner-polish correction made
immediately after tranche 3 landed.

---

## Why This Revision Exists

After `wave6` was promoted into the main convergence runner, the compile
baseline still covered:

- `ops/run_convergence_validation.py`

but not:

- `ops/run_convergence_live_matrix.py`

That left the new live-wave script outside the static compile baseline, which
was inconsistent with the rest of the runner contract.

---

## What Landed

Updated `COMPILE_TARGETS` in:

- `ops/run_convergence_validation.py`

so the convergence runner now compiles:

- `chatgptrest/api/app.py`
- `chatgptrest/api/routes_jobs.py`
- `chatgptrest/api/routes_advisor_v3.py`
- `ops/run_convergence_validation.py`
- `ops/run_convergence_live_matrix.py`

Also updated:

- `tests/test_convergence_validation_runner.py`

to assert that the compile command includes `ops/run_convergence_live_matrix.py`.

---

## Validation Performed

Executed:

```bash
python3 -m py_compile \
  ops/run_convergence_validation.py \
  ops/run_convergence_live_matrix.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_convergence_validation_runner.py
```

Result:

- passed

---

## Commit Sequence For This Revision

1. `test: include live matrix in convergence compile baseline`
2. pending at time of writing: walkthrough, PR refresh, and closeout

---

## PR Handling

This remains part of:

- `https://github.com/haizhouyuan/ChatgptREST/pull/160`

The purpose of this follow-up was not a new feature wave; it was to make the
runner’s static baseline accurately reflect the live-wave code that tranche 3
already introduced.
