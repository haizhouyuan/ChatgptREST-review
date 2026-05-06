# 2026-03-22 Phase 4 Research Scenario Pack Completion Walkthrough v2

## Trigger

Post-review found one real mismatch after `Phase 4 v1`: the legacy `/v1/advisor/consult` ingress still grouped `research_report` with `topic_research` and `comparative_research` for default-model selection.

## Independent Judgment

The review finding was valid, but it did not invalidate Phase 4 as a whole.

- The live research-pack architecture was still correct.
- The defect was a legacy consult adapter inconsistency.
- The right fix was to realign consult defaults, not to reopen `scenario_pack` design.

## Implementation

1. Rechecked the live policy split:
   - `research_report` is a `report`-lane pack
   - `topic_research` / `comparative_research` are `deep_research` packs
2. Narrowed `_select_consult_models(...)` so only the deep-research profiles return `DEEP_RESEARCH_MODELS`.
3. Added a regression test proving a research-report-shaped consult ask returns:
   - `scenario_pack.profile == "research_report"`
   - `models == ["chatgpt_pro", "gemini_deepthink"]`

## Outcome

`Phase 4` can now be read more precisely:

- `v1`: research packs entered the live path
- `v2`: the remaining legacy consult default-model mismatch is closed
