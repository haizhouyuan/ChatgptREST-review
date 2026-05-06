# 2026-03-10 Issue #113 Gemini Anchor-Only Fix Walkthrough v1

## Why

GitHub issue `#113` mixed three Gemini symptom families:

- Deep Think tool unavailable
- bogus-short terminal completion (`Gemini 说`)
- send -> wait with no stable thread URL

After re-auditing the cited local jobs against current `master`, the still-live path was the anchor-only bogus completion. The other two families already had current-code mitigations and were better treated as historical issue-domain evidence.

## What I Changed

### 1. Narrow code fix for the still-live bogus completion path

Files:

- `chatgptrest/executors/gemini_web_mcp.py`
- `tests/test_gemini_answer_quality_guard.py`

Commit:

- `6b64aaa` `fix(gemini): fail closed on anchor-only ui noise`

Change:

- when Gemini UI-noise sanitize leaves no usable body, `_gemini_strip_ui_noise_prefix()` now returns an empty cleaned string instead of preserving the anchor fragment
- `_gemini_apply_answer_quality_guard()` now treats `ui_noise_empty_after_sanitize` as `GeminiAnswerContaminated`
- added regression tests for:
  - helper-level anchor-only sanitize behavior
  - executor-level downgrade from `completed` to `needs_followup`

### 2. Wrote a narrow issue-domain / EV intake approval note

File:

- `docs/reviews/2026-03-10_issue113_gemini_issue_domain_intake_approval_v1.md`

Commit:

- `9946ec8` `docs(issues): add issue113 issue-domain intake approval`

What it does:

- narrows `#113` into three families instead of one broad Gemini bucket
- records why only the bogus-short completion path was still live on current `master`
- requests a new curated issue family:
  - `gemini_anchor_only_bogus_completion`
- requests canonical `issue_domain` backfill for the five cited jobs plus commit linkage and post-fix verification

### 3. Posted the GitHub issue update / intake request

Thread:

- `https://github.com/haizhouyuan/ChatgptREST/issues/113#issuecomment-4031625493`

What was posted:

- narrowed systemic analysis
- fix commit reference
- local approval-note path
- issue-domain / EV intake request

## Validation

Passed:

- `PYTHONPATH=. ./.venv/bin/pytest -q tests/test_gemini_answer_quality_guard.py tests/test_gemini_deep_think_overloaded.py tests/test_gemini_followup_wait_guard.py`
- `python3 -m py_compile chatgptrest/executors/gemini_web_mcp.py tests/test_gemini_answer_quality_guard.py`

GitNexus checks:

- `_gemini_apply_answer_quality_guard` upstream impact: `LOW`
- `_gemini_strip_ui_noise_prefix` upstream impact: `LOW`
- `gitnexus_detect_changes(scope=\"staged\")` before each commit: `low`

## Outcome

The still-live `Gemini 说` false-success path from `#113` is now fixed narrowly and covered by regression tests.

The broader GitHub issue is no longer being treated as one unresolved Gemini architecture problem. It is now framed as:

- one fixed code path
- two historical / already-mitigated families
- one narrow `issue_domain` / EV intake request for canonical history
