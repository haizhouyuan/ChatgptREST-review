# Convergence Test Program TODO

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Worktree: `/vol1/1000/projects/ChatgptREST/.worktrees/convergence-validation-program-20260313`  
Owner: Codex

Status: in_progress

---

## Objective

Produce a release-grade, versioned validation program for the product convergence effort:

- keep the existing `2026-03-13_convergence_test_plan_v1.md` intact
- author an independent, fuller design version with explicit execution waves
- include a complete test plan with actual simulation strategy, evidence paths, and release gates
- keep a walkthrough record of how the document set was produced and validated
- push a dedicated feature branch and open a PR

---

## Deliverables

- [x] `docs/dev_log/2026-03-13_convergence_test_plan_v2.md`
- [x] `docs/dev_log/2026-03-13_convergence_test_matrix_v1.md`
- [x] `docs/dev_log/2026-03-13_convergence_test_program_walkthrough_v1.md`
- [x] Git commits for each meaningful stage
- [x] Remote branch push
- [x] PR opened against `master`
- [x] Closeout executed

---

## Memory Anchors

### Scope Rules

- Do not overwrite any existing `_v1.md` document.
- Treat `2026-03-13_convergence_test_plan_v1.md` as input, not the final answer.
- Keep the new test program grounded in current repo assets: `tests/`, `ops/`, `docs/contract_v1.md`, `docs/runbook.md`.
- Separate deterministic tests from live/provider-dependent tests.
- The plan must prove:
  - no fake health
  - no fake convergence
  - no fake success

### Required Content

- validation principles and target state
- environment matrix
- wave-by-wave execution plan
- test catalog by capability domain
- actual simulation catalog for failures and boundary conditions
- evidence and artifact collection rules
- release exit criteria
- ownership / cadence / rerun policy

---

## Validation Commands

Run after the doc set is written:

```bash
python3 -m py_compile chatgptrest/api/app.py chatgptrest/api/routes_advisor_v3.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_api_startup_smoke.py \
  tests/test_contract_v1.py \
  tests/test_routes_advisor_v3_security.py \
  tests/test_advisor_api.py \
  tests/test_advisor_orchestrate_api.py \
  tests/test_advisor_runs_replay.py \
  tests/test_cognitive_api.py \
  tests/test_openclaw_cognitive_plugins.py
```

Executed:

- [x] `python3 -m py_compile chatgptrest/api/app.py chatgptrest/api/routes_advisor_v3.py`
- [x] `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_api_startup_smoke.py tests/test_contract_v1.py tests/test_routes_advisor_v3_security.py tests/test_advisor_api.py tests/test_advisor_orchestrate_api.py tests/test_advisor_runs_replay.py tests/test_cognitive_api.py tests/test_openclaw_cognitive_plugins.py`

Optional live checks to reference in the design:

```bash
PYTHONPATH=. ./.venv/bin/python ops/run_execution_plane_parity_smoke.py
bash ops/run_soak.sh
bash ops/run_monitor_12h.sh
```

---

## Commit Plan

- Commit 1: add TODO anchor
- Commit 2: add main design doc + test matrix
- Commit 3: add walkthrough and PR context, then push/open PR

Current state:

- [x] Commit 1 completed
- [x] Commit 2 completed
- [x] Commit 3 completed

---

## Exit Checklist

- [ ] New documents are versioned and additive
- [ ] All file references in docs resolve to current repo assets
- [ ] Validation commands were actually executed or explicitly marked as optional/live
- [ ] PR body summarizes scope, artifacts, and validation
- [ ] Closeout script completed

Progress snapshot:

- [x] New documents are versioned and additive
- [x] All file references in docs resolve to current repo assets
- [x] Validation commands were actually executed or explicitly marked as optional/live
- [x] PR body summarizes scope, artifacts, and validation
- [x] Closeout script completed

## Final References

- Remote branch: `origin/codex/convergence-validation-program-20260313`
- PR: `https://github.com/haizhouyuan/ChatgptREST/pull/160`
- Closeout summary: `authored convergence validation program docs and opened PR #160`
