## Summary

Two production-facing issues were closed in this round:

1. `QAInspector` submitted review jobs to `/v1/jobs` with the idempotency key in the JSON body instead of the required `Idempotency-Key` header, which caused repeat `422` failures in live advisor traffic.
2. Advisor runtime cold start still did EvoMap startup rescore by default, which turned the first `/v2/advisor/*` request after restart into a long synchronous warmup.
3. After the header fix, live traffic still hit `403 client_not_allowed` because the local inspector submit path did not include the write-guard `X-Client-Name` and trace headers required by the production profile.

## Changes

- `chatgptrest/advisor/qa_inspector.py`
  - Moved idempotency to the request header expected by `/v1/jobs`.
  - Kept `preset` in `params`, matching the contract already used elsewhere.
  - Added `X-Client-Name`, `X-Client-Instance`, and `X-Request-ID` so the internal submit path satisfies write-guard policy in production.
- `chatgptrest/advisor/runtime.py`
  - Changed `OPENMIND_ENABLE_EVOMAP_STARTUP_RESCORE` to default off.
  - Preserves the feature behind an explicit env flag for operators who want startup maintenance.
- `tests/test_qa_inspector.py`
  - Added coverage for header-based idempotency and payload shape.
  - Added failure-path coverage when submit raises.
- `tests/test_advisor_runtime.py`
  - Added a regression test proving startup rescore stays off unless explicitly enabled.

## Why

The QA inspector failure was not a model issue. The service contract required a header and the inspector violated that contract, so every quick inspection call created avoidable noise and wasted background work.

The second QA inspector failure was also not a model issue. The production API enforces client-name allowlist and trace headers on write operations, so an internal HTTP caller has to identify itself like any other first-class client.

The cold-start latency was also self-inflicted. Startup rescore is maintenance work, not a request-path responsibility, so the safe default for production is to keep it disabled unless an operator opts in.

## Validation

- `./.venv/bin/pytest -q tests/test_advisor_runtime.py tests/test_qa_inspector.py tests/test_advisor_v3_end_to_end.py -k 'rescore or kb_direct or qa_inspector'`
- `./.venv/bin/python -m py_compile chatgptrest/advisor/runtime.py chatgptrest/advisor/qa_inspector.py tests/test_advisor_runtime.py tests/test_qa_inspector.py`

## Expected operator-visible impact

- Advisor quick requests no longer spam `QA Inspector job submit failed ... 422` due to malformed `/v1/jobs` requests.
- Advisor quick requests no longer spam `QA Inspector job submit failed ... 403` due to missing write-guard headers on the self-call path.
- The first advisor request after API restart should no longer pay a default EvoMap rescore penalty.
