# Issue 157 Inline Answer Result Fix Design v1

## Background

- GitHub issue: `#157`
- Severity: `P1`
- Symptom: `chatgptrest_result(include_answer=true)` returns `answer=""` for a completed `chatgpt_web.ask` job even when:
  - `preview` is non-empty
  - `answer_chars > 0`
  - `artifacts/jobs/<job_id>/answer.*` contains the expected answer text

## Problem Statement

The unified MCP result tool is expected to provide a one-stop `status + inline answer` surface for completed jobs. For issue `#157`, the REST storage and artifact layers are healthy, but the MCP retrieval layer drops the answer and returns an empty inline payload. This breaks programmatic consumers even though the job itself completed successfully.

## Root Cause

`GET /v1/jobs/{job_id}/answer` now exposes the documented chunked answer contract:

- `chunk`
- `returned_chars`
- `next_offset`
- `done`
- `offset`

But the MCP reader paths still parse an older shape:

- `content`
- `total_bytes`
- `length`
- `offset`

Affected read paths:

- `chatgptrest/mcp/server.py::chatgptrest_result`
- `chatgptrest/mcp/_answer_cache.py::prefetch`

As a result:

- direct API fetch inside `chatgptrest_result()` stores `answer=""`
- answer prefetch cache also stores an empty payload
- completed jobs can therefore surface as `answer=""` even when artifacts are correct

## Goals

- Make `chatgptrest_result()` correctly inline completed answers from the current chunked REST answer contract.
- Keep the MCP layer backward compatible with older answer payload shapes when possible.
- Fix prefetch cache normalization so cached answers are not silently emptied.
- Add regression tests for both direct fetch and prefetch cache paths.

## Non-Goals

- No REST contract change for `/v1/jobs/{job_id}/answer`
- No worker/storage pipeline change
- No change to answer artifact format or answer chunk semantics

## Proposed Fix

Introduce a shared MCP-side normalization step for answer payloads:

1. Accept the current chunked REST shape:
   - map `chunk -> content`
   - map `returned_chars` or `len(chunk) -> length`
   - preserve `offset`, `next_offset`, `done`
   - derive `answer_truncated = not done`
2. Continue accepting the legacy shape when present:
   - keep `content`, `total_bytes`, `length`, `offset`
3. Reuse the same normalization logic in:
   - direct fetch path inside `chatgptrest_result()`
   - `_answer_cache.prefetch()`
4. Surface normalized metadata consistently:
   - `answer`
   - `answer_length`
   - `answer_offset`
   - `answer_truncated`
   - `next_offset` when more chunks remain
   - `answer_source`

## Verification Plan

- Unit test `chatgptrest_result()` against chunked `/answer` payloads.
- Unit test cached answer path so prefetch-cache responses also return non-empty inline answers.
- Run focused pytest for MCP result tests.
- Run `gitnexus_detect_changes()` before commit to confirm scope is limited to MCP + docs/tests.

## Risks

- Low blast radius. GitNexus impact for `chatgptrest_result` and `_answer_cache.prefetch` is `LOW`.
- Main risk is regressing callers that still rely on legacy payload interpretation; backward-compatible normalization addresses this.

## Commit Plan

1. Commit design + todo docs
2. Commit MCP normalization + tests
3. Commit walkthrough / closeout artifacts if needed
