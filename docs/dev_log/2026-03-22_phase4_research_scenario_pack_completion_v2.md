# 2026-03-22 Phase 4 Research Scenario Pack Completion v2

## Result

`Phase 4: Research Scenario Pack` remains complete after one post-review correction on the legacy consult ingress.

## What Changed

- Corrected [chatgptrest/api/routes_consult.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_consult.py) so `_select_consult_models(...)` now keeps:
  - `topic_research` and `comparative_research` on `DEEP_RESEARCH_MODELS`
  - `research_report` on `DEFAULT_MODELS`
- Added a dedicated regression in [tests/test_advisor_consult.py](/vol1/1000/projects/ChatgptREST/tests/test_advisor_consult.py) for the `research_report` consult path.

## Why v2 Was Needed

`Phase 4 v1` was directionally correct but one legacy adapter still disagreed with the canonical research-pack semantics:

- `preset_recommender.py` already treated `research_report` as `pro_extended`
- `/v1/advisor/consult` still treated `research_report` like a deep-research profile

That mismatch meant the legacy consult entry could default a report-writing ask to `chatgpt_dr` / `gemini_dr` instead of the report-grade pair `chatgpt_pro` / `gemini_deepthink`.

## Acceptance

- `research_report` remains a `report`-lane research pack.
- `/v1/advisor/consult` now aligns with the report-grade default model policy for `research_report`.
- `topic_research` and `comparative_research` still default to deep-research-capable model sets.

## Verification

```bash
./.venv/bin/pytest -q tests/test_advisor_consult.py
python3 -m py_compile chatgptrest/api/routes_consult.py tests/test_advisor_consult.py
```

## Remaining Scope Boundary

- This v2 only corrects the legacy consult ingress default-model mismatch.
- It does not change the already-frozen `research_report -> report` routing, strategist clarify behavior, or `standard_entry` preset alignment from `Phase 4 v1`.
