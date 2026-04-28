# Production Asset Clearance Queue v1

Generated: 2026-04-28

## Purpose

This queue turns the current consumer-site asset audit into a production approval handoff. It does not approve any image for public launch. Every active DTC product image remains `pending_brand_legal_review` until the brand owner, legal/rights reviewer and ecommerce owner mark the asset approved, internal-only or replace-before-launch.

## Summary

| Metric | Count |
|---|---:|
| Active consumer-site product image assets | 26 |
| Internal prototype OK | 26 |
| Production approved | 0 |
| Pending brand/legal review | 26 |
| Consumer-site videos requiring clearance | 0 |

## Source Class Counts

- official_catalog_exact_copy: 17
- official_catalog_live_probe_exact_copy: 9

## Product World Counts

- Milestone Activity: 2
- First Steps & Activity: 5
- Giftable Rockers: 7
- Study & Art Corner: 1
- Tiny Pretend Worlds: 4
- Montessori at Home: 2
- Playroom Reset: 3
- Outdoor Pretend Play: 2

## Required Review Decision

For each row, choose exactly one:

- `approve_for_dtc`: Labebe confirms it owns or can use the image in production independent-store deployment.
- `internal_only`: asset can remain in internal demo/prototype packs but must not ship publicly.
- `replace_before_launch`: asset needs new photography, licensed media, or AI/synthetic replacement with explicit labeling and approval.

## Reviewer Checklist

- Confirm image ownership or license scope.
- Confirm product shown matches the current SKU and variant.
- Confirm no child/person usage rights issue exists.
- Confirm no marketplace-only or third-party listing image is used as DTC truth.
- Confirm image can be exported in the final deployment environment.
- Record reviewer, decision date and replacement path if needed.

## Sample Rows

| Asset | Product | World | Source class | Status |
|---|---|---|---|---|
| SITE-ASSET-001 | activity-cube-baby-push-walker | Milestone Activity | official_catalog_exact_copy | pending_brand_legal_review |
| SITE-ASSET-002 | activity-montessori-baby-push-walker | First Steps & Activity | official_catalog_live_probe_exact_copy | pending_brand_legal_review |
| SITE-ASSET-003 | blue-squirrel-plush-rocker | Giftable Rockers | official_catalog_live_probe_exact_copy | pending_brand_legal_review |
| SITE-ASSET-004 | children-s-writing-desk-and-chair-set-with-hutch---cork-board-for-study---art | Study & Art Corner | official_catalog_exact_copy | pending_brand_legal_review |
| SITE-ASSET-005 | classic-montessori-baby-push-walker | First Steps & Activity | official_catalog_live_probe_exact_copy | pending_brand_legal_review |
| SITE-ASSET-006 | cream-wooden-play-kitchen-set-with-storage | Tiny Pretend Worlds | official_catalog_exact_copy | pending_brand_legal_review |
| SITE-ASSET-007 | crocodile-plush-rocker | Giftable Rockers | official_catalog_live_probe_exact_copy | pending_brand_legal_review |
| SITE-ASSET-008 | farm-themed-baby-push-walker | First Steps & Activity | official_catalog_live_probe_exact_copy | pending_brand_legal_review |
| SITE-ASSET-009 | foldable-learning-tower-montessori-kitchen-tower-log-color | Montessori at Home | official_catalog_exact_copy | pending_brand_legal_review |
| SITE-ASSET-010 | fox-plush-rocker | Giftable Rockers | official_catalog_live_probe_exact_copy | pending_brand_legal_review |
| SITE-ASSET-011 | highlander-cattle-plush-rocker | Giftable Rockers | official_catalog_exact_copy | pending_brand_legal_review |
| SITE-ASSET-012 | ice-cream-cart-baby-push-walker | First Steps & Activity | official_catalog_live_probe_exact_copy | pending_brand_legal_review |

Full queue: `production_asset_clearance_queue_v1.csv`
