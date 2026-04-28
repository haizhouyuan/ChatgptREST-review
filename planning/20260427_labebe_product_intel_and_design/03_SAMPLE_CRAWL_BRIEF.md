# Sample Crawl Brief for Claude/Minimax Worker

Date: 2026-04-27

This brief is for the first sample phase only. Do not crawl all 46 products until the sample fields, method, error handling and QA gates are proven.

## Objective

Create 3-5 high-quality product dossiers that prove the Labebe independent-site plus Amazon intelligence workflow. The output should show exactly what can be extracted reliably, what requires manual review, and which method should be used for the full parallel run.

## Sample Products

Primary sample set:

1. `pink-unicorn-plush-rocker`
   - Independent-site anchor: highest onsite review count in current scrape.
   - Design reason: strongest gift/visual/hero candidate.
2. `cream-wooden-play-kitchen-set-with-storage`
   - Independent-site anchor: strong pretend-play SKU with 9 onsite reviews.
   - Design reason: story-world and short-video potential.
3. `foldable-learning-tower-montessori-kitchen-tower-log-color`
   - Independent-site anchor: utility/furniture category.
   - Design reason: kitchen participation, parent concerns, Amazon-search likely category.
4. `natural-wood-montessori-shelf-with-storage-boxes`
   - Independent-site anchor: storage/Montessori SKU with 9 onsite reviews.
   - Design reason: room organization and playroom-reset path.
5. `activity-cube-baby-push-walker` or current ASIN sample `B087P9SXZQ`
   - Amazon anchor: existing review sample may provide method validation.
   - Design reason: milestone and first-walker content.

## Required Outputs Per Product

Create one dossier per product in Markdown plus one structured JSON/CSV row.

Required sections:

1. Identity
   - Labebe slug
   - cleaned title
   - raw scraped title
   - collection
   - independent-site URL
   - local image paths
2. Independent-site facts
   - price
   - compare-at price if visible
   - discount
   - onsite review count
   - badges
   - PDP bullets/description/specs/FAQ if extractable
   - materials/dimensions/age/certification claims, with source snippets or null
3. Amazon discovery
   - search query used
   - candidate ASINs
   - candidate URLs
   - match confidence
   - why accepted/rejected
   - seller/brand/variation notes
4. Amazon listing facts for accepted ASIN
   - title
   - brand
   - seller/fulfillment if visible
   - price/coupon if visible
   - rating/review count
   - BSR/category/rank if visible or available
   - images/A+ content/video presence
5. Review/VOC summary
   - review rows scraped
   - rating distribution
   - top positive themes
   - top negative themes
   - quoted review IDs, not anonymous fake quotes
6. Design implications
   - homepage eligibility
   - collection role
   - PDP message angle
   - image/video needs
   - bundle/cross-sell ideas
7. Unknowns and risks
   - missing fields
   - crawl failures
   - confidence limits

## Method Comparison

For the sample, compare these paths where credentials/tools allow:

1. Labebe independent-site scrape upgrade
   - collection/listing extraction
   - PDP extraction
   - image gallery classification
2. Amazon public page/manual extraction
   - use as validation, not necessarily full-scale method
3. Existing Apify review actor
   - verify dedupe, rating distribution, quote provenance
4. One product/listing/rank source
   - Apify product/rank actor, Keepa, or another available structured source
5. Search discovery
   - Google/Amazon search only for candidate ASIN discovery

Record for each method:

- fields returned
- field quality
- cost/rate/latency
- failure mode
- whether it should be used in the full run

## QA Gates

The sample passes only if:

- 3-5 dossiers are complete enough for design planning.
- All factual claims have source IDs or are marked unknown.
- ASIN matches include confidence and rejection logic.
- Review text has dedupe and review URL/ID provenance.
- At least two Amazon methods are compared, or a documented constraint explains why not.
- Method lessons are written into `skill_notes/labebe-amazon-product-intel-skill-draft.md`.

## Forbidden

- Do not infer sales volume from review count without labeling it as a weak proxy.
- Do not claim Labebe owns an Amazon listing without evidence.
- Do not generate fake review quotes.
- Do not invent ratings, certifications, awards, safety claims or materials.
- Do not skip sample QA and start full crawl.

## Handoff To Full Run

After sample acceptance, split the full work into:

- PDP enrichment for all 46 independent-site SKUs.
- ASIN discovery and match verification.
- Amazon listing/rank/price extraction.
- Amazon review/VOC extraction.
- Competitor ASIN discovery.
- Image role classification.
- Product-to-design implication matrix.
