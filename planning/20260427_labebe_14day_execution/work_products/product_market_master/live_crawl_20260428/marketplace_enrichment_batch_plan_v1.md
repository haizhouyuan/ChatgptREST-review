# Marketplace Enrichment Batch Plan v1

Generated: 2026-04-27T23:18:27.261817+00:00

## Purpose

This file turns the 60-row Labebe product strategy matrix into a worker-ready marketplace enrichment backlog. It does not create new Amazon claims. It tells future workers which rows can be processed in parallel and which gates must stay closed.

## Summary

- Total SKU rows: 60
- Backlog CSV: `marketplace_enrichment_backlog_v1.csv`
- Worker batches JSON: `marketplace_enrichment_worker_batches_v1.json`

### Batch Counts

- `B0_identity_whitelist_review_voc`: 7
- `B1_variant_cluster_map`: 4
- `B2_pdp_retry_provider`: 10
- `B3_no_identity_high_signal`: 1
- `B3_no_identity_restart_discovery`: 26
- `B4_negative_training_restart_search`: 7
- `B5_regional_scope_review`: 5

### Priority Counts

- `P0_gate_after_authorized_reviews`: 7
- `P1_high`: 10
- `P2_medium`: 33
- `P3_low`: 10

## Batch Definitions

| Batch | Use For | Allowed Next Step | Guardrail |
|---|---|---|---|
| `B0_identity_whitelist_review_voc` | confirmed same-product identity rows | authorized review/VOC runner, then claim review | no public copy until source/claim approval |
| `B1_variant_cluster_map` | related model/variant clusters | provider variation API, child ASIN/variation mapping, image review | no exact SKU claim |
| `B2_pdp_retry_provider` | weak PDP, blank image, missing proof | Browser Harness retry then provider fallback | no review crawl |
| `B3_no_identity_high_signal` | strong search candidate but no accepted identity | PDP probe then visual gate | search facts stay discovery-only |
| `B3_no_identity_restart_discovery` | no accepted identity | exact title/brand search, reverse image/provider fallback | no search-page facts |
| `B4_negative_training_restart_search` | known wrong ASIN mappings | preserve negative example and restart with exclusions | blocked ASIN cannot be reused as proof |
| `B5_regional_scope_review` | EU/regional products | locale/fulfillment review first | keep out of Amazon US proof layer |

## Top P1 Rows

| SKU | Batch | Current ASIN | Search ASIN | Method |
|---|---|---|---|---|
| `activity-montessori-baby-push-walker` | `B1_variant_cluster_map` | `B0D6YX3XG1` | `B0D6YX3XG1` | provider_variation_api_or_manual_variant_sheet |
| `classic-montessori-baby-push-walker` | `B1_variant_cluster_map` | `B0D6YX3XG1` | `B0D6YX3XG1` | provider_variation_api_or_manual_variant_sheet |
| `activity-cube-baby-push-walker` | `B1_variant_cluster_map` | `B0F8PZ7KZQ` | `B0F8PZ7KZQ` | provider_variation_api_or_manual_variant_sheet |
| `doll-stroller-baby-push-walker` | `B1_variant_cluster_map` | `B0F8PZ7KZQ` | `B0F8PZ7KZQ` | provider_variation_api_or_manual_variant_sheet |
| `kids-art-table-chair-set-with-easel-3-in-1` | `B3_no_identity_high_signal` | `` | `B0G3PQSH77` | pdp_probe_then_visual_gate |
| `children-s-writing-desk-and-chair-set-with-hutch---cork-board-for-study---art` | `B3_no_identity_restart_discovery` | `` | `B0FLPXNKNB` | exact_title_brand_search_then_provider_fallback |
| `kids-wooden-desk---chair-set-with-corkboard--hutch-storage---organizer` | `B3_no_identity_restart_discovery` | `` | `B0F3HTRVLL` | exact_title_brand_search_then_provider_fallback |
| `natural-wood-montessori-shelf-with-storage-boxes` | `B3_no_identity_restart_discovery` | `` | `B0FLXN9MG7` | exact_title_brand_search_then_provider_fallback |
| `rubber-wood-montessori-shelf` | `B3_no_identity_restart_discovery` | `` | `B0G6KY6WQY` | exact_title_brand_search_then_provider_fallback |
| `kids-desk-chair-set-with-cork-board-hutch` | `B3_no_identity_restart_discovery` | `` | `B0FLPXNKNB` | exact_title_brand_search_then_provider_fallback |

## Stop Rules

- Search pages are discovery only.
- Marketplace facts remain internal until identity, claim, and source gates pass.
- Review/VOC extraction is allowed only for `B0_identity_whitelist_review_voc` rows after provider credentials are available.
- Regional variants must not be mixed into Amazon US proof.
- Negative examples must stay attached to prevent repeated false-positive matching.
