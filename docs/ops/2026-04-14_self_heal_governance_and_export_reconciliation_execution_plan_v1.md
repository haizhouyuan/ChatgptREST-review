# ChatgptREST Self-Heal Governance And Export Reconciliation Execution Plan v1

Date: `2026-04-14`

Related issue:
- `#211` `chatgpt_web.ask` long answers can be fully visible in the browser while ChatgptREST remains stuck at `awaiting_export_reconciliation`

Primary reproductions captured in the issue:
- `aa2731cd8f164da08392d471435b6e9a`
- `621650ce45d344e9bc7e8505d32818f7`

## Problem Statement

Two problems have been interacting:

1. Self-heal routing was too wide.
   - `maint_daemon` and historical worker auto-autofix lanes could promote caller-contract failures, external prerequisites, and provider fail-closed states into Codex-backed remediation.
   - This created unnecessary `repair.check`, `codex_sre_analyze`, `codex_sre_autofix`, and `repair.autofix` traffic, which in turn burned `gpt-5.3-codex-spark`.

2. `chatgpt_web.ask` export reconciliation was too conservative.
   - For some long answers, the web UI already showed the final answer and the user could manually copy it.
   - ChatgptREST still waited for conversation export reconciliation to converge before producing a canonical answer artifact.
   - That left jobs in `phase=wait`, `phase_detail=awaiting_export_reconciliation`, `canonical_answer.ready=false`.

## Scope

This execution plan covers four tracks:

- `P0` stopgap: make safe defaults actually safe.
- `P1` routing gate: deny auto-remediation for the wrong incident families.
- `P2` budgets: add hard daily caps on top of existing rolling-window and per-incident limits.
- `P3` provider fix: complete `chatgpt_web.ask` when the final answer is already available even if export lags.

## Implementation Plan

### P0: Safe defaults

- Keep `ops/systemd/chatgptrest-maint-daemon.service` analysis-first.
- Change `ops/systemd/enable_maint_self_heal.sh` so it no longer silently enables:
  - worker auto Codex autofix
  - maint daemon Codex SRE autofix
- Require explicit CLI opt-in:
  - `--with-worker-auto-autofix`
  - `--with-codex-sre-autofix`

### P1: Shared repair gate

- Add a shared classifier in `chatgptrest/core/repair_gate.py`.
- Classify and fail closed for these families:
  - `caller_contract`
    - `AttachmentContractMissing`
  - `external_prerequisite`
    - `GeminiUnsupportedRegion`
    - `GeminiNotLoggedIn`
    - `GeminiGoogleVerification`
    - `GeminiCaptcha`
  - `provider_fail_closed`
    - `GeminiBlankSendTimeout`
    - `GeminiConversationThreadMismatch`
    - `GeminiDriveAttachUnavailable`
    - Gemini `WaitNoThreadUrlTimeout` / `MaxAttemptsExceeded` variants without stable thread identity
- Apply the same gate to:
  - worker `_maybe_submit_worker_autofix`
  - maint daemon `repair.check`
  - maint daemon `codex_sre_analyze`
  - maint daemon `codex_sre_autofix`
  - maint daemon fallback `repair.autofix`
  - maint daemon issues-registry-triggered Codex re-analysis

### P2: Hard budgets

- Preserve existing window/per-incident limits.
- Add hard daily caps for:
  - `repair.check`
  - `codex_sre_analyze`
  - `codex_sre_autofix`
  - maint fallback `repair.autofix`
- Emit dedicated events when the daily budget is exhausted so operators can distinguish:
  - rate-limited in rolling window
  - capped per incident
  - capped for the day

### P3: ChatGPT export reconciliation

- In worker `chatgpt_web.ask` wait-phase completion logic:
  - when `status=in_progress`
  - and conversation export matched the target user turn
  - but export still has no assistant reply
  - and the current DOM answer or offloaded `answer_id` answer is already substantial/final
- Complete the job directly instead of requeueing `awaiting_export_reconciliation`.
- Prefer the rehydrated full `answer_id` blob when it is better than the DOM/export candidate.
- Keep the existing contamination guard:
  - if export shows a subsequent user turn before any assistant reply for the target prompt, fail closed to `needs_followup` instead of finalizing the wrong answer.

## Verification Plan

- Unit/regression tests for `repair_gate` classification.
- Worker autofix tests proving same-session-repair incidents do not auto-submit `repair.autofix`.
- Worker export-reconciliation tests proving:
  - final DOM/answer-id answer can complete a stuck `in_progress` ChatGPT wait job
  - contaminated threads still fail closed
- Compile checks:
  - `./.venv/bin/python -m py_compile ...`

## Status Snapshot

Planned commits:

1. Governance gate + budgets
2. Safe-enable defaults + docs + execution plan
3. ChatGPT export reconciliation completion fix
4. Walkthrough / closeout

This file exists to preserve the execution contract and reproduction context even if the working conversation is compressed later.
