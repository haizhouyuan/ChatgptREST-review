# Premium Ask EvoMap Writeback Fix v1

Date: 2026-03-18

## Problem

`/v3/agent/turn` had premium post-review generation wired, but the EvoMap writeback path was effectively dead:

- `chatgptrest/api/routes_agent_v3.py::_write_review_to_evomap()` created a fresh `EventBus()` instead of using the persistent runtime bus.
- The helper called `publish()` even though `EventBus` exposes `emit()`.
- `_build_agent_response()` dropped the real `trace_id` and wrote reviews with an empty trace.

Result:

- premium review signals never flowed into the already-wired runtime observer path
- `signals.db` had zero `premium_ask.review.*` rows before the fix

## Fix

Updated [routes_agent_v3.py](/vol1/1000/worktrees/chatgptrest-dashboard-p0-20260317-clean/chatgptrest/api/routes_agent_v3.py):

- use `get_advisor_runtime_if_ready()` and reuse `runtime.event_bus`
- skip writeback cleanly when runtime bus is not ready
- call `event_bus.emit(...)` instead of the nonexistent `publish(...)`
- preserve the real `trace_id` for both explicit review objects and auto-generated reviews
- thread `trace_id` through all `_build_agent_response(...)` call sites

Updated [test_routes_agent_v3.py](/vol1/1000/worktrees/chatgptrest-dashboard-p0-20260317-clean/tests/test_routes_agent_v3.py):

- added a direct unit test for `_write_review_to_evomap(...)`
- added an integration-style helper test proving `_build_agent_response(...)` emits five premium review signals with the real trace id

## Verification

Automated:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_routes_agent_v3.py
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_agent_v3_routes.py
```

Runtime:

- restarted `chatgptrest-api.service`
- executed a local runtime probe against the live EvoMap DB using the persistent advisor runtime bus
- verified the emitted trace produced these signal types:
  - `premium_ask.review.answer_quality`
  - `premium_ask.review.contract_completeness`
  - `premium_ask.review.hallucination_risk`
  - `premium_ask.review.model_route_fit`
  - `premium_ask.review.question_quality`

Post-fix DB check:

```sql
select count(*) from signals where signal_type like 'premium_ask.review.%';
```

Result after fix: `5`

## Notes

- The API service restart succeeded and remained `active`.
- A direct HTTP probe could not be completed with the non-secret test token shown by `systemctl show`; the running service is enforcing a different credential source than the visible explicit env. This did not block verification because the runtime bus probe wrote through the same persistent EvoMap pipeline and landed in the shared `signals.db`.
