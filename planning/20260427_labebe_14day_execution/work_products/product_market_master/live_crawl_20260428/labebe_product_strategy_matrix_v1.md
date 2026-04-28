# Labebe Product Strategy Matrix v1

Date: 2026-04-28

## Scope

This matrix combines the live Labebe DTC catalog probe, Amazon identity lanes, visual review, PDP facts, and claim gate into a site-design decision layer.

It is an internal planning artifact. It does not authorize public marketplace claims, safety claims, certification claims, or customer review reuse.

## Product World Counts

- First Steps & Activity: 17
- Giftable Rockers: 13
- Montessori Home & Study: 13
- Pretend Play Worlds: 10
- Playroom Reset: 7

## Website Role Counts

- supporting_catalog_item: 18
- family_collection_not_exact_marketplace_claim: 11
- dtc_visible_marketplace_blocked: 7
- supporting_collection_and_bundle: 7
- navigation_and_room_solution_anchor: 5
- do_not_hero: 5
- best_seller_grid_and_gift_collection: 3
- homepage_hero_or_best_seller: 3
- category_anchor_pdp: 1

## Amazon Identity Lane Counts

- no_marketplace_identity_yet: 32
- retry_or_provider_required: 10
- identity_whitelist_candidate: 7
- blocked_negative_example: 7
- variant_cluster_research: 4

## Marketplace Signal Counts

- no_marketplace_identity_yet: 32
- marketplace_retry_required: 10
- blocked_wrong_match: 7
- variant_cluster_not_exact: 4
- moderate_amazon_social_proof: 3
- strong_amazon_social_proof: 3
- light_amazon_social_proof: 1

## Current Design Decisions

- Giftable Rockers are the strongest proof-rich hero category because they combine visual character, DTC reviews, and multiple Amazon identity-whitelist candidates.
- Pretend Play should be anchored by Cream Wooden Play Kitchen, with the black and gray kitchen variants treated carefully as separate DTC variants, not as the same Amazon ASIN.
- First Steps & Activity is a real DTC family, but Amazon evidence is variant-clustered. It can become a shopping world, but not a marketplace-proof story yet.
- Montessori Home & Study and Playroom Reset are important for site architecture and parent utility, but need PDP/spec recrawl before strong claims.
- Regional variants and site-all-only rows should not become homepage heroes until category, locale, and fulfillment are confirmed.

## Hero / Anchor Candidates

| SKU | World | Role | DTC reviews | Amazon ASIN | Amazon reviews | Seller | Next action |
|---|---|---|---:|---|---:|---|---|
| `blue-squirrel-plush-rocker` | Giftable Rockers | best_seller_grid_and_gift_collection |  | `B0FSQ48N93` | 77 | Labebe Store | run_claim_gate_then_review_voc_seed_if_whitelisted |
| `fox-plush-rocker` | Giftable Rockers | best_seller_grid_and_gift_collection | 4 | `B0DSVJB5QH` | 69 | Labebe Store | run_claim_gate_then_review_voc_seed_if_whitelisted |
| `llama-plush-rocker` | Giftable Rockers | best_seller_grid_and_gift_collection | 7 | `B07MFXJ28Y` | 358 | Labebe Store | run_claim_gate_then_review_voc_seed_if_whitelisted |
| `cream-wooden-play-kitchen-set-with-storage` | Pretend Play Worlds | category_anchor_pdp | 9 | `B0FH1KX7XQ` | 25 | Pretty valley | verify variant, specs, dimensions, and claims before production PDP copy |
| `crocodile-plush-rocker` | Giftable Rockers | homepage_hero_or_best_seller | 4 | `B071774PWC` | 662 | Labebe Store | prepare_pdp_story_and_review_voc_after_authorized_crawl |
| `white-swan-plush-rocker` | Giftable Rockers | homepage_hero_or_best_seller | 6 | `B0BVR63LRR` | 560 | Labebe Store | prepare_pdp_story_and_review_voc_after_authorized_crawl |
| `pink-unicorn-plush-rocker` | Giftable Rockers | homepage_hero_or_best_seller | 18 | `B072LXVM36` | 2657 | Labebe Store | prepare_pdp_story_and_review_voc_after_authorized_crawl |

## Files

- `labebe_product_strategy_matrix_v1.csv`
- `labebe_product_strategy_matrix_v1.md`