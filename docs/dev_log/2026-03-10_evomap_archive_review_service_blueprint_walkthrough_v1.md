# 2026-03-10 EvoMap Archive Review Service Blueprint Walkthrough v1

## What I Did

Created a new blueprint document:

- `2026-03-10_evomap_archive_review_service_blueprint_v1.md`

## Why

The recent EvoMap discussion converged on one core issue:

- the system is not missing storage
- it is missing separation between raw capture, semantic review, and
  production service

The blueprint therefore does four things:

- defines `archive / review / service` as separate planes
- explains why `staged` must not remain the default retrieval surface
- explains why current `p4_batch_fix.py` is not a valid bootstrap for the main DB
- turns “agent experience” into explicit objects: correction events and lesson atoms

## Key Decisions Captured

- raw artifacts and all document versions stay in archive
- semantic judgment must be stored as explicit review decisions
- service retrieval should converge toward `active_only`
- the transition needs a bootstrap active set, not a direct hard cut

## Verified Constraints Included

The blueprint explicitly reflects current code/data realities:

- canonical DB is `data/evomap_knowledge.db`
- main DB currently has `95239 staged / 0 active`
- retrieval still allows `staged`
- current `p4_batch_fix.py` only promotes `candidate`

## Why This Matters

Without this separation, EvoMap will keep accumulating content but will not
become a trustworthy memory system.

With this separation, the project gets a clean next step:

- inventory the corpus
- review representative samples
- bootstrap a small trusted service plane
- then tighten retrieval and scale curation

