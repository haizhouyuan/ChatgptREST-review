# Crawl Run Ledger

Created: 2026-04-27

## Existing Runs

| Run ID | Date | Source | Outputs | Status | Notes |
|---|---|---|---|---|---|
| `dtc_catalog_existing_20260424` | 2026-04-24 | Labebe independent site | `data/labebe/labebe_products.csv`, `data/labebe/labebe_products_with_images.csv`, `data/labebe/all_product_images.json`, `data/labebe/images/` | usable draft | Full DTC catalog base exists, but parser QA still required. |
| `product_data_qa_v0` | 2026-04-27 package | Local DTC scrape files | `work_products/product_data_qa/product_master_v0_draft.csv`, parser and join reports | usable draft | Best current intermediate fact table. |
| `media_asset_probe_v0` | 2026-04-27 package | Local image/video assets | `work_products/media_asset_probe/*.csv` | usable draft | Media publishability still needs final legal/brand review. |
| `amazon_reviews_sample_B087P9SXZQ` | existing | Apify Amazon review script | `data/amazon_reviews_US_B087P9SXZQ.csv`, `.jsonl` | sample only | Single ASIN review sample; not full Labebe market evidence. |
| `marketplace_identity_sample_v0` | 2026-04-27 package | Search/marketplace method probe | `work_products/marketplace_identity_sample/asin_candidate_matrix.csv` | candidate only | No full accepted ASIN map yet. |

## New Sample Promotion

| Run ID | Date | Outputs | Status |
|---|---|---|---|
| `product_master_v1_sample_manual_promotion` | 2026-04-27 | `product_master_v1_sample.csv` | sample fact layer ready for review |
| `sample_identity_candidate_v1_manual_promotion` | 2026-04-27 | `sample_identity_candidate_v1.csv` | marketplace identity sample ready for controlled follow-up |

## Next Controlled Runs

1. `parser_repair_sample_v1`
   - Input: `dirty_title_parse_report_draft.csv`, `product_master_v0_draft.csv`
   - Output: `parser_repair_sample_v1.csv`
   - Goal: prove title/price/review parser repair on 5 SKUs.

2. `marketplace_identity_browser_sample_v1`
   - Input: `sample_identity_candidate_v1.csv`
   - Output: `product_marketplace_identity_v1_sample.csv`
   - Goal: accept/reject candidates using canonical marketplace pages and image/title/seller evidence.

3. `media_publishability_sample_v1`
   - Input: `downloaded_media_manifest_draft.csv`, `brand_video_assets_draft.csv`
   - Output: `media_publishability_sample_v1.csv`
   - Goal: mark DTC usable, internal-only, paid-media blocked, or needs review.

## Gate

Do not run full parallel review/rating crawl until `marketplace_identity_browser_sample_v1` has at least accepted/probable entities and documented false-match cases.
