# Issue 157 Inline Answer Result Fix Walkthrough v1

## Scope

- Issue: `#157`
- Branch: `fix/issue157-inline-answer`
- Base: `8fb1ac793ac30d014ad7889414223e0f20d1116a`

## What Happened

Observed symptom:

- completed `chatgpt_web.ask` jobs had non-empty `preview`
- answer artifacts under `artifacts/jobs/<job_id>/answer.*` were non-empty
- `chatgptrest_result(include_answer=true)` still returned `answer=""`

Confirmed root cause:

- REST `/v1/jobs/{job_id}/answer` returns the documented chunked shape:
  - `chunk`
  - `returned_chars`
  - `next_offset`
  - `done`
- MCP `chatgptrest_result()` and answer prefetch cache were still parsing the legacy shape:
  - `content`
  - `total_bytes`
  - `length`

That contract drift caused inline answer loss only in the MCP result surface.

## Changes

### 1. Added execution anchors

- `docs/dev_log/2026-03-12_issue157_inline_answer_result_fix_design_v1.md`
- `docs/dev_log/2026-03-12_issue157_inline_answer_result_fix_todolist_v1.md`

Purpose:

- preserve issue context
- lock repair scope
- keep a stable todo list for long-running execution

### 2. Fixed MCP answer normalization

Updated:

- `chatgptrest/mcp/_answer_cache.py`
- `chatgptrest/mcp/server.py`

Implementation:

- added shared MCP-side normalization for current chunked `/answer` payloads
- preserved compatibility for legacy `content/total_bytes/length` payloads
- reused the same normalization in:
  - direct fetch path inside `chatgptrest_result()`
  - background answer prefetch cache

### 3. Added regression coverage

Updated:

- `tests/test_mcp_unified_ask_min_chars.py`

Added coverage for:

- direct `chatgptrest_result()` reading chunked `/answer` responses
- cached result path using normalized answer payloads
- answer prefetch cache storing chunk payloads correctly

## Verification

Passed:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_mcp_unified_ask_min_chars.py
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_mcp_unified_ask_min_chars.py tests/test_contract_v1.py::test_preview_and_answer_follow_answer_path
```

## GitNexus Notes

Impact analysis before editing:

- `chatgptrest/mcp/server.py::chatgptrest_result` => `LOW`
- `chatgptrest/mcp/_answer_cache.py::prefetch` => `LOW`

`gitnexus_detect_changes()` did not produce a trustworthy scope summary in this task. The indexed repo is shared with another dirty primary worktree containing large unrelated changes, so `detect_changes(scope=all|compare)` surfaced a repo-wide `critical` delta unrelated to this branch.

Branch-local git verification was used as the authoritative scope check:

```bash
git diff --name-only 8fb1ac793ac30d014ad7889414223e0f20d1116a..HEAD
```

Result:

- `chatgptrest/mcp/_answer_cache.py`
- `chatgptrest/mcp/server.py`
- `docs/dev_log/2026-03-12_issue157_inline_answer_result_fix_design_v1.md`
- `docs/dev_log/2026-03-12_issue157_inline_answer_result_fix_todolist_v1.md`
- `tests/test_mcp_unified_ask_min_chars.py`

## Commits

- `6763e54` `docs: add issue157 design and todo`
- `afe3960` `fix: normalize chunked answer payloads in mcp result`

## Expected Outcome

After this branch lands:

- completed jobs with readable answer artifacts will again return non-empty inline `answer` from `chatgptrest_result(include_answer=true)`
- prefetch cache will no longer silently cache empty content for chunked `/answer` payloads
