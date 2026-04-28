# Labebe Product Fact And Market Crawl Masterplan

Created: 2026-04-27

## Goal

Build a source-backed product and market fact layer before making further website design decisions. The website should be designed from the actual Labebe catalog, product mix, visual assets, review-count signals, and verified marketplace identity, not from a handful of attractive demo SKUs.

## Current Assets Found Locally

| Area | Current file or directory | Status |
|---|---|---|
| DTC catalog | `/vol1/1000/projects/toyresearch/data/labebe/labebe_products.csv` | Existing independent-site product table |
| DTC catalog with images | `/vol1/1000/projects/toyresearch/data/labebe/labebe_products_with_images.csv` | Existing enhanced catalog table |
| Product gallery URL map | `/vol1/1000/projects/toyresearch/data/labebe/all_product_images.json` | Existing slug-to-images map |
| Local product images | `/vol1/1000/projects/toyresearch/data/labebe/images` | Existing image store |
| Product QA draft | `work_products/product_data_qa/product_master_v0_draft.csv` | Existing normalized draft |
| Title parse report | `work_products/product_data_qa/dirty_title_parse_report_draft.csv` | Existing parsing issue report |
| Image join report | `work_products/product_data_qa/slug_image_join_report_draft.csv` | Existing image join audit |
| Media manifest | `work_products/media_asset_probe/downloaded_media_manifest_draft.csv` | Existing image/media quality manifest |
| Brand video manifest | `work_products/media_asset_probe/brand_video_assets_draft.csv` | Existing video index draft |
| Video scene index | `work_products/media_asset_probe/video_scene_index_draft.csv` | Existing scene-level draft |
| Amazon review script | `/vol1/1000/projects/toyresearch/fetch_amazon_reviews_apify.py` | Existing Apify-based sample script |
| Amazon sample reviews | `/vol1/1000/projects/toyresearch/data/amazon_reviews_US_B087P9SXZQ.csv` and `.jsonl` | One ASIN sample only |
| Marketplace method docs | `work_products/marketplace_probe/*` | Existing method and access matrix |
| ASIN identity sample | `work_products/marketplace_identity_sample/asin_candidate_matrix.csv` | Existing sample candidate matrix |

## Critical Gaps

1. **Catalog parse quality is not final.** Some title/price/review fields are polluted or require reparse. The current product master is useful but still a QA draft.
2. **SKU identity is not globally stable.** CSV slug, image JSON slug, local filename, DTC URL, and possible marketplace identifiers still need one canonical entity table.
3. **Marketplace data is sample-grade.** The current Amazon material is one ASIN review sample plus method notes. It must not be treated as full Labebe sales evidence.
4. **Structured product attributes are thin.** Age range, material, dimensions, variants, certifications, assembly, care, package size, shipping, and safety warnings need field-level provenance.
5. **Media needs publishability gates.** Images and videos need usable-for labels: DTC, Boss Gallery, paid ad concept, internal only, or blocked.
6. **Claim gates must be explicit.** No certification, safety, rating, origin, award, market rank, or sales claim can appear in a public-facing artifact unless sourced.

## Method: Sample First, Then Parallel Exhaustive Crawl

### Gate 1: Sample Identity And Extraction

Pick 10-30 representative SKUs across rockers, furniture, pretend play, activity toys, and outdoor play. For each sample SKU, complete the identity and extraction chain before scaling.

Required sample fields:

| Field | Description |
|---|---|
| `sample_sku` | Canonical internal SKU id |
| `canonical_slug` | Normalized Labebe slug |
| `dtc_product_url` | Labebe independent-site product URL |
| `dtc_title_clean` | Clean title after parser audit |
| `dtc_collection` | Current DTC collection/category |
| `dtc_price_current` | Current visible price |
| `dtc_price_original` | Compare-at/original price, if visible |
| `dtc_review_count` | Visible DTC review count, null if absent |
| `dtc_gallery_count` | Number of image URLs captured |
| `local_media_count` | Number of local image/video assets joined |
| `candidate_asin` | Marketplace candidate ASIN, if any |
| `candidate_marketplace_title` | Marketplace title for candidate |
| `identity_match_score` | 0-100 match score |
| `identity_status` | `accepted`, `probable`, `candidate`, `rejected`, `no-match` |
| `match_flags_json` | Evidence flags: title, image, price band, seller, brand, variant |
| `blocked_fields` | Missing fields preventing promotion to fact master |
| `evidence_urls_json` | Source URLs supporting each claim |
| `sample_gate_status` | `pass`, `reject`, or `blocked` |

Gate 1 passes only when:

- At least 3 representative product types reach `identity_status=accepted` or `probable`.
- The parser can produce clean title, price, review count, product URL, and image join for each sample SKU.
- The team has a documented rejection reason for false marketplace candidates.
- The output includes a `claim_gate_log` for fields that cannot be used publicly.

### Gate 2: Parallel Exhaustive Crawl

After Gate 1 passes, run independent parallel workstreams:

| Workstream | Output table | Notes |
|---|---|---|
| DTC catalog recrawl | `product_master_v1.csv` | All DTC products, one canonical row per SKU |
| DTC price/state recrawl | `product_price_v1.csv` | Current/original price, stock, timestamp |
| DTC specs extraction | `product_specs_v1.csv` | Age, materials, dimensions, care, warnings, variants |
| DTC media crawl | `product_media_v1.csv` | URL, local path, hash, role, dimensions, publishability |
| Marketplace identity | `product_marketplace_identity_v1.csv` | ASIN/entity match, evidence, confidence |
| Marketplace reviews | `product_reviews_marketplace_v1.csv` | Only for accepted/probable ASINs |
| Brand video crawl | `brand_video_assets_v1.csv` | Source, scene, SKU relation, usage caveat |
| Claim audit | `claim_gate_log_v1.csv` | Block/pass state for claims used in website/demo |

### Gate 3: Design Readiness

Website design can consume a product only when:

- `product_master_v1` has canonical slug, clean title, product URL, collection, current price, and media.
- Any review/rating display has a source and timestamp.
- Any safety/material/certification claim has an allowed source.
- Media has `dtc_usable=true`.
- Unknown fields are hidden or shown as neutral FAQ placeholders, never filled with attractive guesses.

## Target Data Model

### `product_master_v1.csv`

`sku_id, canonical_slug, title_clean, collection, product_url, dtc_status, source_domain, first_seen_ts, last_seen_ts, scrape_batch_id, parse_quality, notes`

### `product_price_v1.csv`

`sku_id, currency, price_current, price_original, discount_pct, stock_state, source_url, observed_at`

### `product_specs_v1.csv`

`sku_id, age_range, material_json, dimensions_json, weight_json, variants_json, certifications_json, safety_warnings_json, assembly_json, care_json, source_url, field_confidence_json`

### `product_media_v1.csv`

`sku_id, media_id, media_type, source_url, local_path, sha256, width, height, duration_s, role, scene_tags_json, dtc_usable, boss_gallery_usable, paid_media_usable, usage_caveat, observed_at`

### `product_marketplace_identity_v1.csv`

`sku_id, marketplace, asin, marketplace_url, title, seller, price, review_count, rating, identity_status, match_score, match_reason_json, evidence_urls_json, observed_at`

### `claim_gate_log_v1.csv`

`claim_id, sku_id, claim_text, claim_type, requested_surface, source_scope, decision, blocker_reason, evidence_url, reviewer, reviewed_at`

## Implementation Path

1. **Normalize DTC product master.** Start from `labebe_products.csv`, `labebe_products_with_images.csv`, `all_product_images.json`, and local image paths.
2. **Repair parser anomalies.** Use the dirty-title report to separate title, current price, original price, review count, and discount.
3. **Join media deterministically.** Use slug normalization and hash-based duplicate detection.
4. **Run marketplace identity sample.** Do not scrape reviews or sales proxies before ASIN identity is accepted or probable.
5. **Write a crawl run ledger.** Every crawl run needs batch id, command, source, timestamp, output path, and failure notes.
6. **Parallelize only after Gate 1.** Separate DTC recrawl, media crawl, marketplace identity, and specs extraction.
7. **Promote only source-backed rows.** Publishable website and demo assets consume `v1` tables, not raw scrape drafts.

## Acceptance Standard

The fact layer is acceptable when it can answer, for every Labebe product:

- What is this product, which category does it belong to, and where is the source URL?
- What is the visible current price, and when was it observed?
- Which images/videos belong to it, and are they usable for DTC or internal demo?
- What claims can be safely displayed?
- Does it have an accepted/probable marketplace identity, or is marketplace data explicitly unavailable?
- What fields remain unknown and must be hidden or reviewed?

## Immediate Next Work Orders

1. Create `sample_identity_candidate_v1.csv` for 10-30 SKUs using existing DTC files and marketplace candidate workflow.
2. Create `field_mapping_v1.md` mapping existing source fields to target v1 tables.
3. Run the parser repair on a sample of 5 SKUs and compare before/after clean fields.
4. Run ASIN identity on 3 SKUs only, document false-match and no-match cases.
5. Promote only passed sample rows into `product_master_v1_sample.csv`.
