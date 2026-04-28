# Product Fact Execution Update 2026-04-28

## What Changed

- A non-destructive live Labebe catalog probe was run against current collection pages.
- The previous local DTC table had 46 product slugs; the live probe found 60 unique slugs.
- 46 previous slugs were still observed; 14 additional slugs appeared in the live probe.
- 0 previous slugs were not observed in this live probe.
- The extra rows include regional EU variants, new baby-push-walker variants, and site-all-only rows needing category confirmation.

## Catalog Scope Counts

- Total live probe rows: 60
- Core products observed in category probes: 46
- Regional variants: 5
- Site all-only rows needing category confirmation: 9
- Non-product rows to exclude: 0

## Live-Only Rows

| slug                                               | live_title                                            | live_price   | live_collections   |
|:---------------------------------------------------|:------------------------------------------------------|:-------------|:-------------------|
| activity-montessori-baby-push-walker               | Activity Montessori Baby Push Walker                  | $50.99       | all                |
| classic-montessori-baby-push-walker                | Classic Montessori Baby Push Walker                   | $53.99       | all                |
| classic-montessori-baby-push-walker-eu             | Classic Montessori Baby Push Walker(EU)               | $66.64       | all                |
| doll-stroller-baby-push-walker                     | Doll Stroller Baby Push Walker                        | $60.99       | all                |
| farm-themed-baby-push-walker                       | Farm-Themed Baby Push Walker                          | $52.99       | all                |
| farm-themed-baby-push-walker-eu                    | Farm-Themed Baby Push Walker(EU)                      | $67.46       | all                |
| ice-cream-cart-baby-push-walker                    | Ice Cream Cart Baby Push Walker                       | $65.99       | all                |
| learning-tower-montessori-kitchen-tower-gray-eu    | Learning Tower & Montessori Kitchen Tower (Gray) EU   | $86.05       | all                |
| learning-tower-montessori-kitchen-tower-log-color  | Learning Tower & Montessori Kitchen Tower (Log Color) | $76.69       | all                |
| learning-tower-montessori-kitchen-tower-white-eu   | Learning Tower & Montessori Kitchen Tower (White) EU  | $81.61       | all                |
| learning-tower-montessori-kitchen-tower-with-slide | Learning Tower & Montessori Kitchen Tower with Slide  | $107.18      | all                |
| panda-baby-push-walker                             | Panda Baby Push Walker                                | $66.64       | all                |
| tool-bench-baby-push-walker-eu                     | Tool Bench Baby Push Walker(EU)                       | $69.80       | all                |
| wooden-rotating-bookshelf                          | Wooden Rotating Bookshelf                             | $104.99      | all                |

## Amazon / Marketplace Gate 1 Result

Direct Amazon HTML access via curl returned anti-bot/CloudFront 503, so curl is not the default extraction path.
Browser Harness with headless Chrome and explicit wait states successfully captured canonical Amazon PDP text/screenshots for five ASINs.
The existing Apify review export remains useful for review pipeline testing, but review crawling should still wait for accepted/probable identity.

### Browser-Captured Amazon Facts

| asin       | price     |   rating |   review_count | bought_past_month         | sold_by       | ships_from   |
|:-----------|:----------|---------:|---------------:|:--------------------------|:--------------|:-------------|
| B072LXVM36 | $99.99    |      4.7 |          2,657 | 100+ bought in past month | Labebe Store  | Amazon       |
| B07MFXJ28Y | $129.99   |      4.7 |            358 |                           | Labebe Store  | Amazon       |
| B087P9SXZQ | $49.99    |      4.5 |            512 | 100+ bought in past month | Pretty valley | Amazon       |
| B0DSVJB5QH | JPY14,888 |      4.8 |             69 | 50+ bought in past month  | Labebe Store  | Amazon       |
| B0FH1KX7XQ | JPY20,701 |      4.4 |             25 | 50+ bought in past month  | Pretty valley | Amazon       |

### Image Identity Triage

| sku_id                         | asin       |   hash_similarity |   color_similarity | visual_match_status                             |
|:-------------------------------|:-----------|------------------:|-------------------:|:------------------------------------------------|
| pink-unicorn-plush-rocker      | B072LXVM36 |            0.627  |             0.1103 | weak_visual_match_needs_human_review            |
| doll-stroller-baby-push-walker | B087P9SXZQ |            0.5703 |             0.0478 | visual_mismatch_or_different_asset_needs_review |

Human review of screenshots and contact sheets overrides raw similarity scores where the product is clearly the same but the scene differs. Pink Unicorn, Cream Play Kitchen, Llama Rocker, and Fox Rocker now have accepted sample status. `B087P9SXZQ` remains blocked by visual conflict for DTC push-walker reuse.

| sku_id                                                     | candidate_asin   | identity_status                     |   match_score | visual_match_status                             | allowed_use_now                                                                                                                            |
|:-----------------------------------------------------------|:-----------------|:------------------------------------|--------------:|:------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------|
| pink-unicorn-plush-rocker                                  | B072LXVM36       | accepted_browser_visual_sample      |            92 | human_accepted_same_product_scene_differs       | Use as accepted sample for Amazon listing facts and review-crawl pilot with screenshot/contact-sheet evidence.                             |
| cream-wooden-play-kitchen-set-with-storage                 | B0FH1KX7XQ       | accepted_browser_visual_sample      |            91 | human_accepted_same_product                     | Use as accepted marketplace listing sample after claim gate; do not reuse ASTM/EN71 or safety claims without official source verification. |
| llama-plush-rocker                                         | B07MFXJ28Y       | accepted_browser_visual_sample      |            88 | human_accepted_same_product_family              | Use as accepted marketplace listing sample and review-crawl candidate; public DTC copy must stay source-gated.                             |
| fox-plush-rocker                                           | B0DSVJB5QH       | accepted_but_search_mismatch_source |            82 | human_accepted_for_fox_only                     | Use as Fox marketplace listing sample only. Treat the originating Highlander search result as a search-candidate false positive.           |
| activity-cube-baby-push-walker                             | B087P9SXZQ       | rejected_for_current_dtc_sku        |            38 | not_compared_rejected_by_title                  | Keep as marketplace orphan sample for review pipeline testing only.                                                                        |
| doll-stroller-baby-push-walker                             | B087P9SXZQ       | candidate_visual_conflict           |            55 | visual_mismatch_or_different_asset_needs_review | Use only as marketplace method-test candidate; do not use review/VOC as DTC product evidence.                                              |
| foldable-learning-tower-montessori-kitchen-tower-log-color |                  | no_match_us_sample                  |             0 |                                                 | DTC-only design and product facts.                                                                                                         |
| kids-toy-storage-organizer-bookshelf-with-bins             |                  | no_match_us_sample                  |             0 |                                                 | DTC-only design and category architecture.                                                                                                 |

## Decision

Gate 1 is passed for DTC catalog recrawl. Marketplace identity now has four accepted Amazon samples, one search-mismatch warning sample, and one visual-conflict sample. This is enough for a controlled review/VOC pilot, not for broad review crawling.

## 2026-04-28 Expanded Candidate And Visual Gate

After the initial sample method was proven, candidate discovery was expanded across 55 non-regional / non-EU DTC SKUs.

Result:

- 419 Amazon search-candidate rows captured.
- 38 unique top ASINs observed.
- 15 ASIN PDP probes indexed.
- 10 PDP probes are usable fact samples.
- 5 PDP probes are weak or incomplete.
- 28 ASIN-to-SKU rows were sent through the DTC-vs-Amazon visual gate.

Expanded visual gate result:

| Gate status | Count |
|---|---:|
| `visual_probable_same_product` | 1 |
| `visual_needs_human_review_title_promising` | 10 |
| `visual_needs_human_review` | 5 |
| `blocked_weak_pdp_probe` | 11 |
| `blocked_search_false_positive` | 1 |

The contact sheet shows why the gate must remain conservative: Amazon often uses child-in-scene or variant-cluster imagery while the DTC site uses packshots. Machine visual similarity is useful for queueing and blocking, but SKU-to-ASIN promotion still needs human or stronger VLM review.

Human visual review result:

| Human lane | Count |
|---|---:|
| Identity-whitelist candidates | 7 |
| Variant-cluster candidates | 4 |
| Blocked negative examples | 7 |
| Retry / provider rows | 10 |

The first identity-whitelist candidate batch is `crocodile-plush-rocker`, `pink-unicorn-plush-rocker`, `llama-plush-rocker`, `white-swan-plush-rocker`, `fox-plush-rocker`, `cream-wooden-play-kitchen-set-with-storage`, and `blue-squirrel-plush-rocker`.

The identity lanes and review/VOC seed were materialized in `amazon_identity_lanes_v1.csv` and `amazon_review_voc_seed_v1.csv`. The seed is restricted to the seven identity-whitelist candidates and does not authorize public copy or direct browser review crawling.

The next efficient path is:

1. Promote the live Labebe category union as the current DTC catalog probe.
2. Exclude non-product/payment rows from product design.
3. Keep EU/regional variants separate from US DTC and Amazon US matching.
4. Use Browser Harness with wait-state detection as the default ASIN evidence path; keep paid product-data provider as fallback.
5. Use DTC-vs-Amazon contact sheets as the identity promotion queue.
6. Product-detail pages are browser-capturable, but direct browser access to `/product-reviews/<ASIN>` redirected to Amazon sign-in in this run.
7. Run review crawlers only through an authorized review pipeline such as Apify/product-data API or a controlled logged-in browser profile, and only for accepted ASINs first.

## Files

- `live_labebe_catalog_probe.py`
- `live_crawl_20260428/labebe_products_live_probe.csv`
- `live_crawl_20260428/labebe_old_vs_live_slug_diff.csv`
- `live_crawl_20260428/product_master_live_probe_v1.csv`
- `live_crawl_20260428/amazon_identity_sample_v2.csv`
- `live_crawl_20260428/amazon_browser_identity_facts_v1.csv`
- `live_crawl_20260428/amazon_listing_facts_v1.csv`
- `live_crawl_20260428/amazon_claim_gate_v1.csv`
- `live_crawl_20260428/amazon_review_crawl_gate_v1.csv`
- `live_crawl_20260428/amazon_search_candidates_full_v1.csv`
- `live_crawl_20260428/amazon_pdp_probe_facts_v1.csv`
- `live_crawl_20260428/amazon_pdp_probe_index_v1.md`
- `live_crawl_20260428/amazon_dtc_visual_gate_v1.csv`
- `live_crawl_20260428/amazon_dtc_visual_gate_v1.md`
- `live_crawl_20260428/amazon_dtc_visual_human_review_v1.csv`
- `live_crawl_20260428/amazon_dtc_visual_human_review_v1.md`
- `live_crawl_20260428/amazon_identity_lanes_v1.csv`
- `live_crawl_20260428/amazon_identity_lanes_v1.md`
- `live_crawl_20260428/amazon_review_voc_seed_v1.csv`
- `live_crawl_20260428/image_identity_sample/amazon_dtc_image_identity_sample.csv`
- `live_crawl_20260428/image_identity_sample/amazon_dtc_image_identity_contact_sheet.jpg`
- `live_crawl_20260428/image_identity_expanded_v1/amazon_dtc_visual_gate_contact_sheet_v1.jpg`
- `live_crawl_20260428/amazon_B072LXVM36_reviews_browser.json`
- `qa/marketplace_probe/amazon_B072LXVM36_reviews_browser.png`
- `qa/marketplace_probe/amazon_B072LXVM36_desktop_wait.png`
- `qa/marketplace_probe/amazon_B087P9SXZQ_desktop_wait.png`
