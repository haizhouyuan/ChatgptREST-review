# Amazon / Marketplace Tool Method Comparison v0

Status: Draft
Owner: Codex main controller

## Current Local Inputs

- `fetch_amazon_reviews_apify.py`
- `data/amazon_reviews_US_B087P9SXZQ.csv`

## Method Ranking For This Sprint

1. **Manual/public candidate ASIN search for 6-8 sample SKUs**
   - best for identity scoring;
   - low setup overhead;
   - must record URL/capture date and conflicts.

2. **Local CSV sample analysis**
   - useful to understand available review fields and risks;
   - not usable as VOC until ASIN identity is validated.

3. **Existing Apify script inspection**
   - useful if configured;
   - should not be run at full scale before identity workflow is accepted.

4. **Paid/API data paths**
   - potentially higher quality;
   - deferred until sample method proves value or user supplies access.

## Decision

For the first sprint, Amazon work is identity-first and sample-limited. The output required before design is not a large review corpus; it is `asin_match_scoring.md` with accepted/probable/candidate/rejected/no-match states.

