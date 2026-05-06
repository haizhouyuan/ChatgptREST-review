# Convergence Test Program Walkthrough

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Worktree: `/vol1/1000/projects/ChatgptREST/.worktrees/convergence-validation-program-20260313`  
Status: complete

---

## Goal

Produce a versioned, release-grade validation design for the product convergence effort without overwriting any prior test-plan draft.

The intent was to turn the existing planning material into a document set that is actually executable:

- a persistent TODO anchor so the work survives context compression
- a main validation-program document that defines waves, gates, environments, simulations, and release criteria
- a matrix that maps the design to current repo assets and known gaps

---

## Why A New Version Instead of Editing `v1`

The repository already had `docs/dev_log/2026-03-13_convergence_test_plan_v1.md`.  
Per repository rules, that file was kept intact.

I created additive documents because:

- `v1` is a strong draft, but it is still mostly a "what to test" outline
- the convergence effort needs a stronger operational frame:
  - validation environments
  - wave sequencing
  - simulation catalog
  - evidence model
  - release gates
  - cadence and ownership
- the new document set is intended to be execution-ready rather than purely descriptive

---

## Deliverables

Created:

- `docs/dev_log/2026-03-13_convergence_test_program_todo_v1.md`
- `docs/dev_log/2026-03-13_convergence_test_plan_v2.md`
- `docs/dev_log/2026-03-13_convergence_test_matrix_v1.md`
- `docs/dev_log/2026-03-13_convergence_test_program_walkthrough_v1.md`

---

## Design Decisions

### 1. Keep deterministic and live validation separate

The largest execution mistake in this repo would be treating "live smoke passed once" as proof of convergence.

The design therefore separates:

- deterministic contract and lifecycle checks
- local integration checks
- live provider execution
- fault injection and restart recovery
- soak / shadow / canary rollout

### 2. Use waves, not a flat checklist

The test plan is structured as Wave 0 through Wave 7 so release gating is explicit:

- startup honesty first
- deterministic contract next
- durable lifecycle before live provider work
- channel parity before real rollout
- fault injection before canary

### 3. Require evidence, not just pass/fail

Each wave is tied to expected evidence paths and artifact types.  
This is necessary because the system can otherwise appear healthy while lifecycle or control-plane truth is drifting.

### 4. Treat current repo assets as the baseline, not as perfect coverage

The design does not pretend the repo lacks tests. It explicitly builds on:

- contract tests
- advisor lifecycle tests
- security tests
- cognitive and memory tests
- plugin and gateway tests
- smoke and monitor scripts

At the same time, it marks missing areas such as:

- cross-entry envelope parity
- durable adjunct-store restart checks
- fault-injection playbooks
- knowledge authority precedence tests

---

## Validation Performed During This Documentation Task

### Static Check

Executed:

```bash
python3 -m py_compile chatgptrest/api/app.py chatgptrest/api/routes_advisor_v3.py
```

Result:

- passed

### Deterministic Baseline

Executed from the feature worktree using the shared main-repo virtualenv:

```bash
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

Result:

- passed

Note:

- the worktree itself does not have a local `.venv`, so the main repo virtualenv was used intentionally
- this is an environment detail, not a product validation failure

### Live Validation

Not executed in this documentation task:

- `ops/run_execution_plane_parity_smoke.py`
- `ops/antigravity_router_e2e.py`
- `ops/run_soak.sh`
- `ops/run_monitor_12h.sh`

Reason:

- these belong to later release gates in the design
- they depend on live browser/provider/runtime state and should run as part of the actual convergence execution cycle, not as a documentation-only branch side effect

---

## Commit Sequence

1. `docs: add convergence test program todo anchor`
2. `docs: add convergence validation program and matrix`
3. `docs: add convergence test program walkthrough`

---

## Expected PR Scope

This branch is documentation-only and should open a PR that contains:

- a new TODO anchor for the workstream
- a `v2` test plan that upgrades the draft into an execution design
- a matrix tying the design to current repo assets and missing work
- this walkthrough for traceability

It should not include unrelated runtime or knowledge artifacts.

## PR Result

- Branch pushed: `origin/codex/convergence-validation-program-20260313`
- PR opened: `https://github.com/haizhouyuan/ChatgptREST/pull/160`
- PR title: `docs: add release-grade convergence validation program`

---

## Recommended PR Title

`docs: add release-grade convergence validation program`

---

## Closeout Reminder

Completed:

- branch pushed
- PR opened
- `/vol1/maint/ops/scripts/agent_task_closeout.sh --repo /vol1/1000/projects/ChatgptREST --agent codex --status completed --summary "authored convergence validation program docs and opened PR #160"`

This walkthrough is the durable handoff record for why the document set exists, how it was validated, and where the review thread now lives.
