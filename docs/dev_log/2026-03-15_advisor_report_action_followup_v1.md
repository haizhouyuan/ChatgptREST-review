## Summary

This follow-up closes two live regressions discovered immediately after the
controller unification merge:

1. synchronous `report` requests on `/v2/advisor/advise` could fail with
   `Type is not msgpack serializable: LLMConnector`
2. explicit action asks such as uploading a file to Google Drive or sending a
   team notice could be misrouted to `hybrid` or `funnel/team_execute` instead
   of the controller-owned `effect_intent` path

## What Changed

### Report runtime serialization

- Removed live runtime services from the `report_app.invoke(...)` payload in
  `chatgptrest/advisor/graph.py`
- Bound the nested report subgraph through `bind_runtime_services(runtime)` so
  the subgraph can still access runtime services without putting them into
  checkpointed state
- Added runtime-service fallback helpers in
  `chatgptrest/advisor/report_graph.py` so `kb_hub`, `policy_engine`, and
  `effects_outbox` are resolved from serializable state overrides first and the
  bound advisor runtime second

### Action routing

- Stopped upgrading `action_required + QUICK_QUESTION` into
  `BUILD_FEATURE` during `analyze_intent`
- Added explicit command detection for notification-style asks
- Hardened `route_decision` so explicit action requests stay on the `action`
  pipeline, and `BUILD_FEATURE` overrides no longer clobber a route that has
  already resolved to `action`

### Regression coverage

- Added route-level tests for explicit upload / notice asks
- Added end-to-end controller coverage for
  `把这个文件上传到Google Drive -> effect_intent`
- Added a checkpoint regression test that exercises the `report` route with a
  real `SqliteSaver` and bound runtime services, preventing the original
  `LLMConnector` serialization failure from regressing

## Verification

### Targeted suites

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_advisor_graph.py \
  tests/test_report_graph.py \
  tests/test_advisor_v3_end_to_end.py
```

### Business-flow suites present on current master baseline

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_business_flow_advise.py \
  tests/test_business_flow_deep_research.py \
  tests/test_business_flow_multi_turn.py \
  tests/test_business_flow_openclaw.py \
  tests/test_business_flow_planning_lane.py \
  tests/test_routes_advisor_v3_team_control.py \
  tests/test_routes_advisor_v3_security.py
```

### Live probes against a clean-worktree temp API on `127.0.0.1:18731`

- `把这个文件上传到Google Drive`
  - `route=action`
  - `controller_status=WAITING_HUMAN`
  - `objective_kind=effect`
  - work items: `input -> plan -> effect_intent`
- `给团队发一条通知，说今晚 9 点开始切换`
  - `route=action`
  - `controller_status=WAITING_HUMAN`
  - `objective_kind=effect`
  - work items: `input -> plan -> effect_intent`

The synchronous `report` live probe on the clean worktree did not produce a
quick HTTP result because the temp instance lacked the browser login state used
by the current routing candidates. The regression is still covered by the new
checkpointed graph test, which specifically exercises the historical
serialization failure mode.

## Notes

- `gitnexus_detect_changes(scope=\"all\")` remained polluted by unrelated changes
  in the main repository worktree, so scope validation for this task relied on
  the clean follow-up worktree plus focused `git diff --stat`
- `chatgptrestctl` currently does not offer a first-class “launch a clean
  worktree temp OpenMind API instance on a chosen port” workflow, so the live
  validation still used a manual `uvicorn` command; this CLI gap should be
  tracked separately if we want to standardize merged-branch smoke tests
