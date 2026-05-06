# 2026-03-21 Research Scenario Pack v1

## Goal

Turn `research` from a bare top-level scenario into a live `scenario_pack` contract that:

- resolves at ingress
- influences strategist clarify behavior
- affects `deep_research` and `report` execution behavior
- aligns `standard_entry` preset recommendation and `/v1/advisor/consult` defaults

## Frozen Profiles

### `topic_research`

- Canonical scenario: `research`
- Route hint: `deep_research`
- Output shape: `research_memo`
- Prompt template override: `research`
- Acceptance sections:
  - `research_question`
  - `key_findings`
  - `evidence`
  - `uncertainties`
  - `implications`
- Evidence policy:
  - `min_evidence_items=3`
  - `require_sources=true`
  - `prefer_primary_sources=true`
  - `require_traceable_claims=true`

### `comparative_research`

- Canonical scenario: `research`
- Route hint: `deep_research`
- Output shape: `research_memo`
- Prompt template override: `research`
- Acceptance sections:
  - `comparison_scope`
  - `comparison_table`
  - `key_findings`
  - `evidence`
  - `recommendation`
  - `uncertainties`
- Evidence policy:
  - `min_evidence_items=4`
  - `require_sources=true`
  - `prefer_primary_sources=true`
  - `require_traceable_claims=true`

### `research_report`

- Canonical scenario: `report`
- Route hint: `report`
- Output shape: `markdown_report`
- Prompt template override: `report_generation`
- Provider hint:
  - `report_type=analysis`
- Acceptance sections:
  - `summary`
  - `research_question`
  - `analysis`
  - `evidence`
  - `risks`
  - `recommendation`
- Evidence policy:
  - `min_evidence_items=4`
  - `require_sources=true`
  - `prefer_primary_sources=true`
  - `require_traceable_claims=true`

## Detection Rules

- Planning packs still resolve first.
- Research packs only resolve after planning misses.
- `research_report` resolves from research-report keywords or `report + research` mixed asks.
- `comparative_research` resolves from comparison-oriented asks.
- `topic_research` is the default research profile once a request is clearly research-shaped.

## Live Consumption

### Strategist

- `research_report` clarifies before execution when completeness is still low and no grounding inputs exist.
- `topic_research` and `comparative_research` clarify only at a lower threshold; explicit-scope research can execute directly.

### `execute_deep_research`

- Reads `scenario_pack`.
- Injects research-profile and evidence-threshold guidance into the KB/deep-research context.

### `execute_report` / `report_graph`

- Passes `scenario_pack` into `report_graph`.
- Derives `report_type` from pack provider hints.
- `web_research` now uses pack-driven evidence thresholds instead of a fixed `>=3` skip rule.

### `standard_entry`

- Resolves and applies research packs before preset recommendation.
- Emits `scenario_pack` in `dispatch_params`.

### `/v1/advisor/consult`

- Builds canonical `task_intake`.
- Resolves and applies research packs.
- Defaults to `deep_research` model set when the resolved pack is research-heavy and caller did not explicitly choose `models` or `mode`.

## Non-goals

- No new controller route type was introduced.
- No change to `build_task_intake_spec()` canonical schema logic.
- No OpenClaw plugin contract change was required for Phase 4.
