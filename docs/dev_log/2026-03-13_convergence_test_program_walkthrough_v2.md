# Convergence Test Program Walkthrough

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Worktree: `/vol1/1000/projects/ChatgptREST/.worktrees/convergence-validation-program-20260313`  
Status: complete

This walkthrough records the follow-up revision that absorbed selected items
from `docs/dev_log/2026-03-13_convergence_test_plan_v1.md` into the current
convergence validation program.

---

## Why This Revision Exists

The first document set on this branch established the governance skeleton:

- environments
- waves
- release gates
- evidence model

After re-reading `v1`, I concluded that its best content was not the top-level
structure. The best content was the concrete execution detail:

- fixture ideas
- business-flow scenario design
- network partition and dependency-loss simulations
- the implicit demand that tests must be able to fail meaningfully

This revision exists to absorb those parts without importing `v1`'s weaker
assumptions.

---

## Accepted From `v1`

Accepted and incorporated into the new design:

1. a time-bound current test baseline snapshot
2. shared fixture infrastructure:
   - `MockLLMConnector`
   - `InMemoryAdvisorClient`
   - `FeishuGatewaySimulator`
   - `MemoryManagerFixture`
3. a first-class business-flow simulation catalog:
   - Feishu -> answer
   - deep research -> delivery
   - OpenClaw async flow
   - multi-turn memory continuity
   - planning lane lifecycle
4. network partition and dependency-loss fault classes
5. the rule that critical tests must be able to fail when target behavior is broken

---

## Rejected From `v1`

Rejected and intentionally not carried over:

1. route-count assertions such as `advise_routes <= 2`
2. a forced unified public response envelope before product contract decisions land
3. an assumption that a public task plane already exists on current master
4. week-by-week execution guesses
5. `pytest tests/ -v` as the release-grade default execution mode

These would make the plan look more concrete while actually baking in unstable
or incorrect assumptions.

---

## New Deliverables

Created in this revision:

- `docs/dev_log/2026-03-13_convergence_test_program_todo_v2.md`
- `docs/dev_log/2026-03-13_convergence_test_plan_v3.md`
- `docs/dev_log/2026-03-13_convergence_test_matrix_v2.md`
- `docs/dev_log/2026-03-13_convergence_test_program_walkthrough_v2.md`

---

## Validation Performed

### Static Check

Executed:

```bash
python3 -m py_compile chatgptrest/api/app.py chatgptrest/api/routes_advisor_v3.py
```

Result:

- passed

### Deterministic Baseline

Executed:

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

### Reference Sanity

Manually checked that the new `v3` plan and `matrix_v2` only reference assets
that currently exist in this repository or in the already-created versioned doc
set on this branch.

Result:

- passed

---

## Design Outcome

The validation program is stronger after this revision because it now has both:

- governance structure from `v2`
- concrete implementation hooks from `v1`

The resulting plan is now better balanced:

- abstract enough to survive product evolution
- concrete enough to drive implementation of the next test suites

That balance is what the branch was missing before this revision.

---

## Commit Sequence For This Revision

1. `docs: add convergence test program todo v2`
2. `docs: add convergence validation plan v3`
3. pending at time of writing: walkthrough and PR refresh

---

## PR Handling

This revision intentionally updates the existing branch and PR rather than
opening a second competing PR for the same workstream.

Target PR:

- `https://github.com/haizhouyuan/ChatgptREST/pull/160`

Reason:

- keeps the history of the validation-program work in one review thread
- avoids parallel PR drift on the same design topic
- keeps versioned documents additive inside one branch lineage

---

## Next Expected Step

After this walkthrough is committed:

- push the branch update
- refresh PR #160 with a summary of what `v3` adds
- emit a final closeout event for this revision
