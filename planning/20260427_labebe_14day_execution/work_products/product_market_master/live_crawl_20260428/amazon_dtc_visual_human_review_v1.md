# Amazon DTC Visual Human Review v1

Date: 2026-04-28

## Scope

This review is a human inspection pass over `amazon_dtc_visual_gate_contact_sheet_v1.jpg` and its four split sheets. It promotes, blocks, or queues the 28 ASIN-to-SKU candidate rows after machine visual triage.

It is still an internal evidence artifact. It does not authorize public DTC copy, Amazon sales claims, certification claims, or review/VOC reuse without the claim gate and review-access gate.

## Summary

| Human status | Count | Meaning |
|---|---:|---|
| `human_confirmed_same_product` | 7 | Product image/title are consistent enough to promote into the identity whitelist. |
| `human_variant_cluster_probable` | 1 | Likely close variant, but provider verification is needed before exact SKU use. |
| `human_variant_cluster_not_exact` | 3 | Related product family, not an exact DTC SKU match. |
| `human_rejected_wrong_product` | 1 | Search mapped to the wrong product family. |
| `human_rejected_wrong_variant` | 6 | ASIN belongs to a different variant than the DTC SKU. |
| `human_retry_required` | 10 | PDP image/social-proof capture is too weak; retry or provider source required. |

## Identity Whitelist Candidates

These rows can move to the next identity-promotion stage, still with claim gating attached:

| SKU | ASIN | Note |
|---|---|---|
| `crocodile-plush-rocker` | `B071774PWC` | Same crocodile plush rocker. |
| `pink-unicorn-plush-rocker` | `B072LXVM36` | Same Pink Unicorn rocker; Amazon uses a child-in-scene image. |
| `llama-plush-rocker` | `B07MFXJ28Y` | Same Llama plush rocker. |
| `white-swan-plush-rocker` | `B0BVR63LRR` | Same White Swan family; Amazon includes companion plush. |
| `fox-plush-rocker` | `B0DSVJB5QH` | Same Fox rocker. |
| `cream-wooden-play-kitchen-set-with-storage` | `B0FH1KX7XQ` | Same cream wooden play kitchen. |
| `blue-squirrel-plush-rocker` | `B0FSQ48N93` | Same Blue Squirrel rocker. |

## Variant Queue

These are useful for product-family learning but should not be used as exact SKU proof:

| SKU | ASIN | Lane | Note |
|---|---|---|---|
| `doll-stroller-baby-push-walker` | `B0F8PZ7KZQ` | `variant_cluster_review` | Close doll-stroller/activity variant; accessories differ. |
| `activity-montessori-baby-push-walker` | `B0D6YX3XG1` | `variant_cluster_review` | Same broad activity-walker family, different model. |
| `classic-montessori-baby-push-walker` | `B0D6YX3XG1` | `variant_cluster_review` | Related activity walker, not exact model. |
| `activity-cube-baby-push-walker` | `B0F8PZ7KZQ` | `variant_cluster_review` | Related push-walker family, not exact model. |

## Blocked Negative Training Examples

These should be kept to improve future matching rules:

| SKU | ASIN | Reason |
|---|---|---|
| `highlander-cattle-plush-rocker` | `B071774PWC` | Search returned Crocodile. |
| `yak-plush-rocker` | `B07Z3DXVQT` | ASIN text points to Mammoth, not Yak. |
| `panda-baby-push-walker` | `B0D6YX3XG1` | Amazon image is not Panda. |
| `farm-themed-baby-push-walker` | `B0F8PZ7KZQ` | Amazon image is not Farm-Themed. |
| `ice-cream-cart-baby-push-walker` | `B0F8PZ7KZQ` | Amazon image is not Ice Cream Cart. |
| `midnight-serenity-wooden-play-kitchen-set` | `B0FH1KX7XQ` | Amazon image is Cream Kitchen, not Midnight Serenity. |
| `stylish-wooden-kids-kitchen-playset` | `B0FH1KX7XQ` | Amazon image is Cream Kitchen, not Stylish Kitchen. |

## Retry Queue

These need a fresh Browser Harness PDP capture, provider extraction, or a controlled storefront profile before promotion:

- `mammoth-plush-rocker` -> `B07Z3DXVQT`
- `sheep-plush-rocker` -> `B0DJ6XM7GK`
- `wooden-rocking-horse` -> `B0DSZXRZZ1`
- `princess-vanity-set-with-stool-and-lights` -> `B0FLD8TWWN`
- all current Learning Tower rows -> `B0FMRDDRZK`

## Operational Rule

For the next Amazon/VOC crawl batch:

1. Run review extraction only for identity-whitelist candidates.
2. Keep variant-cluster rows for product-family insight, not exact SKU claims.
3. Do not use blocked negative rows for review/VOC or public copy.
4. Retry weak PDP rows before any marketplace conclusion.
5. Carry the claim gate forward even for confirmed products; a same-product match does not validate safety, certification, award, age, material, or development-benefit claims.
