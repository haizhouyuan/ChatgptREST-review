---
name: "labebe-product-concept-workflow"
description: >
  Use when turning Labebe product, VOC, competitor, or design inputs into
  opportunity clusters, concept briefs, concept image prompts, design review,
  DFM/safety preflight, or launch-test asset drafts. Do not use for Paperclip
  issue mechanics alone.
metadata:
  paperclip:
    tags:
      - product-design
      - voc
      - concept
---

# Labebe Product Concept Workflow

This skill defines the demo workflow from local sample signals to review-ready concept artifacts.

## Input Order

1. Read `docs/DATA_TRUTH.md` and confirm the source boundary.
2. Read `data/products_seed.json`.
3. Read `data/review_signal_samples.csv`.
4. Read `data/competitor_samples.csv`.
5. Read `docs/DESIGN.md` for design principles.

## Output Families

- Opportunity radar: opportunity clusters with evidence labels and open questions.
- VOC requirement map: pain points to product requirements.
- Concept brief: target user, use case, design promise, evidence label, assumptions.
- Image prompt set: four differentiated concept routes with safety caveats.
- Review scorecard: brand fit, usability, differentiation, risk, source support.
- DFM/safety preflight: tipping, pinch, small-part, durability, cleaning, material, cost assumptions.
- Asset matrix: PDP, Amazon A+, TikTok, Meta carousel, Google image brief, email/waitlist draft.

## Gate Rules

- Opportunity radar must pass Data Truth review before concept routes.
- Concept routes must pass Design Director review before asset matrix.
- DFM/safety/cost remains blocked until human engineering review.
- Market assets must stay local draft/demo unless a human approves publication.

## Minimum Artifact Header

Every markdown artifact should start with:

```markdown
# Artifact Title

- Paperclip issue:
- Owner agent:
- Source labels:
- Human review required:
- Output status: draft/demo
```
