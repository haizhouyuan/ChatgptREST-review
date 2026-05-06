# 2026-03-11 Codex Gemini Recovery Shutdown Summary v1

## Purpose

This document records the full set of work completed in the Gemini
`conversation_url` recovery investigation/fix session, so the next operator can
shut down this Codex lane without losing context.

It is written as a shutdown summary, not as a design doc.

## User Request That Started This Work

The trigger was a live user report:

- Gemini thread URL:
  - `https://gemini.google.com/app/2f7ddf5e8efabe4a`
- user observation:
  - browser already showed a real answer
  - Antigravity / ChatgptREST still treated the job as problematic
  - second round with attachments still had `conversation_url=null`

The user explicitly asked for:

1. issue-graph / EvoMap-side investigation
2. fundamental root-cause judgment, not just a patch
3. reliable discovery of similar historical failures

## Main Findings

### 1. The page had a real answer

I verified the reported Gemini thread with a read-only extraction path:

- tool:
  - `gemini_web.extract_answer`
- source URL:
  - `https://gemini.google.com/app/2f7ddf5e8efabe4a`
- result job:
  - `e06db059950f4135b06063c3931adfa1`

Observed result:

- `status=completed`
- `answer_chars=6813`
- same Gemini thread URL returned

Judgment:

- this was not a "Gemini produced no answer" failure
- it was a state recovery / resumability failure

### 2. The real contract gap

Before the fix:

- Gemini provider persisted idempotency state
- that state could later contain `conversation_url`
- `GeminiWebMcpExecutor` had no Gemini-side read-only recovery seam equivalent to
  ChatGPT's idempotency lookup flow

That allowed the following bad sequence:

1. send returned `in_progress`
2. immediate response did not yet contain a stable thread URL
3. executor crossed into wait semantics
4. later, the thread had a valid answer, but the job still could not safely
   recover the resumable `conversation_url`

This is why the browser could show a valid answer while the job still looked
broken.

### 3. The correct issue-family split

This investigation confirmed that the Gemini wait failures must stay split into
two operational classes:

- `gemini_no_thread_url`
  - wait entered without a resumable thread URL
- `gemini_stable_thread_no_progress`
  - stable thread existed, but wait/harvest made no progress

These are related, but not the same repair surface.

### 4. Historical Gemini issue history is still under-normalized

Newer runtime issues already emit useful `family_id` values, but many historical
Gemini issue rows still have blank family IDs, so history search still requires
fallback through symptom/fingerprint text.

## Work Completed

### A. Runtime fix

Implemented Gemini idempotency-based `conversation_url` recovery:

- added read-only Gemini MCP tool:
  - `gemini_web_idempotency_get`
- wired recovery into send phase
- wired recovery into wait phase
- preserved recovery provenance in result metadata

Primary code areas:

- `chatgpt_web_mcp/providers/gemini/ask.py`
- `chatgpt_web_mcp/providers/gemini_web.py`
- `chatgpt_web_mcp/tools/gemini_web.py`
- `chatgptrest/executors/gemini_web_mcp.py`
- `chatgptrest/executors/config.py`

### B. Issue-family normalization

Normalized Gemini wait family names in:

- `docs/issue_family_registry.json`

Current normalized names:

- `gemini_no_thread_url`
- `gemini_stable_thread_no_progress`

Backward-compatible matching retained for:

- `gemini_followup_thread_handoff`
- `gemini_wait_no_progress`

### C. Additional compatibility fix discovered on clean PR branch

When replaying the work on a clean branch from current `origin/master`, tests
exposed an existing bug in:

- `chatgptrest/core/issue_family_registry.py`

Bug:

- `match_issue_family()` could raise `TypeError` when `metadata` contained
  structured values such as lists/dicts

Fix:

- added `_text_fragments()` flattening
- switched haystack construction to use flattened text fragments instead of
  directly joining nested structures

This fix was necessary to keep the Gemini family normalization tests green on the
actual PR base.

### D. Investigation and review docs written

I wrote two detailed records:

1. walkthrough:
   - `docs/dev_log/2026-03-11_gemini_conversation_url_recovery_and_issue_graph_walkthrough_v1.md`
2. deep analysis:
   - `docs/reviews/2026-03-11_gemini_missing_conversation_url_deep_analysis_v1.md`

The walkthrough is the concise operational record.

The deep analysis contains:

- evidence
- root-cause reasoning
- issue-domain / EvoMap interpretation
- historical search strategy
- acceptance criteria / recommended next steps

## GitHub Artifacts Created

### Issue

Created narrow GitHub issue:

- `#118`
- title:
  - `gemini: answered thread can still strand in WaitNoThreadUrlTimeout when conversation_url recovery is missing`

Purpose:

- separate this narrow state-recovery problem from the broader mixed Gemini issue
  bucket in `#113`

Also added a cross-reference comment on:

- `#113`

### PR

Created clean PR from dedicated branch:

- branch:
  - `codex/gemini-conversation-url-recovery-pr118`
- PR:
  - `#119`
- title:
  - `fix(gemini): recover missing conversation URLs and normalize issue families`

PR scope includes:

- Gemini idempotency recovery
- Gemini issue-family normalization
- issue-family matcher flattening fix
- investigation docs

## Commit Inventory

### Original local work on main repo

These commits were made during the investigation on the local main working repo:

- `05733ac`
  - `fix(gemini): recover conversation url from idempotency`
- `1e3bc18`
  - `docs(gemini): record conversation url recovery investigation`
- `cf6684d`
  - `docs(gemini): add deep analysis for missing conversation url`

### Clean PR branch commits

These are the commits that matter for the PR branch:

- `17762ea`
  - cherry-picked runtime fix
- `9bb2186`
  - cherry-picked walkthrough doc
- `7bdf196`
  - cherry-picked deep analysis doc
- `74cfc2c`
  - `fix(issues): flatten issue family metadata matching`

If another operator needs the merged/clean branch history, use the PR branch
commits above, not the original local main commit IDs.

## Validation Performed

### On the original investigation path

I ran targeted regression coverage for:

- Gemini wait conversation hint behavior
- Gemini transient wait handling
- Gemini driver entrypoint compatibility
- selected worker regression cases
- issue family normalization
- selected canonical issue-domain routing cases

### On the clean PR branch

I reran the relevant subset from the clean PR worktree using the main repo
virtualenv:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_gemini_wait_conversation_hint.py \
  tests/test_gemini_wait_transient_handling.py \
  tests/test_driver_startup_smoke.py \
  tests/test_issue_family_registry.py \
  tests/test_issue_canonical_api.py \
  -k 'issue_graph_query_uses_canonical_when_available or issue_canonical_export_handles_list_metadata_values or test_issue_family_registry_normalizes_gemini_wait_families or test_gemini_wait_passes_conversation_hint_for_base_app_url or test_gemini_wait_phase_recovers_base_app_url_from_idempotency or test_gemini_full_send_without_conversation_url_does_not_enter_wait or test_gemini_full_send_recovers_thread_url_from_idempotency_and_enters_wait or test_gemini_wait_transient_errors_retry_then_complete or test_gemini_wait_transient_errors_return_in_progress_after_limit or test_gemini_wait_phase_without_conversation_url_is_retryable or test_gemini_wait_passes_deep_research_flag or test_gemini_capture_ui_entrypoint_exists or test_gemini_wait_keeps_deep_research_compat_param'
```

And:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/python -m py_compile \
  chatgptrest/core/issue_family_registry.py \
  chatgptrest/executors/gemini_web_mcp.py \
  chatgptrest/executors/config.py \
  chatgpt_web_mcp/tools/gemini_web.py \
  chatgpt_web_mcp/providers/gemini_web.py \
  chatgpt_web_mcp/providers/gemini/ask.py \
  tests/test_gemini_wait_conversation_hint.py \
  tests/test_issue_family_registry.py
```

Final result on the clean PR branch:

- target pytest subset passed
- py_compile passed

## Current Repository State

### Main repo

The main shared repo remains dirty for unrelated reasons.

At shutdown time it still contains unrelated modified/untracked files in areas
outside this Gemini task, including docs/ops, execution-experience files, and
generated knowledge artifacts.

This was explicitly *not* cleaned up by this work.

### Clean PR worktree

The dedicated worktree used for PR creation is:

- `/tmp/chatgptrest-pr118`

Its branch state at handoff time:

- branch:
  - `codex/gemini-conversation-url-recovery-pr118`
- tracking:
  - `origin/codex/gemini-conversation-url-recovery-pr118`
- worktree:
  - clean after PR creation

## Recommended Next Steps

These were intentionally *not* pulled into the PR:

1. historical Gemini issue backfill
   - normalize old blank-family rows into current Gemini family buckets
2. canonical graph reprojection / label cleanup
   - some historical canonical views still expose older Gemini family labels
3. issue-domain operational closeout
   - add verification / usage evidence to move open incidents toward mitigation or
     closure

These are follow-up items, not blockers for PR `#119`.

## Shutdown-Safe Conclusion

It is safe to shut this Codex lane down.

The important durable outputs already exist:

- runtime fix is on a clean PR branch
- investigation docs are committed
- GitHub issue is filed
- PR is filed
- tests were rerun on the clean branch

The next operator should start from:

- issue:
  - `#118`
- PR:
  - `#119`
- branch:
  - `codex/gemini-conversation-url-recovery-pr118`

and should not rely on the dirty shared `master` worktree as the source of truth
for this task.
