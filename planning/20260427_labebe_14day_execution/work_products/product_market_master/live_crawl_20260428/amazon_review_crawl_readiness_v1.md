# Amazon Review Crawl Readiness v1

Date: 2026-04-28

## Result

Review/VOC crawl is not ready to execute in the current shell environment because `APIFY_TOKEN` / `APIFY_API_TOKEN` is not set.

This is not a product-method failure. The identity lane is ready: `amazon_review_voc_seed_v1.csv` contains the seven ASIN rows that are eligible for an authorized review/VOC pilot.

The execution path has now been converted into a self-contained dry-run/real-run
entry:

- `../amazon_authorized_review_voc_runner.py`
- `../build_review_voc_summary.py`
- `authorized_reviews/authorized_review_crawl_plan_v1.csv`
- `authorized_reviews/authorized_review_crawl_plan_v1.json`
- `authorized_review_voc_execution_update_v1.md`

## Eligible Seed

Use only these identity-whitelist candidates for the first authorized review run:

- `crocodile-plush-rocker` -> `B071774PWC`
- `pink-unicorn-plush-rocker` -> `B072LXVM36`
- `llama-plush-rocker` -> `B07MFXJ28Y`
- `white-swan-plush-rocker` -> `B0BVR63LRR`
- `fox-plush-rocker` -> `B0DSVJB5QH`
- `cream-wooden-play-kitchen-set-with-storage` -> `B0FH1KX7XQ`
- `blue-squirrel-plush-rocker` -> `B0FSQ48N93`

## Why Direct Browser Review Crawl Is Not The Default

The browser review-page probe against `B072LXVM36` redirected to Amazon sign-in. For this project, that means direct browser review crawling is not accepted as the default path unless a controlled logged-in browser profile and policy gate are explicitly configured.

## Authorized Command Pattern

When `APIFY_TOKEN` is available, run the project-local runner:

```bash
APIFY_TOKEN=... \
python3 planning/20260427_labebe_14day_execution/work_products/product_market_master/amazon_authorized_review_voc_runner.py \
  --execute \
  --out-dir planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/authorized_reviews \
  --marketplace US \
  --max-reviews 100 \
  --sorts recent helpful
```

For a one-ASIN pilot:

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

After review CSVs are produced, summarize VOC with:

```bash
python3 planning/20260427_labebe_14day_execution/work_products/product_market_master/build_review_voc_summary.py \
  planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/authorized_reviews/amazon_reviews_US_*.csv \
  --out-dir planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/authorized_reviews/voc_summary \
  --label authorized_labebe_reviews
```

## Dry-Run Evidence

The runner has been smoke-tested in dry-run mode:

- eligible rows: 7
- external calls made: `false`
- gate status: `dry_run_no_external_calls`
- planned calls per ASIN: 10

The VOC summary builder has been smoke-tested against the existing
`B087P9SXZQ` sample for format validation only. That old sample is not accepted
as current DTC evidence.

## Gate Rules

- Do not run review extraction for search candidates.
- Do not run review extraction for variant-cluster rows as exact DTC SKU proof.
- Do not run review extraction for blocked negative examples.
- Do not use review text as public copy without claim review and source labeling.
- Keep marketplace facts timestamped; prices, ratings, and review counts are volatile.
