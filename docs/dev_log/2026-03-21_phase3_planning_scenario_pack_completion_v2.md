# Phase 3 Planning Scenario Pack Completion v2

Date: 2026-03-21

## Goal

Close the Phase 3 quality-policy gaps that remained after `95ae2ec`:

- meeting/interview summary asks could generate clarify questions but still execute
- light business-planning asks were forced into `funnel + job`
- common Chinese shortforms such as `例会纪要` were not recognized
- `watch_policy` / `funnel_profile` were mostly declarative metadata

## What Changed

### 1. Summary-style planning now clarifies before low-context execution

- `meeting_summary` and `interview_notes` packs now trigger clarify when:
  - `watch_policy.checkpoint == delivery_only`
  - contract completeness is still below `0.75`
  - clarify questions exist
  - there are no grounding inputs (`files` / `attachments` / canonical available inputs)
- This keeps summary asks from running on vague prompts like `请总结面试纪要`.

Affected code:

- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py`

### 2. Business planning now has a light outline branch

- `business_planning` no longer always forces `funnel`.
- Requests that clearly signal a lightweight deliverable such as:
  - `简要`
  - `简版`
  - `框架`
  - `大纲`
  - `不要走复杂流程`
- now resolve to:
  - `route_hint=report`
  - `execution_preference=job`
  - `prompt_template_override=report_generation`
  - lighter acceptance / review expectations

Affected code:

- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py`

### 3. Chinese meeting-summary lexicon was expanded

- Added shortforms and high-frequency variants including:
  - `例会纪要`
  - `例会总结`
  - `周会纪要`
  - `周会总结`
  - `同步纪要`

This fixes the previous fallback that could incorrectly classify these asks as implementation planning.

Affected code:

- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py`

### 4. `watch_policy` and `funnel_profile` are now live runtime inputs

- `watch_policy` now affects strategist clarify gating for summary-style planning asks.
- `funnel_profile` now affects Funnel Gate A thresholding:
  - `implementation_plan`
  - `workforce_planning`
  receive a stricter Gate A threshold (`+0.05` over the current tuned base).

Affected code:

- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/funnel_graph.py`

## Result

Phase 3 can now be considered complete at the quality-policy level, not just at the integration level.

Current frozen behavior:

- `meeting_summary` / `interview_notes` prefer `report`, and vague asks clarify first
- heavy planning profiles still use `funnel`
- light business-planning asks can stay in the report lane
- common Chinese meeting-summary wording is recognized
- pack metadata is no longer prompt-only

## Validation

### Direct reproductions

- `请总结面试纪要`:
  - resolves to `interview_notes`
  - `clarify_required=True`
- `请整理今天例会纪要`:
  - resolves to `meeting_summary`
  - `route=report`
  - `clarify_required=True`
- `请帮我做一个业务规划框架，先给简要版本，不要走复杂流程`:
  - resolves to `business_planning`
  - `route=report`
  - `clarify_required=False`

### Tests

Passed:

```bash
./.venv/bin/pytest -q tests/test_scenario_packs.py tests/test_ask_strategist.py tests/test_funnel_graph.py tests/test_routes_agent_v3.py tests/test_routes_advisor_v3_task_intake.py tests/test_controller_engine_planning_pack.py
./.venv/bin/pytest -q tests/test_prompt_builder.py tests/test_advisor_v3_end_to_end.py tests/test_business_flow_advise.py -k 'planning or advise or v3_ask or strategy or prompt'
python3 -m py_compile chatgptrest/advisor/scenario_packs.py chatgptrest/advisor/ask_strategist.py chatgptrest/advisor/funnel_graph.py tests/test_scenario_packs.py tests/test_ask_strategist.py tests/test_funnel_graph.py tests/test_routes_agent_v3.py tests/test_routes_advisor_v3_task_intake.py
```

## Residual

- `watch_policy` is now behavior-bearing, but it is still not a full watcher/orchestrator contract.
- `funnel_profile` now changes funnel runtime gating, but downstream delivery/watch systems still do not consume it outside the planning lane.
