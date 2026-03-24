# Convergence Test Program TODO

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Worktree: `/vol1/1000/projects/ChatgptREST/.worktrees/convergence-validation-program-20260313`  
Owner: Codex

Status: in_progress

This revision continues the convergence validation program after the
antigravity-authored L5-L7 test tranche landed.

---

## Objective

Turn the newly added L5-L7 tests into real release-validation coverage and fix
the concrete quality gaps found during audit.

Do not overwrite existing versions.

---

## Audit Findings Driving This Revision

- [ ] `ops/run_convergence_validation.py` does not execute the new L5
      business-flow suite at all
- [ ] `ops/run_convergence_validation.py` does not execute the new L6
      resilience suite inside Wave 7
- [ ] Wave 8 currently runs only the soak script and omits deterministic
      shadow/canary governance tests
- [ ] `test_zero_byte_db_handled()` accepts both success and failure, which
      weakens the fault-recovery assertion
- [ ] `test_working_memory_capacity_enforcement()` is too loose and did not
      catch a real working-memory turn-pair eviction bug
- [ ] `MemoryManager.add_conversation_turn()` evicts only one record while each
      turn writes two records

---

## Scope For This Revision

- [ ] fix working-memory turn-pair eviction semantics
- [ ] tighten L5/L6 tests so they fail when the target behavior is broken
- [ ] add Wave 5 to the convergence validation runner
- [ ] expand Wave 7 to cover the new restart / DB corruption / partition suite
- [ ] expand Wave 8 to include deterministic shadow/canary governance tests
- [ ] update runner tests for the new wave layout and flags
- [ ] run curated validation for changed production and runner scope
- [ ] commit each meaningful stage
- [ ] refresh PR #160 context
- [ ] record walkthrough and closeout

---

## Planned Deliverables

- [ ] `chatgptrest/kernel/memory_manager.py`
- [ ] strengthened L5/L6 regression tests
- [ ] updated `ops/run_convergence_validation.py`
- [ ] updated `tests/test_convergence_validation_runner.py`
- [ ] `docs/dev_log/2026-03-13_convergence_test_program_walkthrough_v7.md`

---

## Validation Target

Recommended command set for this revision:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_business_flow_multi_turn.py \
  tests/test_db_corruption_recovery.py \
  tests/test_restart_recovery.py \
  tests/test_network_partition.py \
  tests/test_shadow_mode.py \
  tests/test_canary_routing.py \
  tests/test_convergence_validation_runner.py
```

Expanded runner validation after green local fixes:

```bash
python3 -m py_compile \
  chatgptrest/kernel/memory_manager.py \
  ops/run_convergence_validation.py

/vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/run_convergence_validation.py \
  --include-wave4 \
  --include-wave5 \
  --include-fault
```

---

## Commit Plan

- Commit 1: add todo v6 anchor
- Commit 2: fix memory turn-pair eviction + tighten L5/L6 tests
- Commit 3: wire L5/L6/L7 coverage into convergence runner
- Commit 4: add walkthrough v7, refresh PR context, and closeout
