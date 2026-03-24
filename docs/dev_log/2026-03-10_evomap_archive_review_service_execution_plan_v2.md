# 2026-03-10 EvoMap Archive Review Service Execution Plan v2

## Goal

Turn the `archive / review / service` blueprint into an executable program with
three concrete outputs:

1. a verified manual understanding of what is already in the canonical DB
2. a multi-model audit plan that can compare reviewer quality across lanes
3. a final decision gate for what may be fully archived, what may enter review,
   and what may become service-visible knowledge

This version supersedes `execution_plan_v1` by adding:

- a concrete manual small-sample audit over the canonical DB
- a three-lane LLM review plan using Codex Spark, Gemini CLI, and Claude via
  MiniMax
- a source-by-source full-import decision path

## Authoritative Baseline

Canonical DB:

- `data/evomap_knowledge.db`

Verified on `2026-03-10`:

- `atoms_total = 95239`
- `promotion_status='staged' = 95239`
- `promotion_status='active' = 0`
- `promotion_status='candidate' = 0`
- `groundedness_audit = 0`
- `promotion_audit = 0`

Current retrieval reality:

- retrieval default still admits `active + staged`
- the filter also does not reject blank `promotion_status`
- current service retrieval therefore still reads unreviewed material

Current promotion reality:

- `p4_batch_fix.py` only promotes `candidate -> active`
- the canonical DB currently has `candidate = 0`
- current P4 script is not a valid bootstrap path for the canonical DB

## Manual Small-Sample Audit

This plan incorporates a manual audit over the canonical DB before any broader
LLM audit is run.

### Inventory Snapshot

Documents by `source`:

- `planning = 3350`
- `chatgptrest = 2213`
- `antigravity = 1113`
- `maint = 446`
- `agent_activity = 4`

Important `source/project` cross-overs:

- `planning / planning = 2399`
- `planning / research = 951`
- `chatgptrest / ChatgptREST = 2213`
- `antigravity / antigravity = 1113`
- `maint / infrastructure = 446`

Implication:

- research material is already present in the canonical DB, but it is currently
  folded under `source='planning'` and `project='research'`
- future import policy must normalize this instead of pretending research is a
  cleanly separated source today

Atoms by document source:

- `antigravity = 50783`
- `planning = 40901`
- `chatgptrest = 2475`
- `maint = 438`
- `agent_activity = 275`

Status drift is already visible:

- `planning` atom status is split across `reviewed=35769`, `draft=4518`,
  `active=614`
- but `promotion_status` is still `staged` for all `40901` planning atoms

Implication:

- `status` and `promotion_status` are not currently reliable synonyms
- service eligibility must be decided from an explicit review-plane decision,
  not inferred from legacy status labels

### Source-Level Findings

#### `maint`

Observed pattern:

- highest signal density
- mostly operational procedures, incident fixes, inventory reports, and
  governance notes
- good standalone value and strong actionability

Decision:

- first-wave bootstrap source for `active`

#### `planning`

Observed pattern:

- strongest mixed source
- contains both high-value diligence/procedure material and heavy process noise
- `2399` docs belong to project `planning`
- `951` docs belong to project `research` but are still stored under
  `source='planning'`

Noise indicators already visible:

- `_review_pack` docs: `1101`
- `title like 'answer%'`: `286`
- `title in MANIFEST/CHANGELOG/VERSION`: `58`
- `raw_ref like '%/answer%.md'`: `499`

Decision:

- do not bulk-promote by source
- split by family and project before review
- treat `planning/planning` and `planning/research` as separate review queues

#### `chatgptrest`

Observed pattern:

- strong long-form reviews and operational guidance exist
- mixed with OCR verification prompts, screenshot extraction, file-open failure
  responses, and one-off asks

Decision:

- second-wave bootstrap candidate after stricter semantic review
- reject or archive trivial interaction artifacts

#### `antigravity`

Observed pattern:

- largest source by atom count
- contains many useful analyses and design outputs
- also contains heading-like fragments, duplicated conversation shards, and
  blank `canonical_question`

Noise indicator:

- `quality_auto >= 0.8` but blank `canonical_question`: `167`

Version/noise indicators:

- repeated conversation-title families are common
- many top titles are prompt scaffolding or conversation wrappers rather than
  reusable knowledge

Decision:

- keep in archive first
- do not use as first-wave default service source
- review by family/topic, not by raw source-wide promotion

#### `agent_activity`

Observed pattern:

- provenance and execution bookkeeping
- useful as trace/evidence material
- weak direct service value

Decision:

- archive only by default
- do not expose to service retrieval except as explicit debug/provenance context

### Manual Audit Conclusion

The current canonical DB is already large enough to stop asking
"is the schema big enough to test?".

The real issue is different:

- the archive plane is already large
- the review plane does not yet exist
- the service plane still reads staged material

That means the next step is not "import even more first and see later". The
next step is:

1. inventory and segment what already exists
2. use a structured multi-model audit to measure reviewer quality
3. bootstrap a small trusted `active` set
4. only then widen import/service scope

## Execution Principles

1. Preserve full archive provenance; never destroy raw versions.
2. Do not equate extractor output with service-ready knowledge.
3. Add review-plane objects before expanding service-visible content.
4. Default retrieval must eventually move to `active`-first behavior.
5. Model comparison should be evidence-driven, not preference-driven.

## Phase 0: Freeze And Inventory

### Objective

Create a reproducible audit baseline from the canonical DB only.

### Planned outputs

- `artifacts/monitor/evomap/inventory/summary_YYYYMMDD.json`
- `artifacts/monitor/evomap/inventory/source_breakdown_YYYYMMDD.csv`
- `artifacts/monitor/evomap/inventory/version_family_candidates_YYYYMMDD.csv`
- `artifacts/monitor/evomap/inventory/noise_buckets_YYYYMMDD.csv`

### Planned helper scripts

- `ops/evomap_inventory_report.py`
- `ops/evomap_build_review_packs.py`

### Acceptance

- inventory is reproducible from `data/evomap_knowledge.db`
- no dependency on legacy `~/.openmind/evomap_knowledge.db`

## Phase 1: Manual Gold Set

### Objective

Create a human-audited benchmark before trusting any model lane.

### Sampling design

Build one stratified gold set from the canonical DB:

- `maint`: 30 atoms
- `planning / planning`: 40 atoms
- `planning / research`: 30 atoms
- `chatgptrest`: 30 atoms
- `antigravity`: 40 atoms
- `agent_activity`: 10 atoms

Total: `180` atoms

Also build two special packs:

- `version_family pack`: 40 document/version families
- `noise pack`: 40 items from `answer/MANIFEST/CHANGELOG/VERSION/OCR wrapper`
  style buckets

### Manual review checklist

Each item must be judged on:

- `worth_keeping`
- `service_readiness`
- `standalone_comprehensibility`
- `actionability`
- `long_term_reuse`
- `version_sensitivity`
- `duplication_risk`
- `conflict_risk`
- `lesson_candidate`

Allowed decisions:

- `service_candidate`
- `review_queue`
- `archive_only`
- `reject_noise`

### Acceptance

- gold set is reviewed by hand before model comparison
- each item has an explicit decision and short rationale

## Phase 2: Shared LLM Review Contract

### Objective

Make all model lanes evaluate the same material under the same output schema.

### Review input unit

Each review item should contain:

- `item_id`
- `doc_id`
- `atom_id`
- `source`
- `project`
- `title`
- `raw_ref`
- `atom_type`
- `canonical_question`
- `answer_excerpt`
- `status`
- `promotion_status`
- optional `family_context`
- optional `near_duplicate_context`

### Required output schema

```json
{
  "pack_id": "string",
  "lane": "codex_spark|gemini_cli|claude_minimax",
  "items": [
    {
      "item_id": "string",
      "decision": "service_candidate|review_queue|archive_only|reject_noise",
      "confidence": 0.0,
      "dimensions": {
        "standalone_comprehensibility": 1,
        "actionability": 1,
        "long_term_reuse": 1,
        "version_sensitivity": 1,
        "duplication_risk": 1,
        "conflict_risk": 1
      },
      "version_relation": "singleton|latest|supersedes_prior|supplement|conflict|needs_family_review",
      "lesson_candidate": false,
      "reason": "short explanation"
    }
  ],
  "lane_summary": {
    "service_candidate_count": 0,
    "review_queue_count": 0,
    "archive_only_count": 0,
    "reject_noise_count": 0
  }
}
```

### Rule

- no lane may silently rewrite source facts
- all reviewer judgments must be additive review records

## Phase 3: Multi-Model Expanded Audit

### Objective

Compare reviewer quality across three lanes before choosing a default review
stack.

### Lanes

#### Lane A: Codex Spark

Use Codex non-interactive CLI with Spark model:

```bash
codex exec \
  -C /vol1/1000/projects/ChatgptREST \
  -m openai-codex/gpt-5.3-codex-spark \
  -s workspace-write \
  -a never \
  "$(cat artifacts/monitor/evomap/review_packs/pack_01_prompt.txt)"
```

#### Lane B: Gemini CLI

Use Gemini headless prompt mode with JSON output:

```bash
gemini \
  -m gemini-2.5-pro \
  --approval-mode plan \
  --output-format json \
  -p "$(cat artifacts/monitor/evomap/review_packs/pack_01_prompt.txt)"
```

#### Lane C: Claude via MiniMax

Use the existing `claudeminmax` alias or equivalent env-wrapped `claude -p`
runner as documented in
`docs/reviews/03_AIOS_REQUIREMENTS_BACKGROUND.md`.

```bash
claudeminmax -p "$(cat artifacts/monitor/evomap/review_packs/pack_01_prompt.txt)"
```

### Expanded audit packs

After the manual `180`-item gold set is defined, run a broader model-only audit
over:

- `service-readiness pack`: 240 atoms
- `version-family pack`: 80 document/version families
- `noise-and-wrapper pack`: 80 items

Total expanded LLM workload:

- `400` review units per lane

### Required artifacts

Per lane:

- `artifacts/monitor/evomap/review_runs/<run_id>/<lane>/raw_output.json`
- `artifacts/monitor/evomap/review_runs/<run_id>/<lane>/normalized_output.json`
- `artifacts/monitor/evomap/review_runs/<run_id>/<lane>/metrics.json`

Cross-lane:

- `artifacts/monitor/evomap/review_runs/<run_id>/comparison.md`
- `artifacts/monitor/evomap/review_runs/<run_id>/agreement_matrix.csv`

## Phase 4: Lane Comparison And Selection

### Objective

Choose the default semantic reviewer stack from evidence.

### Metrics

Measure each lane on:

- JSON/schema validity rate
- agreement with manual gold set
- precision of `service_candidate`
- recall of `reject_noise`
- accuracy on `latest/supersede/conflict` judgments
- blank-context failure rate
- operator friction
- runtime per 100 items

### Recommended pass thresholds

- schema validity: `>= 0.98`
- overall gold-set agreement: `>= 0.80`
- `service_candidate` precision: `>= 0.90`
- `reject_noise` recall: `>= 0.80`
- version-family judgment accuracy: `>= 0.70`

### Decision rule

- best lane becomes primary reviewer
- second lane becomes spot-check / tie-break reviewer
- third lane stays experimental unless it clearly wins on one dimension

If no lane meets threshold:

- do not widen service ingestion
- keep manual-first review for `maint` and narrow `planning` families only

## Phase 5: Review Plane Implementation

### Objective

Land the schema needed to store review decisions without mutating archive truth.

### Required tables

- `document_families`
- `document_family_members`
- `document_reviews`
- `atom_reviews`
- `correction_events`
- `lesson_links`

### Design rule

- archive rows remain authoritative raw truth
- review verdicts are separate records
- service eligibility is computed from review + governance, not from extractor
  output alone

## Phase 6: Bootstrap Active Set

### Objective

Create the first trusted `active` slice.

### First-wave scope

- all reviewed `maint` service candidates
- selected `planning / planning` families
- selected `planning / research` families
- selected `chatgptrest` families

Deferred:

- `antigravity`
- `agent_activity`

### Admission gate

An atom may enter first-wave `active` only if:

- it passed manual or high-confidence model review
- it is not tagged `reject_noise`
- it is not in unresolved version conflict
- it is standalone enough for retrieval context
- it has acceptable duplication/conflict scores

### Retrieval cutover sequence

1. ship explicit retrieval mode support
2. start in `active_then_staged_fallback`
3. measure fallback rate and hit quality
4. switch default to `active_only`
5. keep `debug_all` for diagnosis only

## Phase 7: Full Import Decision

### Objective

Separate "full archive ingestion" from "full service exposure".

### Decision

#### Archive plane

Full archive ingestion is allowed after:

- provenance is preserved
- version-family grouping is available
- low-value wrappers are tagged, not mistaken for service knowledge

This applies to:

- planning
- research
- chat histories
- agent histories
- future structured note/report imports

#### Review plane

All newly imported material must enter review by family/topic, not default
service exposure.

#### Service plane

Full service exposure is not allowed source-wide.

Service exposure must be:

- family-scoped
- review-backed
- reversible

### Source-specific import stance

- `maint`: yes for archive, yes for early service bootstrap
- `planning / planning`: yes for archive, selective service only
- `planning / research`: yes for archive, selective service only after source
  normalization
- `chatgptrest`: yes for archive, selective service only
- `antigravity`: yes for archive, defer service
- `agent_activity`: yes for archive, no default service

## Recommended Immediate Next Tasks

1. Build inventory and review-pack generator scripts.
2. Create the manual `180`-item gold set.
3. Run the three-lane expanded audit over identical packs.
4. Compare lane quality and select the primary reviewer.
5. Implement review-plane schema.
6. Bootstrap a small `active` set and move retrieval to
   `active_then_staged_fallback`.

## Core Decision

The system should stop treating raw extractor output as service knowledge.

The correct long-term operating model is:

- full raw archive is acceptable
- semantic review is mandatory
- service exposure is a gated promotion outcome

That is the path that supports future large-scale import of planning, research,
and agent-history material without polluting the answer surface.
