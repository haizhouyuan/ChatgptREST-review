# 2026-03-31 Gemini Review Repo Hint And Drive Attach Fail-Open Alignment v1

## Goal

Fix the wrapped Gemini review lane so repo-backed review packets can still reach Gemini with authoritative public repo context when Drive attachment UI is unavailable.

This remediation is intentionally narrow:

- preserve `github_repo` as a review-context hint for direct Gemini review jobs
- do not re-enable generic imported-code behavior
- do not widen deep-research semantics
- keep Drive attach fail-open behavior grounded in a public review repo URL

## Incident Summary

Wrapped Gemini review calls for the `opencli / CLI-Anything` v2 plan were failing or degrading in two stages:

1. older runs failed in imported-code mode
2. after imported-code fail-open work, direct Gemini review jobs could still lose repo-level context because `github_repo` was only passed through when `enable_import_code=true`

That meant a review request could arrive at `gemini_web.ask` with:

- local file attachments
- generated attach bundle
- Drive upload metadata

but **without** the authoritative public repo hint that the provider-side fail-open path expected to keep the review grounded when upload UI actions were partially unavailable.

## Root Cause

The repo-hint contract was inconsistent across three layers:

1. `chatgptrest/api/routes_agent_v3.py`
   - direct Gemini lane only copied `provider_request.github_repo` into `input_obj.github_repo` when `enable_import_code` was true
2. `chatgptrest/api/routes_jobs.py`
   - low-level `/v1/jobs` rejected `gemini_web.ask` requests carrying `input.github_repo` unless `params.enable_import_code=true`
3. `chatgptrest/executors/gemini_web_mcp.py`
   - executor `_run_ask` also rejected `github_repo` unless `enable_import_code=true`

This made sense for imported-code mode, but it was too strict for wrapped review jobs where `github_repo` is not a code-import request. In review mode it is an authoritative public repo hint used to preserve context when Drive attachment actions degrade.

## Code Changes

### 1. Preserve repo hint in direct Gemini review lane

File:

- `chatgptrest/api/routes_agent_v3.py`

Change:

- when direct Gemini lane is selected and `provider_request.github_repo` is present, copy it into `input_obj.github_repo` even if `enable_import_code` is absent

Rationale:

- wrapped review jobs need the repo hint as stable review context, not as imported-code permission

### 2. Allow low-level gemini review jobs to carry public repo hint without imported-code mode

File:

- `chatgptrest/api/routes_jobs.py`

Change:

- keep type validation for `input.github_repo`
- remove the write-time guard that forced `params.enable_import_code=true`

Rationale:

- `gemini_web.ask` review jobs may need a public repo hint without enabling imported-code features

### 3. Allow executor ask path to accept repo hint without imported-code mode

File:

- `chatgptrest/executors/gemini_web_mcp.py`

Change:

- remove the executor-side error for `github_repo && !enable_import_code`
- retain the separate block on `github_repo + deep_research`

Rationale:

- review-mode repo hint is now a supported, narrower use case
- deep research remains a separate path and is still blocked from mixing with repo-hint semantics

## Tests Added / Updated

### `tests/test_gemini_drive_attach_urls.py`

- verify `gemini_web.ask` can pass `github_repo` without imported-code mode
- keep the positive imported-code case
- verify `github_repo + deep_research` remains blocked

### `tests/test_routes_agent_v3.py`

- verify direct Gemini research lane preserves normalized public repo hint without adding `enable_import_code`

### `tests/test_jobs_write_guards.py`

- verify signed planning-wrapper low-level `/v1/jobs` can submit `gemini_web.ask` with public repo hint and no imported-code flag

## Validation

Targeted regression:

```bash
./.venv/bin/pytest -q \
  tests/test_gemini_drive_attach_urls.py \
  tests/test_routes_agent_v3.py \
  tests/test_jobs_write_guards.py \
  -k 'gemini_github_repo or gemini_research_keeps_public_repo_hint or gemini_web_ask_allows_public_repo_hint_without_import_code or requested_gemini_code_review_uses_direct_gemini_web_lane'
```

Observed result:

- `6 passed`

Runtime reload:

```bash
systemctl --user restart \
  chatgptrest-api.service \
  chatgptrest-mcp.service \
  chatgptrest-worker-send.service \
  chatgptrest-worker-wait.service
```

Observed live outcome:

- wrapped Gemini `v4` review completed with a grounded answer
- wrapped Gemini `v2` review advanced past the old repo-hint loss failure mode
- one retry still produced an off-target answer due to model interpretation, which is handled as a review-quality issue, not a runtime transport failure

## Boundary

This fix does **not** claim:

- every Gemini long review will always be high quality
- Drive UI will never degrade again
- imported-code and repo-hint semantics are interchangeable

It only claims:

- repo-backed wrapped Gemini review jobs now preserve public review repo context through the direct Gemini review lane
- provider-side Drive attach fail-open has the context it needs to stay grounded
