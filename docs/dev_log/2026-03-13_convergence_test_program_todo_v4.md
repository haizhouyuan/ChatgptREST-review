# Convergence Test Program TODO

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Worktree: `/vol1/1000/projects/ChatgptREST/.worktrees/convergence-validation-program-20260313`  
Owner: Codex

Status: in_progress

This revision continues the convergence validation program after the first
execution tranche.

---

## Objective

Close the next repository-local gaps in the validation plan by landing:

- startup honesty evidence and route inventory
- startup manifest propagation into readiness
- an executable convergence validation runner that emits an evidence bundle
- tests for the new control-plane behavior and runner

Do not overwrite existing versions.

---

## Scope For This Revision

- [ ] record startup router load results and route inventory on app boot
- [ ] surface router-load failures through `readyz`
- [ ] add startup honesty regression tests
- [ ] add an ops runner that executes curated convergence waves and writes an
      evidence bundle
- [ ] add tests for the runner plan and artifact generation
- [ ] run focused and expanded validation
- [ ] commit each meaningful stage
- [ ] refresh PR #160
- [ ] record walkthrough and closeout

---

## Working Notes

- `create_app` has critical blast radius; change only metadata and readiness
  integration, not unrelated auth or route behavior.
- Existing repo tests already cover many Wave 3/4 edges; the missing piece is
  bundling them into a repeatable program with stored evidence.
- `readyz` is the correct place to reject fake readiness when boot recorded a
  core router failure.

---

## Planned Deliverables

- [ ] startup manifest support in `chatgptrest/api/app.py`
- [ ] readiness startup-check support in `chatgptrest/api/routes_jobs.py`
- [ ] `ops/run_convergence_validation.py`
- [ ] startup honesty tests
- [ ] validation runner tests
- [ ] `docs/dev_log/2026-03-13_convergence_test_program_walkthrough_v4.md`

---

## Validation Target

Recommended command set for this revision:

```bash
python3 -m py_compile \
  chatgptrest/api/app.py \
  chatgptrest/api/routes_jobs.py \
  chatgptrest/api/routes_advisor_v3.py \
  ops/run_convergence_validation.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_api_startup_smoke.py \
  tests/test_ops_endpoints.py \
  tests/test_convergence_validation_runner.py

/vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/run_convergence_validation.py \
  --output-dir artifacts/release_validation/convergence_validation_local \
  --include-wave4
```

---

## Commit Plan

- Commit 1: add tranche todo v4
- Commit 2: add startup manifest and runner implementation + tests
- Commit 3: add walkthrough v4, refresh PR, and closeout
