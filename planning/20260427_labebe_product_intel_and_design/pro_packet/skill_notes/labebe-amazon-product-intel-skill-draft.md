# Draft Skill Notes: Labebe / Amazon Product Intelligence

Status: draft, not yet installed
Date: 2026-04-27

This file records what should become a reusable Codex skill after the sample crawl proves the method. Do not install this as a finished skill until the sample run validates the workflow.

## Trigger

Use this skill when a task asks for product intelligence across:

- a brand's DTC/independent site;
- Amazon listings, reviews, ranks or sales proxies;
- SKU-to-ASIN mapping;
- product facts and design/marketing implications.

## Principle

Start with a sample. Do not run the full catalog until the fields, extraction methods, QA rules and confidence model work on 3-5 representative SKUs.

## Standard Workflow

1. Inventory local and official brand sources.
2. Clean product master:
   - slug
   - raw title
   - canonical title
   - collection
   - product URL
   - prices
   - review count
   - main image
3. Enrich DTC PDPs:
   - copy
   - specs
   - dimensions
   - materials
   - age guidance
   - certifications
   - FAQ
   - media roles
4. Discover Amazon candidate ASINs:
   - brand + product title search
   - image/title matching
   - seller/brand verification
   - variation handling
5. Verify ASIN match confidence:
   - exact product/title/image match
   - brand evidence
   - seller/variation notes
   - conflict notes
6. Extract Amazon listing facts:
   - title
   - price/coupon
   - rating/review count
   - BSR/rank/category
   - bought-past-month if visible
   - images/A+ content
   - availability
7. Extract and dedupe reviews:
   - review ID/URL
   - rating
   - date
   - verified purchase
   - helpful votes
   - body
   - language/marketplace
8. Summarize VOC:
   - positive themes
   - negative themes
   - product improvement implications
   - PDP reassurance implications
   - marketing angle implications
9. Record source IDs and confidence for every factual field.
10. Write method lessons before parallelizing.

## Required Confidence Labels

- `verified`: strong source match and source URL/path recorded.
- `probable`: good match but one field or seller detail needs manual review.
- `candidate`: discovery lead only.
- `rejected`: considered but not matched, with reason.
- `unknown`: not found or not safely inferable.

## Forbidden Defaults

- Do not invent missing ratings or review counts.
- Do not convert review count into sales without explicit proxy language.
- Do not assume a marketplace listing is official.
- Do not treat AI-generated text/images as evidence.
- Do not use screenshots or generated concepts as product facts.

## Output Artifacts

- `product_master.csv`
- `amazon_match_candidates.csv`
- `product_dossiers/*.md`
- `review_quotes.csv`
- `voc_summary.csv`
- `method_comparison.md`
- `crawl_errors.csv`
- `design_implications.csv`

## Maint Record To Write After Sample

Location to be decided under `/vol1/maint`.

Record:

- tools tested
- credentials required
- average runtime and cost
- field coverage
- rate-limit or anti-bot issues
- recommended default path
- fallback path
- sample QA results
- full-run batch plan
