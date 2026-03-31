# 2026-03-08 Gemini Deep Research Followup Issue Ledger Fix

## Context

- Source issue ledger item: `iss_9af240e52984458984aa27576f726947`
- Symptom: Gemini Deep Research parent job entered `needs_followup` with a planning stub, but the explicit followup child job completed with the same stub instead of starting research.
- Evidence jobs:
  - parent: `e49a4709023d4500a7c46880c78ebdc4`
  - child: `08a6cc4b3254466a8ba5d7735621bc7b`

## Root Cause

Two failures stacked together:

1. `chatgptrest_followup()` defaulted `deep_research=False` and forwarded that value into `chatgptrest_ask()`.
2. The HTTP create path only inherited `conversation_url` from `parent_job_id`; it did not inherit deep-research intent when the child omitted the flag.

That meant the child job request artifact was persisted as:

- `kind = gemini_web.ask`
- `preset = pro`
- `deep_research = false`

Once the child ran as a non-DR ask, the Gemini planning stub was allowed to complete as a normal answer instead of being classified as `needs_followup`.

## Fixes

### 1. Preserve DR intent across followups

- `chatgptrest_ask()` now treats `deep_research` as optional and only serializes it when explicitly provided.
- `chatgptrest_followup()` now defaults `deep_research` to `None` instead of forcing `False`.
- `/v1/jobs` create path now inherits `params.deep_research=true` from the parent web-ask job when:
  - the child has `parent_job_id`
  - the child kind matches the parent kind
  - the child did not explicitly provide `deep_research`

This preserves the existing escape hatch: callers can still explicitly set `deep_research=false` for "retry without DR".

### 2. Fail closed on Gemini plan stubs

- Added a narrow classifier guard for Gemini Deep Research planning stubs that contain the short action set:
  - `修改方案`
  - `开始研究`
  - `不使用 Deep Research`

This keeps repeated planning stubs in `needs_followup` even if they leak through a DR followup path.

## Regression Coverage

- `tests/test_contract_v1.py`
  - followup inherits DR when omitted
  - explicit `deep_research=false` remains respected
- `tests/test_mcp_unified_ask_min_chars.py`
  - MCP followup no longer forces `deep_research=false`
- `tests/test_deep_research_classify.py`
  - exact Gemini planning stub is classified as `needs_followup`

## Validation

Executed in isolated worktree:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_contract_v1.py -k 'followup_parent_job_id_inherits_deep_research_when_param_omitted or followup_parent_job_id_keeps_explicit_deep_research_false'

PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_mcp_unified_ask_min_chars.py -k 'followup'

PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_deep_research_classify.py

PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_gemini_answer_quality_guard.py \
  tests/test_gemini_deep_research_gdoc_fallback.py \
  tests/test_gemini_wait_transient_handling.py

PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_contract_v1.py \
  tests/test_mcp_unified_ask_min_chars.py \
  tests/test_deep_research_classify.py
```

## Notes

- Main repository worktree was dirty, so implementation happened in:
  - `/vol1/1000/projects/_worktrees/chatgptrest-issue-ledger-dr-followup-20260308`
- GitNexus index is current for `/vol1/1000/projects/ChatgptREST`, but `detect_changes()` cannot see the isolated worktree branch directly. Scope verification for this fix therefore used:
  - GitNexus impact on edited symbols
  - `git status` in the isolated worktree
  - targeted regression tests
