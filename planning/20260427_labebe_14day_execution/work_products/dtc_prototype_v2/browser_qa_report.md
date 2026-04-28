# Browser QA Report — DTC Prototype v2.1

Generated: 2026-04-27

## Build

Command:

```bash
cd labebe-gemini-demo && npm run build
```

Result: passed.

Latest validation after cart implementation:

```bash
cd labebe-gemini-demo && npm run build
```

Result: passed. Latest bundle:

- `dist/assets/index-D1KSbpve.css`
- `dist/assets/index-DOsfj6T_.js`

## Preview Server

Stable command now used for external review:

```bash
setsid python3 /vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/spa_static_server.py \
  --directory /vol1/1000/projects/toyresearch/labebe-gemini-demo/dist \
  --host 0.0.0.0 \
  --port 8790 \
  > /vol1/1000/projects/toyresearch/logs/labebe-commerce-v2-spa-8790.log 2>&1 < /dev/null &
```

This serves React routes through an SPA fallback, so direct product/collection
URLs return `index.html` instead of 404.

## HTTP Smoke

| URL | Status |
| --- | --- |
| `/` | 200 |
| `/product/pink-unicorn-plush-rocker` | 200 |
| `/collections/playroom-reset` | 200 |

## CDP Screenshots And Layout Metrics

| Surface | Viewport | Screenshot | Horizontal Overflow |
| --- | --- | --- | --- |
| Home | 1440 x 1100 | `qa/labebe-commerce-v2/home-desktop-cdp-v2.png` | false |
| Home | 390 x 1200 mobile metrics | `qa/labebe-commerce-v2/home-mobile-cdp-v2.png` | false |
| PDP | 1440 x 1100 | `qa/labebe-commerce-v2/pdp-desktop-cdp.png` | false |
| PDP | 390 x 1200 mobile metrics | `qa/labebe-commerce-v2/pdp-mobile-cdp-v2.png` | false |
| Collection | 1440 x 1100 | `qa/labebe-commerce-v2/collection-desktop-cdp.png` | false |
| Home v2.1 | 1440 x 1024 | `qa/labebe-commerce-v2/home-desktop-cdp-v3.png` | false |
| Home v2.1 | 390 x 844 mobile metrics | `qa/labebe-commerce-v2/home-mobile-cdp-v3.png` | false |
| PDP v2.1 | 1440 x 1024 | `qa/labebe-commerce-v2/pdp-desktop-cdp-v2.png` | false |
| Collection v2.1 | 390 x 844 mobile metrics | `qa/labebe-commerce-v2/collection-mobile-cdp-v1.png` | false |
| Cart drawer click flow | 390 x 844 mobile metrics | `qa/labebe-commerce-v2/cart-drawer-mobile-cdp-v2.png` | false |

## Visual QA Notes

- Desktop home: hero no longer uses a narrow centered column; product theater
  and large typography create a stronger first impression.
- Desktop home: fixed the data rail overlap that was covering hero copy and
  product-card pricing.
- Mobile home: fixed the earlier screenshot artifact by using CDP device
  metrics; actual mobile layout has no horizontal overflow.
- Mobile PDP: changed order so product image appears before purchase details.
- Screenshots have nonblank pixel distribution; no black/white-screen failure.
- Cart drawer: add-to-cart opens the drawer, item count increments, quantity
  controls are visible, suggested pairing is shown, subtotal is calculated.
- Cart drawer: first QA pass found stretched mobile rows and hidden close
  button; fixed with explicit `align-content: start` and mobile close display.

## Known Gaps

- Checkout remains a non-integrated CTA; no payment/shipping backend is connected.
- Visual model scoring is not yet connected; current evidence is CDP metrics plus
  human screenshot review.
- PDP dimensions, materials, warnings, assembly, and care still require source capture
  before production copy can be expanded.
