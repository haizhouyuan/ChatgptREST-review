# 2026-03-27 advisor_ask duplicate reuse and legacy wait-loop live fix v1

## Scope

Close the remaining runtime gap behind repeated trivial/test ChatGPT threads and repeated advisor asks that still created fresh conversations after the first dedupe rollout.

## Root causes

1. `advisor_ask` recent-duplicate reuse only matched the new hashed `request_fingerprint`.
2. Older `advisor_ask` rows still carried legacy human-readable fingerprints such as `session_id:question_head`, so replaying an older request did not hit the new dedupe query and opened a fresh ChatGPT conversation.
3. Some pre-policy trivial jobs were still alive in `wait` and could continue export/downgrade cycles until a new worker binary actually processed them.

## Changes

### Code

- Extended `chatgptrest/api/routes_advisor_v3.py` duplicate lookup:
  - primary match: hashed `request_fingerprint`
  - fallback match: exact `question + intent_hint + session_id + user_id + role_id`
- Added regression coverage for the legacy-row fallback in `tests/test_routes_advisor_v3_task_intake.py`.

### Runtime

- Reloaded `chatgptrest-api.service` to pick up the dedupe fix.
- Verified that the pre-existing legacy trivial job `a27f36762eab46b68b16672f8a9aaa2c` no longer requeued indefinitely after the worker reload and instead transitioned to `completed`.

### Documentation

- Updated `docs/contract_v1.md` with the new `advisor_ask` duplicate contract and legacy wait-loop breaker semantics.
- Updated `docs/runbook.md` with the relevant env toggles and runtime expectations.

## Validation

### Local

- `./.venv/bin/python -m py_compile chatgptrest/api/routes_advisor_v3.py tests/test_routes_advisor_v3_task_intake.py`
- `./.venv/bin/pytest -q tests/test_routes_advisor_v3_task_intake.py -k 'duplicate'`

### Live

- API restart timestamp after the fix: `2026-03-27 15:17:11 CST`
- Legacy trivial job `a27f36762eab46b68b16672f8a9aaa2c`:
  - reached `status=completed`
  - final event sequence includes `answer_completed_from_export` followed by `status_changed -> completed`
- `advisor_ask` duplicate replay:
  - first replay before the fallback fix created `job_id=2bb887ed37ac45e8bb42d3657c74a891`
  - second replay after the fix returned `duplicate_reused=true`
  - `count_before == count_after == 2`, proving no new job was created
  - response reused `job_id=2bb887ed37ac45e8bb42d3657c74a891`
- Cleanup:
  - canceled the smoke-created job `2bb887ed37ac45e8bb42d3657c74a891`
  - cancel reason: `smoke_cleanup_duplicate_validation`

## Result

The remaining two user-visible failure modes on this line are now closed:

- legacy trivial/test asks no longer stay in infinite wait/export loops once the current worker code sees them
- repeating an older `advisor_ask` request no longer opens a fresh ChatGPT thread just because the stored duplicate fingerprint was written in the legacy format
