# Live Catalog Design Update

Date: 2026-04-28

## Why This Update Was Needed

The current Labebe live catalog probe found 60 visible product slugs, compared with the older 46-product local table. The most important design implication is that Baby Push Walkers are not a single add-on SKU. They are a visible first-steps product family.

The DTC prototype was updated so the site structure reflects this product reality instead of forcing the catalog into the earlier four-world model.

## Frontend Changes

- Added `First Steps & Activity` as a fifth shopping world.
- Added five live-probe push walker products to `src/data/products.ts`.
- Downloaded the new walker images into `public/assets/products/` so the demo does not depend on remote CDN rendering.
- Updated `/shop/by-age` so the `6-18m` stage shows a real first-steps product family rather than one isolated SKU.
- Replaced the stale `46 products` homepage proof point with shopper-facing value language.
- Updated the world grid to use responsive auto-fit columns so five worlds do not break desktop or mobile layout.

## New Product Entries

| SKU | Role |
|---|---|
| `activity-montessori-baby-push-walker` | First-steps hero extension |
| `classic-montessori-baby-push-walker` | Comparison option |
| `ice-cream-cart-baby-push-walker` | First-steps plus pretend-play crossover |
| `farm-themed-baby-push-walker` | Theme variety |
| `panda-baby-push-walker` | Character variety |

## QA

Build passed:

```bash
npm run build
```

Browser Harness screenshots captured:

- `qa/labebe-commerce-v2/home-desktop-live-products-v2.png`
- `qa/labebe-commerce-v2/first-steps-collection-desktop-v2.png`
- `qa/labebe-commerce-v2/shop-by-age-mobile-live-products-v2.png`
- `qa/labebe-commerce-v2/home-desktop-hero-fit-v3.png`
- `qa/labebe-commerce-v2/home-mobile-hero-fit-v3.png`
- `qa/labebe-commerce-v2/first-steps-collection-desktop-v3.png`

Latest captures reported `horizontalOverflow=false`. The v3 homepage captures also verify the hero product title and price no longer collide with the card boundary.

## Marketplace Boundary

The new walker products use DTC live-probe facts only. Amazon review and VOC data is not attached to these products unless an ASIN reaches accepted identity status.

Current sample result:

- `pink-unicorn-plush-rocker` to Amazon `B072LXVM36` is accepted as a browser-verified visual/listing sample for marketplace fact enrichment.
- `B087P9SXZQ` is not attached to the current DTC push-walker SKUs because the browser and image sample showed a visual mismatch risk.
- Amazon review-page crawling redirected to sign-in during the sample run; review/VOC extraction remains blocked until an authorized review pipeline is selected.
