# Self-Heal Governance And Export Reconciliation Walkthrough v1

Date: `2026-04-14`

Related planning doc:
- [docs/ops/2026-04-14_self_heal_governance_and_export_reconciliation_execution_plan_v1.md](/vol1/1000/projects/ChatgptREST/docs/ops/2026-04-14_self_heal_governance_and_export_reconciliation_execution_plan_v1.md:1)

Related issue:
- `#211` `chatgpt_web.ask` long answers can be visible in the browser while the job remains stuck at `awaiting_export_reconciliation`

## Scope

This delivery implemented the full `P0/P1/P2/P3` bundle:

- `P0` safe defaults for self-heal enablement
- `P1` shared repair gate to block wrong incident families from Codex-backed remediation
- `P2` hard daily budgets for self-heal lanes
- `P3` `chatgpt_web.ask` wait/export reconciliation completion when the final answer is already available

## What Changed

### 1. Self-heal governance was tightened

- Added `chatgptrest/core/repair_gate.py` as the shared classifier for:
  - `caller_contract`
  - `external_prerequisite`
  - `provider_fail_closed`
- Wired the gate into:
  - worker auto-autofix routing
  - maint daemon `repair.check`
  - maint daemon `codex_sre_analyze`
  - maint daemon `codex_sre_autofix`
  - maint daemon fallback `repair.autofix`
  - maint daemon issues-registry-triggered Codex re-analysis
- Added hard daily caps for:
  - `repair.check`
  - `codex_sre_analyze`
  - `codex_sre_autofix`
  - maint fallback `repair.autofix`
- Changed `ops/systemd/enable_maint_self_heal.sh` so mutation lanes are no longer silently enabled. They now require explicit opt-in flags.

### 2. ChatGPT wait/export reconciliation now completes the job earlier when safe

In `chatgptrest/worker/worker.py`, the `chatgpt_web.ask` wait-phase branch now handles the gap raised in issue `#211`:

- If conversation export matched the target prompt but still had no assistant reply, worker now evaluates the current answer candidate instead of blindly requeueing.
- The current answer candidate can come from:
  - the current DOM answer
  - `answer_id` rehydration when the live result was truncated but a full saved blob exists
- If that candidate passes the existing finality/quality guards, worker now:
  - records `conversation_export_missing_reply_ignored`
  - records `answer_completed_from_wait_answer` or `answer_completed_from_answer_id`
  - finalizes the job and writes the canonical answer artifact
- If export shows a subsequent user turn before any assistant reply for the target prompt, worker now fail-closes to `needs_followup` in the wait-phase path as well.

This removes the prior blind spot where the browser could already show a final answer but the API still had no `authoritative_answer_path`.

## Verification

Targeted regression:

```bash
./.venv/bin/python -m py_compile chatgptrest/worker/worker.py tests/test_worker_and_answer.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_worker_and_answer.py -k 'wait_phase_finalizes_from_current_answer_when_export_missing_reply or wait_phase_finalizes_from_answer_id_when_export_missing_reply or wait_phase_fails_closed_when_export_thread_is_contaminated'
```

Broader regression:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_worker_and_answer.py \
  tests/test_job_view_progress_fields.py \
  tests/test_repair_gate.py \
  tests/test_worker_auto_autofix_submit.py \
  tests/test_maint_daemon_auto_repair_check.py \
  tests/test_maint_daemon_codex_sre.py
```

All of the above passed.

Doc obligation check:

```bash
python3 scripts/check_doc_obligations.py --diff HEAD
```

This passed after the runbook update for the worker-side export reconciliation behavior.

## Notes

- The two real jobs referenced in issue `#211` later converged to `completed` locally, but only after additional wait/export cycles. The code change here addresses the earlier stuck shape directly instead of relying on eventual export convergence.
- No live `systemctl --user` change was applied in this task. The safe-enable behavior and budgets were changed in code/scripts/docs only.
