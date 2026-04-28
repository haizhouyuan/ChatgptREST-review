# Product Data Inventory

Date: 2026-04-27
Worker: WP-A Product Data QA (Claude Code, delegated)
Write scope: `planning/20260427_labebe_14day_execution/work_products/product_data_qa/`

This inventory enumerates the source-of-truth product data files this worker
inspected, with sizes, hashes, schemas, and limitations. It is the input map
for `LAB-003 Product Master v0 and Data QA`.

## 1. Source files inspected

All paths are relative to repo root `/vol1/1000/projects/toyresearch/`.
Sizes/hashes captured at run time and persisted in
`evidence/source_hashes.json`.

| File | Bytes | mtime | sha256 (head) | Role |
| --- | ---: | --- | --- | --- |
| `data/labebe/labebe_products.csv` | 13 158 | 2026-04-24 | `a1688c94…` | **Canonical** 46-row product listing CSV. Has working `local_image_path` column. |
| `data/labebe/labebe_products_with_images.csv` | 8 973 | 2026-04-24 | `165f51ab…` | Older mirror of the same 46 products. Same slugs but `local_image_path` column is empty. Misleading filename — do not use. |
| `data/labebe/all_product_images.json` | 54 405 | 2026-04-24 | `415e3069…` | PDP-side gallery URL index, 46 keys × 459 image URLs total. Hosts on `media.cdn.ishopastro.com`. |
| `data/labebe/images/` | 460 files (~165 MB) | 2026-04-24 | – | Local download of every gallery image. 47 distinct slug stems (46 + 1 duplicate variant for the desk slug-mismatch). |
| `scrape_labebe.py` | – | – | – | Listing-level Playwright scraper that produced both CSVs and the JSON. Listing-only — does not extract PDP-side fields like dimensions, materials, age, reviews text, etc. |
| `docs/labebe-scrape-report-2026-04-24.md` | 1 563 | 2026-04-25 | – | Hand-written summary of the 2026-04-24 scrape run. Confirms 46 / 460 / collection split. |

This worker did not modify any source file. No external crawl was run. No new
images were downloaded.

## 2. Schema reference for each file

### `labebe_products.csv` (CSV A — canonical)

Columns:

```
slug, title, current_price, original_price, discount, reviews_count,
product_url, image_url, collection, local_image_path
```

- `slug`: trailing path segment of `product_url`. Unique within the file.
- `title`: dirty concatenation of badges + name + prices + reviews.
  See `dirty_title_parse_report_draft.csv` for the parse model.
- `current_price`: `$NN.NN` string. Filled for all 46 rows.
- `original_price`: `$NN.NN` string. **Filled in only 14 / 46 rows even though
  the title carries an MSRP for 40 / 46 rows.** Treat as unreliable.
- `discount`: e.g. `44%`. **Filled in only 8 / 46 rows.** Many products show a
  `$current$original` pair in the title (implied 27–37 % off) but no `-NN%`
  banner. Do not treat empty `discount` as zero.
- `reviews_count`: filled in 32 / 46 rows. **Empty does not mean zero reviews;
  it means the listing card did not render `(N)` for that product on
  2026-04-24.**
- `product_url`: well-formed; `slug` is its trailing segment for all 46 rows.
- `image_url`: **empty in all 46 rows.** The scraper reserves the column but
  the per-PDP image step that fills it never wrote to this CSV.
- `collection`: one of {`rockers-ride-ons`, `pretend-play`,
  `activity-educational-toys`, `furniture`, `new-in`}.
- `local_image_path`: absolute path to the local hero image. Filled for all
  46 rows; **all 46 referenced files exist on disk**.

### `labebe_products_with_images.csv` (CSV B — stale mirror)

Same 46 slugs as CSV A but produced earlier. `local_image_path` is empty for
every row. Filename is misleading. Use CSV A and ignore CSV B as a primary
source.

### `all_product_images.json`

Shape:

```json
{
  "<slug>": {
    "product_url": "https://labebeclub.com/product/<slug>",
    "images": ["https://media.cdn.ishopastro.com/.../<file>.jpg", ...]
  },
  ...
}
```

46 keys, 459 image URLs total (mean 10 per product, range 6–28).

### `data/labebe/images/`

460 files, all `.jpg` (per the scrape report; some are WebP-with-`.jpg`
extension served by the Shopify CDN). Filenames follow `<slug>.jpg` for the
hero and `<slug>_<n>.jpg` for the gallery, n ≥ 2.

47 distinct slug stems exist (one extra is a duplicate slug variant — see
QA report).

## 3. Per-collection counts (from CSV A)

| Collection | Products |
| --- | ---: |
| `furniture` | 17 |
| `rockers-ride-ons` | 13 |
| `pretend-play` | 9 |
| `activity-educational-toys` | 6 |
| `new-in` | 1 |
| **Total** | **46** |

A given product appears in **at most one** collection in this scrape. The
scraper de-duplicates by slug and stops after the first collection where it
sees a slug. Multi-collection membership is therefore unobservable from this
data — recorded as a known unknown.

## 4. Cross-source size reconciliation

| Metric | Value | Source |
| --- | ---: | --- |
| Distinct slugs in CSV A | 46 | `labebe_products.csv` |
| Distinct slugs in CSV B | 46 | `labebe_products_with_images.csv` |
| Distinct keys in JSON | 46 | `all_product_images.json` |
| Distinct slug stems on disk | 47 | `data/labebe/images/` |
| Total image URLs in JSON | 459 | `all_product_images.json` |
| Total image files on disk | 460 | `data/labebe/images/` |
| Image-URL ↔ disk-file delta per product | 0 (after slug normalization) | computed |

The +1 disk stem and +1 disk file are accounted for by **one product whose
listing-side slug differs from its PDP-side slug** (see
`current_data_qa_draft.md` §3 and `slug_image_join_report_draft.csv`).
After applying a single normalization rule the join is clean.

## 5. Out-of-scope sources noted but not used

- `data/amazon_reviews_US_B087P9SXZQ.csv` and `.jsonl`: belongs to
  WP-B (marketplace probe). Not opened or analyzed here.
- `paperclip_runtime_duel/outputs/labebe_wow/`: belongs to WP-C (media
  asset probe). Not opened.
- `labebe_design_reference_pack/`, `research/...`: belong to WP-D
  (design reference mapping). Not opened.

## 6. What is *not* in any of these sources

The following fields appear nowhere in `data/labebe/`:

- product dimensions (assembled, packaging) and weight
- materials, finish, paint/coating
- age min / age max, weight capacity
- safety warnings, certifications (CPSIA, ASTM F963, EN-71, etc.)
- assembly time, parts count, tools required
- shipping dimensions or shipping carrier signals
- variant relationships (color / size / family parent)
- inventory / stock / availability
- review **rating** (stars), review **text**, review dates
- ASIN / UPC / GTIN / SKU code beyond the slug
- structured-data JSON-LD, breadcrumbs, canonical URLs
- shipping, return, warranty policy text
- A+ content, FAQ, Q&A

These are listed explicitly in `do_not_use_fields_draft.md` so that no
downstream worker fabricates them.

## 7. Reproducibility

The CSV/JSON outputs in this directory were produced by running:

```bash
python3 planning/20260427_labebe_14day_execution/work_products/product_data_qa/build_drafts.py
```

That script is in this work-product directory, takes no arguments, reads only
the four source files listed above, and writes only into this directory and
its `evidence/` subdirectory. Re-running is idempotent. Source-side hashes
are captured in `evidence/source_hashes.json` so any drift between rebuilds
is easy to spot.
