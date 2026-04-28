# Marketplace Identity Sample — Amazon First Pass

Generated: 2026-04-27

## Scope

This is not a full Amazon crawl. It is the first identity-mapping pass required
before any Amazon sales, rank, rating, or review-count claims can enter the
Labebe strategy, website design, or boss-demo materials.

## Method Used In This Tranche

- Searched web results for exact Labebe SKU/title phrases plus Amazon.
- Looked for canonical Amazon pages or reliable third-party pages that point to
  Amazon product identity.
- Recorded only candidate identity signals.
- Did not accept third-party rating/review/sales values as product facts.

## Findings

| Finding | Status | Implication |
| --- | --- | --- |
| Pink Unicorn rocker has Amazon-deal/aggregation traces. | Candidate only | Useful for next controlled browser pass, not enough for claims. |
| White Swan rocker has third-party Amazon review/aggregation traces. | Candidate only | Product-family signal, not a match for Pink Unicorn. |
| Learning Tower, Cream Play Kitchen and Storage Organizer did not yield reliable canonical candidates in this quick pass. | Unknown | Must use identity-first search/image matching before broader crawl. |

## Why This Is Not Yet Claim Evidence

Third-party aggregator pages can be stale, scraped from old Amazon states, or
refer to different variants. The current sprint cannot safely use them for:

- ASIN;
- current Amazon title;
- current rating;
- current review count;
- Best Sellers Rank;
- monthly sales or velocity;
- offer/availability.

## Next Method

1. Open canonical Amazon search/product pages through a controlled browser.
2. Capture screenshots, URL, title, brand, seller, main image, and ASIN if
   visible.
3. Score match against DTC SKU by title, image, brand, color/animal, price band,
   and seller/brand presence.
4. Only after a high-confidence identity match, extract marketplace facts.
5. Put each accepted field into a claim ledger with capture date and screenshot.

## Current Decision

Marketplace evidence remains outside consumer-site copy. It can inform research
planning but cannot be used to claim demand or performance.
