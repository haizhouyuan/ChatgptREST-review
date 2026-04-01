# 2026-03-11 Issue-Domain For EvoMap Service Evolution Walkthrough v1

## Why

The previous discussion around `#113` correctly narrowed the Gemini bug, but it
did not fully answer the higher-order question:

- what role `issue_domain` is supposed to play for `EvoMap`
- and how that eventually helps agents evolve the service

This walkthrough records the deeper conclusion.

## What I Verified

### 1. `issue_domain` is already a real canonical plane

Verified current code and docs show:

- authoritative issue state stays in the issue ledger tables
- canonical read surfaces already exist through `issue_canonical.py`
- graph and export routes already prefer canonical with legacy fallback

So `issue_domain` is not just a future idea. It is already the structured
incident/history plane.

### 2. EvoMap is already a real runtime plane

Verified current code shows:

- extractors run through the EvoMap knowledge pipeline when enabled
- retrieval is connected to runtime consumers
- observers and actuators already exist

So the missing piece is not “build EvoMap”. The missing piece is the semantic
bridge from issue lifecycle into governed EvoMap knowledge.

### 3. Direct issue -> retrieval would be unsafe

The current runtime retrieval still accepts:

- `promotion_status=active`
- `promotion_status=staged`

That means raw issue-derived atoms would be dangerous if ingested naively,
because they could leak into normal runtime responses before review.

## Deliverable

I wrote:

- `docs/reviews/2026-03-11_issue_domain_for_evomap_service_evolution_v1.md`

The note defines the correct architecture:

- `issue_domain` as authoritative incident + canonical plane
- `EvoMap` as archive/review/service evolution plane
- a dedicated bridge from canonical issue projection into EvoMap
- promotion rules that keep raw issues out of normal retrieval
- lifecycle signals that let issue history become real evolution feedback

## Main Conclusion

The right path is not:

- “put GitHub issues into EvoMap”

The right path is:

1. intake issue evidence into the authoritative issue ledger
2. normalize it in canonical issue-domain form
3. ingest canonical issue lifecycle into EvoMap archive
4. distill verified lessons into EvoMap service atoms
5. emit issue lifecycle signals so actuators and future agents can learn from them

For `#113`, this means the final reusable service knowledge is the validated
operational rule, not the raw issue thread.

## Outcome

This task reframed the question from:

- “is issue-domain the same thing as EvoMap?”

to:

- “how should issue-domain feed EvoMap so agent evolution stays authoritative,
  governed, and actually useful at runtime?”

That is the correct design question for the next implementation step.
