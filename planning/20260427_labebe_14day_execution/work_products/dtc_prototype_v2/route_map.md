# Route Map

Generated: 2026-04-27

| Route | Status | Purpose |
| --- | --- | --- |
| `/` | Implemented | Room-first homepage with product theater and guided shopper paths. |
| `/shop/by-room` | Implemented | Room-led browsing for Nursery, Playroom, Kitchen, Outdoor. |
| `/shop/by-age` | Implemented | Age-led browsing for 6-18m, 1-3Y, 3-6Y. |
| `/collections/giftable-rockers` | Implemented | Giftable rocker world. |
| `/collections/montessori-at-home` | Implemented | Furniture and routine world. |
| `/collections/pretend-play-worlds` | Implemented | Kitchens, shop, laundry, mud-play world. |
| `/collections/playroom-reset` | Implemented | Storage and activity-corner world. |
| `/product/:slug` | Implemented for current `productList` | PDP template with price, review count when supported, tags, add-to-cart action, tabs, modules, and bundles. |

## Prototype Interactions

| Interaction | Status | Notes |
| --- | --- | --- |
| Header cart button | Implemented | Opens the cart drawer and shows cart count. |
| PDP Add to cart | Implemented | Adds current product and opens cart drawer. |
| Cart drawer quantity | Implemented | Increase/decrease/remove updates local state and subtotal. |
| Cart pairing add-on | Implemented | Adds Llama Plush Rocker as a sample gift pairing. |
| Checkout | Prototype CTA | No payment/shipping backend. |

## Smoke-Tested URLs

- `http://127.0.0.1:8790/`
- `http://127.0.0.1:8790/product/pink-unicorn-plush-rocker`
- `http://127.0.0.1:8790/collections/playroom-reset`
- Mobile cart drawer click flow through Browser Harness action script.

All returned HTTP 200 under the SPA static server.
