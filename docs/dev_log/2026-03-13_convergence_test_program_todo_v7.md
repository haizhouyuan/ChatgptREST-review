# Convergence Test Program TODO

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Worktree: `/vol1/1000/projects/ChatgptREST/.worktrees/convergence-validation-program-20260313`  
Owner: Codex

Status: in_progress

This revision continues the convergence validation program after auditing the
antigravity-authored L5-L7 tranche and landing the tranche-6 runner fixes.

Do not overwrite existing versions.

---

## Objective

Close the remaining executable gap between "the plan includes Wave 6 live
validation" and "the runner can actually execute it from a normal shell on this
host".

Produce one refreshed release-validation bundle that includes:

- deterministic waves
- business-flow simulations
- fault injection
- live provider validation
- bounded soak / governance waves

---

## Audit Findings Driving This Revision

- [ ] antigravity's L5-L7 tests are real, committed, and passing, but that by
      itself does not complete the release-grade plan
- [ ] the current shell does not export `CHATGPTREST_API_TOKEN`, even though the
      host-standard env file `~/.config/chatgptrest/chatgptrest.env` does have
      shared ChatgptREST tokens
- [ ] `ops/run_convergence_live_matrix.py` currently skips when tokens are not
      already present in process env and does not discover the shared env file
- [ ] full-bundle evidence exists for deterministic/fault/soak waves, but the
      live wave still needs a clean, repeatable execution path from the runner
- [ ] this tranche needs a written adjudication of what antigravity completed
      correctly and what still required Codex follow-through

---

## Scope For This Revision

- [ ] add shared-env discovery for live convergence validation
- [ ] add regression tests for env discovery and include-live bundle execution
- [ ] run a refreshed convergence bundle with `wave0-8` enabled
- [ ] inspect live-wave provider outcomes and classify them honestly
- [ ] record the antigravity audit + tranche-7 implementation walkthrough
- [ ] refresh PR #160 context
- [ ] run closeout

---

## Planned Deliverables

- [ ] `ops/run_convergence_live_matrix.py`
- [ ] `tests/test_convergence_live_matrix.py`
- [ ] `tests/test_convergence_validation_runner.py`
- [ ] `artifacts/release_validation/convergence_validation_tranche7_full/`
- [ ] `docs/dev_log/2026-03-13_convergence_test_program_walkthrough_v7.md`

---

## Validation Target

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_convergence_live_matrix.py \
  tests/test_convergence_validation_runner.py

CHATGPTREST_SOAK_SECONDS=5 \
  /vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/run_convergence_validation.py \
  --include-wave4 \
  --include-wave5 \
  --include-live \
  --include-fault \
  --include-soak \
  --output-dir \
  artifacts/release_validation/convergence_validation_tranche7_full
```

---

## Commit Plan

- Commit 1: add todo v7 anchor
- Commit 2: enable live env discovery + tests
- Commit 3: add walkthrough v7, refresh PR context, and closeout
