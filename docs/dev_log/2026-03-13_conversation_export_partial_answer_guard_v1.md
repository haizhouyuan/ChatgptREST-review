# 2026-03-13 Conversation Export Partial-Answer Guard v1

## Problem

The dual-model self-iteration review exposed a real hot-path issue in ChatGPT conversation export handling:

- the worker could extract a visible assistant snippet from conversation export
- that snippet could still be only a progress preamble or meta-commentary
- the worker would temporarily treat it as a candidate answer
- completion guard usually downgraded it later, but the extraction/reconcile path was still too optimistic

The concrete evidence came from the 2026-03-13 ChatGPT Pro review jobs:

- `b3148573344e46c98d26fe7e110ca69b`
- `3fa08d0ae7ad4d3c9d08777fe8774849`

Both jobs first exported short preamble-like assistant text before later reconciling to the full final answer.

## Root Cause

Two optimistic behaviors existed:

1. `extract_answer_from_conversation_export_obj()` picked a candidate answer from the matched assistant window even when the export still contained `in_progress` messages and the candidate still looked like partial meta-commentary.
2. `_should_reconcile_export_answer()` only blocked empty export answers, connector tool-call stubs, and deep-research incomplete payloads. It did not block meta-commentary-style partial answers during reconcile.

## Change

### Extraction guard

`chatgptrest/core/conversation_exports.py`

- record `export_has_in_progress` / `export_in_progress_count`
- classify each candidate with `classify_answer_quality()`
- when multiple assistant candidates exist, prefer the longest candidate already classified as `final`
- if the export still has `in_progress` messages and the chosen candidate quality is not `final`, return `None` with `answer_source=matched_in_progress_partial`

### Reconcile guard

`chatgptrest/worker/worker.py`

- `_should_reconcile_export_answer()` now blocks:
  - `suspect_meta_commentary`
  - `suspect_short_answer` when the text has no Markdown structure
- short but structured Markdown is still allowed

## Tests

Added / updated:

- `tests/test_longest_candidate_extraction.py`
  - prefer longest final-quality candidate over longer meta-commentary
  - do not return a partial candidate while export still has `in_progress`
- `tests/test_deep_research_export_guard.py`
  - block meta-commentary during reconcile

Verified:

- `tests/test_longest_candidate_extraction.py`
- `tests/test_deep_research_export_guard.py`
- `tests/test_conversation_export_reconcile.py`
- `tests/test_conversation_export_missing_reply_policy.py`
- `tests/test_answer_quality_completion_guard.py`
- `tests/test_mcp_unified_ask_min_chars.py`
- `tests/test_worker_and_answer.py`

## Expected Effect

- fewer premature `answer_completed_from_export` candidates for GPT-5.4 Pro extended-thinking threads
- fewer read-incomplete / preamble-only artifacts on the wait path
- reconcile path stays conservative and only upgrades to export-derived final text when the candidate already looks like a real answer
