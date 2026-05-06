# 2026-03-10 EvoMap Archive Review Service Blueprint v1

## Purpose

This blueprint defines the next EvoMap architecture step after the runtime DB
cutover:

- keep all raw artifacts and versions
- separate review/governance from raw ingest
- stop treating `staged` atoms as production-quality knowledge
- build a small trustworthy `active` service plane before scaling import

The goal is not to replace extractor code with AI. The goal is to stop
confusing raw capture with curated knowledge.

## Verified Current State

As of 2026-03-10, the canonical EvoMap knowledge DB is
`data/evomap_knowledge.db`.

Verified runtime facts:

- `atoms_total = 95239`
- `promotion_status='staged' = 95239`
- `promotion_status='active' = 0`
- `groundedness_audit = 0`
- `promotion_audit = 0`

Verified code facts:

- retrieval still allows `staged` atoms:
  - `allowed_promotion_status = (active, staged)`
- retrieval also accepts `candidate` status in `min_status`
- `p4_batch_fix.py` promotes only `candidate -> active`
- the current main DB has `candidate = 0`
- `p4_batch_fix.py` comments mention groundedness, but the implementation does
  not enforce groundedness before promotion

Implication:

- today the service plane is effectively reading unreviewed material
- tightening retrieval to `active` immediately would produce an empty corpus
- the current P4 script is not a valid bootstrap path for the main DB

## Core Principle

EvoMap needs three separate planes:

1. `Archive plane`
2. `Review plane`
3. `Service plane`

Raw truth belongs in archive.
Semantic judgment belongs in review.
Only trusted, promoted outputs belong in service.

This follows the same pattern that worked in the issue-domain pilot:

- authoritative source stays reconstructable
- projection and retrieval stay derived
- governance decisions are explicit, replayable, and auditable

## Plane 1: Archive

Archive keeps the full raw record.

Objects:

- documents
- episodes
- raw extracted atoms
- all document versions (`v1`, `v2`, `v3`, ...)
- source provenance
- content hashes

Rules:

- archive is append-friendly
- archive is not the default retrieval surface
- old versions are not deleted
- old versions may be marked `superseded`, but remain queryable for audit

Important:

- version explosion is acceptable in archive
- version explosion is not acceptable in service

## Plane 2: Review

Review is the semantic curation layer that does not exist yet in a complete
form.

It should answer questions like:

- Is this worth keeping?
- Is this independently understandable?
- Is it reusable or purely local chatter?
- Does it supersede an older version?
- Does it conflict with an older conclusion?
- Is the change itself the valuable artifact?

### Required review objects

The review plane should add explicit records, not silently overwrite atoms:

- `document_family`
  - groups multiple document versions under one topic/family
- `document_review`
  - verdict for one document version
- `atom_review`
  - verdict for one extracted atom
- `correction_event`
  - records why a previous understanding was wrong
- `lesson_atom`
  - reusable distilled correction or operating rule

### Review verdicts

For documents:

- `keep`
- `supersede_previous`
- `supplement_previous`
- `conflict_needs_review`
- `archive_noise`

For atoms:

- `accept`
- `revise`
- `reject`
- `defer`

### Semantic checklist

This checklist should be answered by AI review and stored as structured fields:

- `standalone`: can this be understood outside the original conversation?
- `reusable`: is this useful beyond the local thread/file?
- `actionable`: can it guide a future action or decision?
- `grounded`: does it cite code/config/evidence clearly enough?
- `time_sensitivity`: evergreen / versioned / ephemeral
- `duplication`: exact duplicate / near duplicate / novel
- `correction_value`: does this encode a reusable mistake correction?
- `service_eligibility`: should this ever appear in default retrieval?

The output of review should be a stored decision, not just a score.

## Plane 3: Service

Service is the default retrieval surface used by advisor/runtime.

Rules:

- default retrieval should prefer `active`
- `staged` must not remain default-visible forever
- `staged` may be used only as an explicit fallback during bootstrap
- fallback results must be tagged as unreviewed if they are ever surfaced

### Service retrieval modes

The runtime should support explicit modes:

- `active_only`
- `active_then_staged_fallback`
- `debug_all`

Default target state:

- production default: `active_only`
- temporary bootstrap mode: `active_then_staged_fallback`

This avoids two bad outcomes:

- serving all `staged` content forever
- switching to `active_only` while `active = 0`

## Version Handling Model

The important unit is not only the document body. It is the change between
versions.

Recommended version policy:

1. Keep all versions in archive.
2. Build a `document_family` for related versions.
3. Compare latest vs previous.
4. Let review classify the relationship:
   - `supersede`
   - `supplement`
   - `conflict`
5. Extract `lesson_atom` only when the change is reusable.

Examples of reusable changes:

- a path/location correction
- a measurement correction
- a rule about how to verify a claim
- a governance rule derived from repeated mistakes

Examples that should not become lesson atoms:

- cosmetic wording changes
- one-off context-specific edits
- partial notes that only make sense in the original thread

## What Counts As Agent Experience

Agent experience is not “all past outputs”.

Agent experience should be modeled as:

- `raw artifact`
- `reviewed correction`
- `reusable lesson`
- `validated procedure`

That means:

- a wrong v1 is still valuable as provenance
- the v1 -> v2 correction may be more valuable than either document alone
- the reusable outcome should be a lesson/procedure atom, not a copy of both docs

## Bootstrap Strategy

The main DB cannot jump directly from “95k staged” to “active-only retrieval”.

Bootstrap should happen in four steps.

### Step 1: Corpus inventory

Build an inventory over the canonical DB:

- by `source`
- by `project`
- by `status`
- by `promotion_status`
- by `version_family`
- by noise buckets (`answer`, `manifest`, `review_pack`, etc.)

Deliverable:

- one inventory report
- one version-family report

### Step 2: Stratified sample audit

Do not review the whole corpus first.
Review a representative sample.

Sampling dimensions should include:

- source
- status/promotion_status
- likely version families
- likely noise patterns
- likely high-value operational content

Review output should estimate:

- keep rate
- reject rate
- revise rate
- reusable correction rate
- source-specific threshold recommendations

### Step 3: Bootstrap active set

Create a small trusted service slice.

This is not “run current P4 as-is”.

Instead:

- select one or two higher-signal sources first
  - likely `maint`
  - likely a curated subset of `planning`
- run review decisions on sampled families/atoms
- promote only reviewed, grounded, reusable items
- keep the initial active set intentionally small

### Step 4: Tighten retrieval

After bootstrap active set exists:

- switch runtime default from `active + staged` to `active_then_staged_fallback`
- observe hit quality
- then switch default to `active_only`

## Why Current P4 Is Not The Bootstrap

Current `p4_batch_fix.py` is useful as a maintenance script for a prepared
candidate set, but it should not be treated as the main bootstrap mechanism for
the canonical DB.

Reasons:

- it only processes `promotion_status='candidate'`
- the main DB currently has zero candidates
- it does not actually enforce groundedness despite the comment header
- it would not create a review audit model

The bootstrap path must create:

- candidate selection
- review verdicts
- audit records
- explicit promotion reasons

## Self-Cleaning Mechanisms

The system becomes self-cleaning only when it can demote or supersede earlier
knowledge based on new evidence.

Required feedback loops:

1. `version supersession`
   - newer reviewed version can supersede an older one
2. `conflict detection`
   - semantically similar atoms with opposite claims trigger review
3. `usage feedback`
   - retrieved atom later judged wrong/useless should lose service weight
4. `revalidation`
   - versioned/ephemeral atoms should be rechecked periodically
5. `lesson extraction`
   - repeated correction patterns become durable lesson atoms

Without these loops, the system only accumulates. It does not learn.

## Recommended Schema Additions

The following additions are recommended before large-scale new import:

- `document_families`
- `document_family_members`
- `document_reviews`
- `atom_reviews`
- `correction_events`
- `lesson_links`

Minimum fields should include:

- stable ids
- verdict
- reason
- reviewer/actor
- evidence refs
- supersedes/conflicts_with links
- timestamps

## Recommended Order Of Work

1. Inventory the canonical DB and cluster version families.
2. Run a stratified sample audit.
3. Design and land the review-plane schema.
4. Build a small bootstrap active set.
5. Change runtime retrieval to `active_then_staged_fallback`.
6. Observe quality and active coverage.
7. Move production default to `active_only`.
8. Only then expand import/review throughput.

## Non-Goals

This blueprint does not propose:

- deleting historical versions
- replacing all extractors with LLM
- doing a full-corpus manual review
- blindly importing scratch DB rows into main DB
- treating every document diff as a lesson atom

## Immediate Next Artifact

The next design artifact should be a concrete implementation plan for the review
plane, including:

- schema DDL
- batch review flow
- bootstrap active-set runbook
- retrieval cutover sequence

