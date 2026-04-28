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

## Sample Run Lessons 2026-04-28

Status: DTC live catalog probe validated; marketplace identity sample expanded to five PDP probes; still not ready for broad Amazon review crawling.

What worked:

- A non-destructive Playwright category-union probe is the fastest safe path for current Labebe DTC catalog discovery.
- Probing `/collections/all` alone is insufficient; category pages must be unioned because all-products may not expose every category item consistently.
- The current live probe found 60 unique slugs, while the prior local table had 46; all 46 old slugs were still visible and 14 additional slugs appeared.
- Cleaning promotional tokens (`Quick add`, `NEW!`, `HOT`, discount labels, prices, review counts) must happen before title comparison or ASIN search.
- Regional EU variants and site-all-only products need explicit scope labels before website or marketplace decisions.

What did not work:

- Direct Amazon HTML access via curl returned anti-bot/CloudFront 503; this should not be the default extraction path.
- Browser Harness with headless Chrome plus explicit wait successfully captured canonical Amazon PDP text/screenshots for `B072LXVM36`, `B087P9SXZQ`, `B0FH1KX7XQ`, `B07MFXJ28Y`, and `B0DSVJB5QH`.
- Amazon search pages are usable as candidate discovery, but not as facts. They can return region-specific prices such as JPY, they can produce false positives, and search-card review extraction is less reliable than PDP extraction.
- A local Apify review export for `B087P9SXZQ` was useful for review pipeline testing. The live DTC recrawl also found `doll-stroller-baby-push-walker`, which is a probable DTC match for this ASIN; it is not a match for current `activity-cube-baby-push-walker`.
- Contact-sheet image review upgraded `B072LXVM36` to an accepted Pink Unicorn sample, but downgraded `B087P9SXZQ` to candidate because the DTC and Amazon product images conflict.
- Additional PDP probes accepted `B0FH1KX7XQ` for Cream Wooden Play Kitchen, `B07MFXJ28Y` for Llama Plush Rocker, and `B0DSVJB5QH` for Fox Plush Rocker. `B0DSVJB5QH` was discovered during a Highlander search and must not be mapped to Highlander.
- The full candidate expansion searched 55 DTC SKUs and captured 419 Amazon search-candidate rows with no captcha-like pages observed.
- The PDP probe index now covers 15 ASINs. Ten are usable PDP fact samples; four are weak because social proof/seller data did not appear; one is blank/incomplete.
- The expanded visual gate compared 28 ASIN-to-SKU candidate rows and generated a DTC-vs-Amazon contact sheet. It produced 1 probable same-product row, 10 title-promising human-review rows, 5 additional human-review rows, 11 weak-PDP blocks, and 1 search false-positive block.
- Automated visual similarity is a triage signal, not final truth. Amazon PDPs often use child-in-scene images, storefront banners, or variant-cluster hero images; DTC pages often use packshots. Keep human/VLM review in the promotion loop.
- A first human visual review produced 7 identity-whitelist candidates, 4 variant-cluster candidates, 7 blocked negative examples, and 10 retry/provider rows.
- The identity lanes were materialized into `amazon_identity_lanes_v1.csv`; the authorized review/VOC pilot seed is restricted to seven whitelist candidates in `amazon_review_voc_seed_v1.csv`.
- Current runtime check: `APIFY_TOKEN` / `APIFY_API_TOKEN` is not set, so review/VOC extraction is prepared but not executed.
- Product strategy output should be generated after identity lanes. `labebe_product_strategy_matrix_v1.csv` converts the live catalog into product worlds, website roles, marketplace signal tiers, and next data actions. It is the right bridge from crawl work to site-design work.
- Direct Browser Harness review-page crawl redirected to Amazon sign-in; review crawling needs Apify/product-data API or a controlled logged-in browser profile.
- Search-indexed marketplace mirrors can suggest ASIN candidates, but they are not enough to mark an ASIN accepted.

Current confidence gates:

- DTC catalog probe: usable as `probe_only`, pending PDP/spec/claim recrawl.
- Amazon identity: Pink Unicorn, Cream Play Kitchen, Llama Rocker, and Fox Rocker samples accepted; B087 sample remains visual-conflict candidate.
- Visual promotion: only `fox-plush-rocker` -> `B0DSVJB5QH` reached automatic probable same-product in the expanded gate. Human review promoted seven identity-whitelist candidates: Crocodile, Pink Unicorn, Llama, White Swan, Fox, Cream Play Kitchen, and Blue Squirrel.
- Review VOC: do not use direct browser review page without logged-in/authorized review pipeline; crawl accepted ASINs first.

Preferred next tool path:

1. Browser Harness with explicit wait-state detection for canonical Amazon page capture and screenshots.
2. Amazon search Browser Harness only to discover candidate ASINs, never as final evidence.
3. DTC-vs-Amazon contact sheet generation for candidate identity triage.
4. Human/VLM review for scene/variant-sensitive matches.
5. Paid product-data provider or Apify product-detail actor for identity evidence, if available.
6. Apify review actor only after identity is accepted/probable.
7. Search mirrors only as discovery leads, never as final proof.

Validated output files:

- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/product_master_live_probe_v1.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_identity_sample_v2.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_browser_identity_facts_v1.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_search_candidates_sample_v2.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_search_candidates_full_v1.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_search_candidate_summary_v1.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_pdp_probe_facts_v1.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_pdp_probe_index_v1.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_dtc_visual_gate_v1.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_dtc_visual_gate_v1.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/image_identity_expanded_v1/amazon_dtc_visual_gate_contact_sheet_v1.jpg`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_dtc_visual_human_review_v1.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_dtc_visual_human_review_v1.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_identity_lanes_v1.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_identity_lanes_v1.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_review_voc_seed_v1.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_review_crawl_readiness_v1.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/labebe_product_strategy_matrix_v1.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/labebe_product_strategy_matrix_v1.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_listing_facts_v1.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_claim_gate_v1.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/amazon_review_crawl_gate_v1.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/product_fact_execution_update_20260428.md`
