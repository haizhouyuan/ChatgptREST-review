# 2026-03-10 EvoMap Multi-Model Review Experiment Report v1

## Scope

This round executed the `archive / review / service` experiment against the
canonical EvoMap DB:

- canonical DB: `data/evomap_knowledge.db`
- manual gold benchmark:
  - `41` atom review items
  - `8` family review items
- expanded model-only audit:
  - `72` service-readiness atoms
  - `21` noise/wrapper atoms
  - `18` version/document families
- lanes:
  - `codex_spark`
  - `gemini_cli`
  - `claude_minimax`

Evidence bundle:

- inventory: `artifacts/monitor/evomap/inventory/summary_20260310_round1.json`
- review packs: `artifacts/monitor/evomap/review_packs/20260310_round1/`
- run artifacts: `artifacts/monitor/evomap/review_runs/20260310_round1/`
- normalized comparison: `artifacts/monitor/evomap/review_runs/20260310_round1/summary/`

## Headline Result

No lane met the execution plan thresholds for autonomous semantic review.

This is the important result, not a disappointment:

- raw extractor output still cannot be promoted by a single-model gate
- the review plane must exist before retrieval is tightened to `active` only
- any near-term bootstrap must stay family-scoped and manually governed

## Gold Benchmark

Weighted over `49` manually judged items:

| lane | weighted decision acc | weighted lesson acc | weighted version acc |
|---|---:|---:|---:|
| `codex_spark` | `0.3877` | `0.4081` | `0.6939` |
| `gemini_cli` | `0.4898` | `0.2857` | `0.7959` |
| `claude_minimax` | `0.3673` | `0.7551` | `0.7755` |

Key implications:

- `gemini_cli` was best on top-level decision accuracy and version judgment.
- `claude_minimax` was best on lesson-candidate alignment.
- all three were weak on `service_candidate` precision.
- none was acceptable on `reject_noise` recall.

Atom-level precision/recall remained poor:

| lane | atom service precision | atom reject-noise recall |
|---|---:|---:|
| `codex_spark` | `0.4091` | `0.2000` |
| `gemini_cli` | `0.3793` | `0.2000` |
| `claude_minimax` | `0.3929` | `0.0000` |

## Expanded Audit

### Service-Readiness Pack

Observed distributions:

| lane | coverage | service_candidate | review_queue | archive_only | reject_noise | runtime / 100 items |
|---|---:|---:|---:|---:|---:|---:|
| `codex_spark` | `71/72` | `12` | `35` | `18` | `6` | `48.841s` |
| `gemini_cli` | `72/72` | `54` | `5` | `7` | `6` | `193.315s` |
| `claude_minimax` | `72/72` | `44` | `5` | `11` | `12` | `505.342s` |

Source-level shape was the important signal:

- `codex_spark` was the most conservative on `planning`: only `2/30`
  `service_candidate`, `21/30` pushed to `review_queue`.
- `gemini_cli` marked `30/30 planning` atoms and `12/12 chatgptrest` atoms as
  `service_candidate`.
- `claude_minimax` marked `12/12 maint` atoms and `26/30 planning` atoms as
  `service_candidate`, but rejected `9/12 antigravity` items as noise.

Interpretation:

- `codex_spark` behaves like a conservative triage model.
- `gemini_cli` is semantically assertive but dangerously promotion-biased.
- `claude_minimax` is inconsistent by source and overfit to some source styles.

### Noise/Wrapper Pack

Observed distributions:

| lane | coverage | service_candidate | review_queue | archive_only | reject_noise |
|---|---:|---:|---:|---:|---:|
| `codex_spark` | `20/21` | `11` | `0` | `9` | `0` |
| `gemini_cli` | `21/21` | `6` | `6` | `0` | `9` |
| `claude_minimax` | `21/21` | `12` | `0` | `3` | `6` |

Important common failure:

- all three lanes marked all `3/3` sampled `chatgptrest` noise items as
  `service_candidate`
- this means semantic review alone cannot replace source-aware denylist /
  wrapper gates

### Version/Family Pack

Observed distributions:

| lane | coverage | service_candidate | review_queue | archive_only | reject_noise | runtime / 100 items |
|---|---:|---:|---:|---:|---:|---:|
| `codex_spark` | `18/18` | `8` | `3` | `7` | `0` | `147.733s` |
| `gemini_cli` | `18/18` | `0` | `9` | `5` | `4` | `442.894s` |
| `claude_minimax` | parse failed | `0` | `0` | `0` | `0` | `144.220s` |

Important result:

- `claude_minimax` family output was not safely parseable as contract JSON.
- `codex_spark` over-promoted wrapper/version families such as `answer 渲染修复`
  and `VERSION`-style families.
- `gemini_cli` was more cautious at family level than on atom-level service
  packs.

## Operational Quality

### `codex_spark`

Strengths:

- fastest lane by a wide margin
- cleanest top-level JSON behavior
- most conservative on `planning` service gating

Weaknesses:

- omitted one item from `expanded_service_atoms`
- omitted one item from `noise_atoms`
- no reason strings in expanded outputs
- over-promotes wrapper/version families
- fails noise recall badly

### `gemini_cli`

Strengths:

- best weighted decision accuracy on the gold benchmark
- best reject-noise rate on the expanded noise pack
- fully covered all expanded packs

Weaknesses:

- output schema drifted between `items`, `reviews`, and `review_results`
- outputs were prefixed with non-JSON wrapper text
- repeated MCP discovery errors increased operator friction
- over-promoted `planning` and `chatgptrest` service atoms

### `claude_minimax`

Strengths:

- best lesson-candidate accuracy on the gold benchmark
- split service run completed with full item coverage
- stronger than Codex/Gemini on rejecting `antigravity` items in the expanded
  service pack

Weaknesses:

- full `expanded_service_atoms` run did not return usable output and had to be
  split
- family pack outer JSON failed because quoted family titles broke the payload
- `<think>` leakage appeared in some outputs
- very slow on larger packs
- still over-promoted many `planning` and noise items

## Cross-Lane Agreement

Decision agreement was low:

- `expanded_service_atoms`
  - `codex_spark` vs `gemini_cli`: `0.3380`
  - `codex_spark` vs `claude_minimax`: `0.2394`
  - `gemini_cli` vs `claude_minimax`: `0.5139`
- `noise_atoms`
  - `codex_spark` vs `gemini_cli`: `0.3000`
  - `codex_spark` vs `claude_minimax`: `0.7000`
  - `gemini_cli` vs `claude_minimax`: `0.5714`
- `version_families`
  - `codex_spark` vs `gemini_cli`: `0.3333`

This is decisive:

- the models are not converging on a stable review policy
- the system must treat model outputs as review evidence, not authoritative
  curation decisions

## Decision

### What We Can Conclude Now

1. No model lane should be used for direct `service_candidate -> active`
   promotion.
2. `staged` must eventually leave the default retrieval surface, but only after
   a manually governed bootstrap set exists.
3. source-aware gates are mandatory before LLM review:
   - review-pack wrappers
   - `answer / MANIFEST / CHANGELOG / VERSION`
   - chat/session wrapper artifacts
4. family review is not optional; atom-only review is too unstable.

### Recommended Reviewer Stack

Use a hybrid stack, not a winner-take-all stack:

- `gemini_cli`
  - role: primary semantic reviewer for curated review queues
  - why: highest gold decision accuracy, best noise-pack recall
  - constraint: must go through strict normalization and must not auto-promote
- `codex_spark`
  - role: fast conservative counter-review / triage lane
  - why: lowest latency, strongest tendency to push `planning` into
    `review_queue` instead of over-promoting it
  - constraint: not trusted on wrapper/family noise
- `claude_minimax`
  - role: post-selection lesson extraction or synthesis aid only
  - why: highest lesson alignment
  - constraint: not trusted for classification/gating because of schema and
    batch instability

## Full Import Decision

### Archive Plane

Proceed with archive ingestion.

This includes:

- `planning`
- `research`
- `chatgptrest`
- `antigravity`
- `agent_activity`

Condition:

- provenance preserved
- version families grouped
- wrapper/noise tagged up front

### Review Plane

Required before wider service exposure:

- `document_families`
- `document_reviews`
- `atom_reviews`
- `correction_events`
- `lesson_links`

### Service Plane

Do not widen source-wide service exposure yet.

First bootstrap should stay narrow:

- `maint`: yes, first wave
- `planning / planning`: selective families only
- `planning / research`: selective families only after normalization
- `chatgptrest`: selective families only
- `antigravity`: archive now, defer service
- `agent_activity`: archive only

### Retrieval Cutover

Do not switch directly to `active_only` yet.

Recommended sequence:

1. implement review-plane schema
2. build a manual `active` seed from `maint` and a few planning families
3. ship `active_then_staged_fallback`
4. measure fallback rate and answer quality
5. only then cut to `active_only`

## Round-1 Closing Judgment

Round 1 is sufficient to stop debating whether “one good model prompt” can
solve EvoMap curation.

It cannot.

The correct next step is to build the review plane and use the model lanes as
auditors inside that plane, not as direct promotion authorities.
