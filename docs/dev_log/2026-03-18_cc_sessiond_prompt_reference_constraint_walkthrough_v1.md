# 2026-03-18 cc-sessiond Prompt Reference Constraint Walkthrough v1

## What Changed

Added a hard prompt-packaging guard to `cc-sessiond` so future Claude task
packets reference versioned documents by path instead of pasting full Markdown
spec bodies into the prompt itself.

## Code Changes

- `chatgptrest/kernel/cc_sessiond/client.py`
  - added `PromptPackagingError`
  - added inline-bundle detection heuristics
  - enforced prompt validation in `CCSessionClient.create_session()`
- `chatgptrest/kernel/cc_sessiond/__init__.py`
  - exported `PromptPackagingError`
- `chatgptrest/api/routes_cc_sessiond.py`
  - convert packaging violations into `HTTP 400`

## Tests Added

- `tests/test_cc_sessiond.py`
  - reject inlined document bundles
  - accept short path-only task packets
- `tests/test_cc_sessiond_routes.py`
  - route returns `400` when a long pasted spec body is submitted

## Why

The first premium integration test run failed inside the Claude execution stack
because the prompt packet was too large and duplicated large document bodies.

The intended operating model is:

- prompt = compact task index
- detailed content = versioned Markdown files
- execution = Claude reads those files from disk

Making this a runtime rule prevents the same failure mode from recurring.

## Validation

Ran:

`/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_cc_sessiond.py tests/test_cc_sessiond_routes.py`

Both suites passed after the change.
