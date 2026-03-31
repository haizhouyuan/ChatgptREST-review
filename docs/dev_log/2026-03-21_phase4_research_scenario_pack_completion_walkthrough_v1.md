# 2026-03-21 Phase 4 Research Scenario Pack Completion Walkthrough v1

## Why this phase existed

After `Phase 3`, planning had a real `scenario_pack`, but research still relied on coarse top-level `scenario` and route heuristics. That left four gaps:

- no stable research profile taxonomy
- no pack-level clarify policy
- no report/deep-research evidence contract
- no alignment for `standard_entry` or `/v1/advisor/consult`

## Implementation order

1. Added research profile resolution to `scenario_packs.py` without touching canonical intake schema.
2. Tightened strategist clarify behavior only for research profiles that need it.
3. Passed `scenario_pack` into `execute_deep_research` and `execute_report`.
4. Let `report_graph` read research evidence thresholds.
5. Aligned preset recommendation and standard-entry adapter.
6. Aligned consult defaults for research-heavy requests.

## Important choices

- Planning resolution still wins over research resolution. This avoids hijacking business-planning asks into research just because they mention comparison or analysis.
- `research_report` keeps `route=report` and `report_type=analysis`; it does not masquerade as `deep_research`.
- `topic_research` and `comparative_research` stay on `deep_research`; they do not force the report lane.
- Phase 4 did not edit `build_task_intake_spec()`. That kept the canonical intake builder stable while the new behavior stayed in the additive pack layer.

## Runtime outcome

- `research_report` now behaves like a real scenario pack instead of a loose combination of `report + research` keywords.
- `comparative_research` and `topic_research` now carry explicit evidence expectations.
- `consult` now defaults to research-capable models when the request shape clearly requires it.
