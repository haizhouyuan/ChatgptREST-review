# Marketplace Sample Execution Report

Date: 2026-04-28

## Result

The sample method is now concrete enough to scale carefully:

- DTC live catalog probe passed.
- Amazon product-detail Browser Harness probe passed for 5 ASINs.
- Pink Unicorn Plush Rocker -> `B072LXVM36` is accepted as a browser + visual sample.
- Cream Wooden Play Kitchen -> `B0FH1KX7XQ` is accepted as a browser + visual sample.
- Llama Plush Rocker -> `B07MFXJ28Y` is accepted as a browser + visual sample.
- Fox Plush Rocker -> `B0DSVJB5QH` is accepted for Fox only; it was discovered during a Highlander search and must not be mapped to Highlander.
- `B087P9SXZQ` remains blocked for DTC mapping because title family and product image conflict with the current live DTC candidate.
- Direct browser review crawl is blocked by Amazon sign-in redirect; review crawling needs Apify/product-data API or a controlled logged-in browser profile.

## Generated Tables

| Table | Purpose |
|---|---|
| `live_crawl_20260428/product_master_live_probe_v1.csv` | Current DTC live catalog probe, 60 slugs |
| `live_crawl_20260428/amazon_identity_sample_v2.csv` | ASIN identity status by SKU |
| `live_crawl_20260428/amazon_browser_identity_facts_v1.csv` | Browser-captured Amazon product facts |
| `live_crawl_20260428/amazon_listing_facts_v1.csv` | Marketplace facts in consumable table form |
| `live_crawl_20260428/amazon_claim_gate_v1.csv` | Seller/listing claims classified by reuse risk |
| `live_crawl_20260428/amazon_review_crawl_gate_v1.csv` | Review crawl gate status |
| `live_crawl_20260428/image_identity_sample/amazon_dtc_image_identity_sample.csv` | DTC-vs-Amazon image triage |
| `live_crawl_20260428/amazon_search_candidates_sample_v2.csv` | Search-candidate discovery sample; candidate only, not facts |

## Scaling Rule

Do not run broad review crawl yet. Search pages are useful only for candidate discovery, because they can return regional prices and false-positive results. The next parallelizable unit is:

1. Use `amazon_browser_product_probe.mjs` for product-detail evidence.
2. Use image contact sheet and similarity triage.
3. Promote only accepted/probable ASINs.
4. Use `build_marketplace_fact_tables.py` to generate claim gates.
5. Only then run review crawling through an authorized review pipeline.

## Design Implication

The website can safely use DTC facts and official Labebe images now. Amazon facts are useful for internal product prioritization and boss-facing research evidence, but not for public DTC copy unless claim-gated.

For Pink Unicorn, Cream Play Kitchen, Llama Rocker, and Fox Rocker, the Amazon samples prove meaningful marketplace listing signals. This supports using them as high-priority products in internal strategy and prototype narratives.

The Highlander search mismatch is a process warning: even when a search result appears under a relevant query, PDP verification can reveal that it belongs to a different SKU. The identity gate must remain mandatory.
