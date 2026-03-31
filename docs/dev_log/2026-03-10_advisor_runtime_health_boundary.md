## Background

`get_advisor_runtime()` remains a heavy bootstrap path. Both `/v2/advisor/health`
and `/v2/cognitive/health` previously called it directly, so a health probe could
accidentally initialize the full runtime and its side effects.

## Change

- added lightweight runtime readiness helpers:
  - `is_advisor_runtime_ready()`
  - `get_advisor_runtime_if_ready()`
- changed `/v2/cognitive/health` to report `status=not_initialized` without
  bootstrapping the runtime
- changed `/v2/advisor/health` to report `status=not_initialized` and subsystem
  placeholders until the runtime has been brought up by a real request
- added tests covering:
  - readiness helper behavior across reset/init/reset
  - cognitive health not booting runtime
  - advisor health remaining auth/rate-limit exempt while not booting runtime

## Why

- health should observe bootstrap state, not mutate it
- runtime/bootstrap tightening can proceed in small steps without touching
  issue-domain or KB/graph ownership
- this keeps future prewarm work optional instead of implicit

## Validation

- `./.venv/bin/pytest -q tests/test_advisor_runtime.py tests/test_cognitive_api.py tests/test_routes_advisor_v3_security.py`
- `./.venv/bin/python -m py_compile chatgptrest/advisor/runtime.py chatgptrest/api/routes_cognitive.py chatgptrest/api/routes_advisor_v3.py tests/test_advisor_runtime.py tests/test_cognitive_api.py tests/test_routes_advisor_v3_security.py`
