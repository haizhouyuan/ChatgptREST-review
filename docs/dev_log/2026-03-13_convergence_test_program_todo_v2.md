# Convergence Test Program TODO

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Worktree: `/vol1/1000/projects/ChatgptREST/.worktrees/convergence-validation-program-20260313`  
Owner: Codex

Status: in_progress

This is the follow-up revision after adjudicating what should be absorbed from
`docs/dev_log/2026-03-13_convergence_test_plan_v1.md`.

---

## Objective

Produce the next version of the convergence validation design by absorbing only
the parts of `v1` that materially improve execution readiness.

Do not overwrite existing versions.

---

## Accepted Carry-Over Items

- [ ] add a time-bound current test baseline appendix
- [ ] add fixture infrastructure section:
  - `MockLLMConnector`
  - `InMemoryAdvisorClient`
  - `FeishuGatewaySimulator`
  - `MemoryManagerFixture`
- [ ] add a business-flow scenario catalog for:
  - Feishu -> answer
  - deep research -> report delivery
  - OpenClaw async flow
  - multi-turn memory continuity
  - planning lane lifecycle
- [ ] expand fault injection with network partition class scenarios
- [ ] add anti-accidental-pass rule to test-complete definition

---

## Explicit Non-Carry-Over Items

- [ ] do not hard-code route-count assertions like `advise_routes <= 2`
- [ ] do not assume unified public envelope before product contract is settled
- [ ] do not assume public task plane already exists on current master
- [ ] do not carry week-by-week schedule guesses into the design
- [ ] do not recommend `pytest tests/ -v` as the release-grade default path

---

## Deliverables

- [ ] `docs/dev_log/2026-03-13_convergence_test_plan_v3.md`
- [ ] `docs/dev_log/2026-03-13_convergence_test_matrix_v2.md`
- [ ] `docs/dev_log/2026-03-13_convergence_test_program_walkthrough_v2.md`
- [ ] meaningful commit(s)
- [ ] push branch update
- [ ] refresh PR context
- [ ] final closeout event for this revision

---

## Validation Targets

- path/reference sanity for all newly added cited assets
- doc coherence between `v3` and `matrix_v2`
- deterministic baseline still runnable from the current branch

Recommended command set:

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

---

## Commit Plan

- Commit 1: add follow-up TODO anchor
- Commit 2: add `plan_v3` + `matrix_v2`
- Commit 3: add `walkthrough_v2` and update PR handoff
