# 2026-03-21 Phase 4 Research Scenario Pack Completion v1

## Result

`Phase 4: Research Scenario Pack` is now implemented in live code.

## What Changed

- Added three research packs in [chatgptrest/advisor/scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py):
  - `topic_research`
  - `comparative_research`
  - `research_report`
- Tightened strategist clarify policy in [chatgptrest/advisor/ask_strategist.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py) so vague research-report asks stop earlier.
- Wired pack consumption into [chatgptrest/advisor/graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py):
  - `execute_deep_research`
  - `execute_report`
- Extended [chatgptrest/advisor/report_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/report_graph.py) so report purpose identification and web-research thresholds consume `scenario_pack`.
- Extended [chatgptrest/advisor/preset_recommender.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/preset_recommender.py) and [chatgptrest/advisor/standard_entry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py) so research packs influence preset choice in the non-live adapter path.
- Extended [chatgptrest/api/routes_consult.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_consult.py) so consult defaults align with research-heavy packs.

## Acceptance

- Research asks now resolve a stable `scenario_pack` instead of staying on raw top-level `scenario`.
- Research-report asks route to `report` with `analysis` report type.
- Topic/comparative research asks route to `deep_research`.
- `standard_entry` no longer loses research semantics before preset recommendation.
- `/v1/advisor/consult` defaults to deep-research-capable model sets for research-heavy asks.

## Verification

### Phase 4 targeted regression

```bash
./.venv/bin/pytest -q \
  tests/test_scenario_packs.py \
  tests/test_ask_strategist.py \
  tests/test_report_graph.py \
  tests/test_system_optimization.py \
  tests/test_routes_agent_v3.py \
  tests/test_routes_advisor_v3_task_intake.py \
  tests/test_advisor_consult.py
```

### Adjacent ingress/runtime regression

```bash
./.venv/bin/pytest -q \
  tests/test_advisor_graph.py \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_feishu_ws_gateway.py \
  tests/test_business_flow_advise.py \
  tests/test_advisor_v3_end_to_end.py \
  -k 'research or report or advise or openclaw or feishu'
```

### Static verification

```bash
python3 -m py_compile \
  chatgptrest/advisor/scenario_packs.py \
  chatgptrest/advisor/ask_strategist.py \
  chatgptrest/advisor/graph.py \
  chatgptrest/advisor/report_graph.py \
  chatgptrest/advisor/preset_recommender.py \
  chatgptrest/advisor/standard_entry.py \
  chatgptrest/api/routes_consult.py
```

## Remaining Non-blocking Gaps

- `prompt_builder` still treats pack profile text as generic scenario metadata; Phase 4 did not add a dedicated research-profile prompt lane beyond template override and pack JSON injection.
- OpenClaw plugin-side payload shaping did not need to change in this phase; research resolution is server-driven.
