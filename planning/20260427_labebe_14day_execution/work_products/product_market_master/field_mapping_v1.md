# Field Mapping V1

This mapping turns the current Labebe scrape artifacts into the target product fact layer.

## Source Tables

| Source | Current fields | Use |
|---|---|---|
| `data/labebe/labebe_products.csv` | `slug`, `title`, `current_price`, `original_price`, `discount`, `reviews_count`, `product_url`, `image_url`, `collection`, `local_image_path` | Raw DTC product seed |
| `data/labebe/labebe_products_with_images.csv` | product fields plus image-local join fields | Cross-check image availability |
| `data/labebe/all_product_images.json` | slug to image URL arrays | Gallery image count and media URL seed |
| `work_products/product_data_qa/product_master_v0_draft.csv` | `slug_csv`, `slug_json`, `slug_match_status`, `name_clean`, `title_raw`, prices, flags, review count, collection, image counts, `unknown_fields` | Best current normalized source |
| `work_products/product_data_qa/dirty_title_parse_report_draft.csv` | dirty title/parser flags | Parser repair queue |
| `work_products/product_data_qa/slug_image_join_report_draft.csv` | slug/image join results | Media join QA |
| `work_products/marketplace_identity_sample/asin_candidate_matrix.csv` | sample marketplace candidate, source URL, match strength, blocked fields | ASIN identity seed only |

## Target Mapping

### `product_master_v1.csv`

| Target field | Source mapping | Rule |
|---|---|---|
| `sku_id` | `slug_csv` | Use canonical normalized Labebe slug |
| `canonical_slug` | `slug_csv` if `slug_match_status=identical`, otherwise reviewed normalized slug | Do not promote mismatched slug without manual/entity review |
| `title_clean` | `name_clean` | Prefer parser-cleaned title |
| `collection` | `collection_listing` | Keep Labebe collection label |
| `product_url` | `product_url` | Required |
| `dtc_status` | derived | `active` if present in latest scrape |
| `source_domain` | constant | `labebeclub.com` |
| `first_seen_ts` | earliest scrape ledger if available | Unknown allowed |
| `last_seen_ts` | `scrape_date_local` | Required for v1 |
| `scrape_batch_id` | crawl ledger | Required after next recrawl |
| `parse_quality` | derived from dirty parser reports | `clean`, `needs_review`, `blocked` |
| `notes` | `unknown_fields` summary | Keep unknowns explicit |

### `product_price_v1.csv`

| Target field | Source mapping | Rule |
|---|---|---|
| `sku_id` | `slug_csv` | Join to master |
| `currency` | constant | `USD` unless source says otherwise |
| `price_current` | `current_price_usd` | Numeric only |
| `price_original` | `original_price_usd` | Null if absent |
| `discount_pct` | `discount_pct_listed` or `discount_pct_implied` | Use listed if present; otherwise implied with flag |
| `stock_state` | future PDP extraction | Unknown until recrawl |
| `source_url` | `product_url` | Required |
| `observed_at` | `scrape_date_local` | Required |

### `product_media_v1.csv`

| Target field | Source mapping | Rule |
|---|---|---|
| `sku_id` | slug from JSON/CSV join | Required |
| `media_id` | sha256 or deterministic URL hash | Required |
| `media_type` | file extension / probe | `image` or `video` |
| `source_url` | `all_product_images.json` URL or video source URL | Required |
| `local_path` | local downloaded path | Required for publishable use |
| `sha256` | media probe | Required before dedupe |
| `width`, `height`, `duration_s` | media probe | Required before video/presentation use |
| `role` | heuristic + page position | `hero`, `gallery`, `detail`, `scene`, `unknown` |
| `scene_tags_json` | media probe/manual scene tagging | Optional for image, required for video |
| `dtc_usable` | media probe gate | True only if local, non-corrupt, product-relevant |
| `boss_gallery_usable` | media probe gate | Internal/demo can be broader but must be caveated |
| `paid_media_usable` | legal/campaign review | Default false until approved |
| `usage_caveat` | media probe notes | Required if not fully publishable |
| `observed_at` | crawl/probe timestamp | Required |

### `product_marketplace_identity_v1.csv`

| Target field | Source mapping | Rule |
|---|---|---|
| `sku_id` | sample/canonical SKU | Required |
| `marketplace` | method config | `amazon_us`, etc. |
| `asin` | accepted candidate only | Null for candidate/no-match |
| `marketplace_url` | canonical marketplace URL | Required for accepted/probable |
| `title` | marketplace page | Required for accepted/probable |
| `seller` | marketplace page | Capture if visible |
| `price`, `review_count`, `rating` | marketplace page/API | Capture only after identity gate |
| `identity_status` | candidate matrix + gate | `accepted`, `probable`, `candidate`, `rejected`, `no-match` |
| `match_score` | identity scoring | 0-100 |
| `match_reason_json` | title/image/brand/seller/variant evidence | Required |
| `evidence_urls_json` | source URLs | Required |
| `observed_at` | crawl timestamp | Required |

## Promotion Rules

- Raw scrape rows can enter `v0_draft`; only reviewed rows enter `v1`.
- Marketplace review/rating/sales proxies can be collected only after identity reaches `accepted` or `probable`.
- Fields in `unknown_fields` must either be sourced, hidden, or shown as "To be confirmed" in internal docs only.
- Consumer website output must not display parser status, scrape status, AI/demo language, or unsupported claims.
