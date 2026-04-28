# Authorized Review / VOC Execution Update v1

Date: 2026-04-28

## What Changed

The Amazon review/VOC gate is still blocked for real extraction until an
authorized provider token or controlled logged-in browser policy is available.
However, the execution path is now concrete and repeatable.

New scripts:

- `product_market_master/amazon_authorized_review_voc_runner.py`
- `product_market_master/build_review_voc_summary.py`

## Dry-Run Result

Command:

```bash
python3 planning/20260427_labebe_14day_execution/work_products/product_market_master/amazon_authorized_review_voc_runner.py \
  --out-dir planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/authorized_reviews \
  --marketplace US \
  --max-reviews 100 \
  --sorts recent helpful
```

Result:

- eligible identity-whitelist rows: 7
- external calls made: `false`
- gate status: `dry_run_no_external_calls`
- planned provider calls per ASIN: 10
  - 2 sorts: `recent`, `helpful`
  - 5 star filters: `five_star`, `four_star`, `three_star`, `two_star`, `one_star`
- public copy allowed: `no`

Outputs:

- `authorized_reviews/authorized_review_crawl_plan_v1.csv`
- `authorized_reviews/authorized_review_crawl_plan_v1.json`

## Eligible ASINs

Only these identity-whitelist rows are eligible for the first authorized review
run:

| SKU | ASIN | Marketplace | Planned output |
|---|---|---|---|
| `crocodile-plush-rocker` | `B071774PWC` | US | `amazon_reviews_US_B071774PWC.csv/jsonl` |
| `pink-unicorn-plush-rocker` | `B072LXVM36` | US | `amazon_reviews_US_B072LXVM36.csv/jsonl` |
| `llama-plush-rocker` | `B07MFXJ28Y` | US | `amazon_reviews_US_B07MFXJ28Y.csv/jsonl` |
| `white-swan-plush-rocker` | `B0BVR63LRR` | US | `amazon_reviews_US_B0BVR63LRR.csv/jsonl` |
| `fox-plush-rocker` | `B0DSVJB5QH` | US | `amazon_reviews_US_B0DSVJB5QH.csv/jsonl` |
| `cream-wooden-play-kitchen-set-with-storage` | `B0FH1KX7XQ` | US | `amazon_reviews_US_B0FH1KX7XQ.csv/jsonl` |
| `blue-squirrel-plush-rocker` | `B0FSQ48N93` | US | `amazon_reviews_US_B0FSQ48N93.csv/jsonl` |

## Real Run Command

After `APIFY_TOKEN` or `APIFY_API_TOKEN` is available:

```bash
APIFY_TOKEN=... \
python3 planning/20260427_labebe_14day_execution/work_products/product_market_master/amazon_authorized_review_voc_runner.py \
  --execute \
  --out-dir planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/authorized_reviews \
  --marketplace US \
  --max-reviews 100 \
  --sorts recent helpful
```

Optional one-ASIN pilot:

```bash
APIFY_TOKEN=... \
python3 planning/20260427_labebe_14day_execution/work_products/product_market_master/amazon_authorized_review_voc_runner.py \
  --execute \
  --asin B072LXVM36 \
  --out-dir planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/authorized_reviews \
  --marketplace US \
  --max-reviews 100 \
  --sorts recent helpful
```

## VOC Summary Smoke

The VOC summarizer was smoke-tested against the existing
`data/amazon_reviews_US_B087P9SXZQ.csv` sample. That sample is not accepted as a
current DTC SKU evidence source because the contact-sheet review found a product
image conflict with the current DTC `doll-stroller-baby-push-walker`.

The smoke is format validation only.

Outputs:

- `voc_smoke_B087P9SXZQ/b087p9sxzq_format_smoke_voc_report_v1.md`
- `voc_smoke_B087P9SXZQ/b087p9sxzq_format_smoke_voc_theme_summary_v1.csv`
- `voc_smoke_B087P9SXZQ/b087p9sxzq_format_smoke_voc_quote_queue_v1.csv`
- `voc_smoke_B087P9SXZQ/b087p9sxzq_format_smoke_voc_manifest_v1.json`

Smoke result:

- input review rows: 13
- SKU/ASIN groups: 1
- theme rows: 9
- quote queue rows: 27
- public copy allowed: `false`
- claim gate required: `true`

## Boundary

- Do not run this for search candidates.
- Do not run this for variant-cluster candidates as exact DTC proof.
- Do not run this for blocked negative examples.
- Do not use review text or snippets as public copy without claim review and
  source approval.
- Do not use the old `B087P9SXZQ` sample as current Labebe DTC evidence.
