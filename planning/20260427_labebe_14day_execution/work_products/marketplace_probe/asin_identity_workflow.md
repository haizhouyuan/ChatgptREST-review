# ASIN Identity Workflow v0

Status: Draft
Owner: Codex main controller

## Principle

Amazon reviews, ratings, listings and VOC cannot be used for Labebe design decisions until product identity is scored. The first task is not review crawling; it is SKU-to-ASIN confidence.

## Status Values

| Status | Meaning | Allowed Use |
| --- | --- | --- |
| accepted | Strong match on title, brand, image, variant, price/context | listing facts and VOC sample may be considered after source checks |
| probable | Strong partial match but one ambiguity remains | listing facts may inform hypotheses; VOC not final |
| candidate | Possible match with multiple unresolved conflicts | method testing only |
| rejected | Clear mismatch | blocked |
| no-match | Search/source found no plausible ASIN | record gap |

## Scoring Fields

- Labebe slug.
- Labebe product title.
- Labebe category.
- Labebe image fingerprint or visual match note.
- Candidate ASIN.
- Amazon title.
- Amazon brand/seller if visible.
- Amazon images match.
- Variant/color match.
- Price range match.
- Feature/material overlap.
- Review marketplace/language.
- Source URL.
- Capture date.
- Confidence status.
- Blocking conflicts.

## Minimal Sample

The sample must include:

- Pink Unicorn Plush Rocker.
- Cream or Midnight Play Kitchen.
- Learning Tower variant.
- One near-duplicate furniture SKU.
- One low/no-review important product.
- ASIN `B087P9SXZQ` mapping check.
- One expected no-match product.
- One slug/data mismatch sample.

## Forbidden

- do not treat `B087P9SXZQ` as mapped until scored;
- do not use Amazon reviews as VOC before accepted/probable identity;
- do not claim demand/sales from reviews alone;
- do not mix marketplace/language without tagging;
- do not start full review crawl before method review.

