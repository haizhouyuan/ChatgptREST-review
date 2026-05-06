# 2026-03-10 EvoMap Archive Review Service Execution Plan Walkthrough v2

## What I Added

Created:

- `2026-03-10_evomap_archive_review_service_execution_plan_v2.md`

## Why v2 Exists

`execution_plan_v1` translated the blueprint into phases, but it still lacked
two things the next step now requires:

- a grounded manual read of what is already in `data/evomap_knowledge.db`
- a concrete way to compare multiple reviewer-model lanes before committing to a
  full import/review strategy

This `v2` closes that gap.

## What Changed From v1

The new plan now includes:

1. a manual small-sample audit over the canonical DB
2. concrete inventory numbers by `source`, `project`, and noise bucket
3. a source-by-source decision on who should enter early bootstrap service and
   who should stay archive-only
4. a three-lane review experiment:
   - Codex Spark
   - Gemini CLI
   - Claude via MiniMax
5. explicit comparison metrics and thresholds
6. a final "full archive yes / full service no unless promoted" decision rule

## Most Important Audit Findings Embedded

The plan hard-codes the key things the manual audit already showed:

- the canonical DB is already large enough; the blocker is curation, not sample
  size
- all `95239` atoms are still `staged`
- the service path still reads staged material
- `maint` is the best first-wave bootstrap source
- `planning` is strong but mixed and must be split by family and by
  `planning` vs `research`
- `chatgptrest` is useful but noisy
- `antigravity` is too large/noisy for first-wave default service use
- `agent_activity` belongs in archive/provenance, not default service

## What The Multi-Model Part Is For

The new plan does not assume one reviewer model is best.

Instead it defines:

- one shared review schema
- one manual gold set
- identical review packs for three lanes
- explicit metrics for agreement, noise rejection, service precision, and
  version-family judgment

That gives a practical basis for deciding later:

- which model should become the default semantic reviewer
- which model should be kept as spot-check or tie-break
- whether service widening is safe at all

## Operational Consequence

The biggest practical decision in `v2` is this:

- full archive ingestion is acceptable
- full service exposure is not

So the system should move toward:

- archive everything with provenance
- review everything important by family/topic
- only expose promoted subsets to service retrieval

## Intended Next Step

The next implementation task should start with:

- inventory/report pack generation
- manual `180`-item gold-set review
- three-lane audit run scaffolding

Only after those are in place should the repo change retrieval defaults or try
to bootstrap an `active` set.
