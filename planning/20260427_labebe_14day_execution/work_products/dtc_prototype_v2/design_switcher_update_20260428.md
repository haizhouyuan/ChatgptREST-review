# DTC Design Switcher Update

Date: 2026-04-28

## Purpose

The consumer website must remain a pure Labebe independent-site replacement, not an AI/Paperclip demo surface. This update adds a visible prototype switcher on the homepage so decision makers can compare three product-backed creative directions without mixing in internal automation content.

## Product Basis

The three directions come from the 60-SKU product strategy matrix and the Amazon identity-lane work:

| Direction | Product-world anchor | Why it exists |
|---|---|---|
| Gift Theater | Giftable Rockers | Rockers have the clearest character imagery and the strongest current identity-whitelist Amazon sample set. |
| Room Builder | Playroom Reset / Montessori Home | The catalog has enough shelves, storage, desks, and first-step products to sell practical room solutions instead of isolated SKUs. |
| Play Worlds | Pretend Play Worlds | Kitchens, cafe, laundry, and outdoor mud kitchen products can be merchandised as scene-based worlds. |

## Implementation

Changed files:

- `labebe-gemini-demo/src/routes/Home.tsx`
- `labebe-gemini-demo/src/index.css`
- `labebe-gemini-demo/src/data/products.ts`
- `labebe-gemini-demo/src/data/collections.ts`

Added local prototype images:

- `labebe-gemini-demo/public/assets/products/crocodile-plush-rocker.jpg`
- `labebe-gemini-demo/public/assets/products/white-swan-plush-rocker.jpg`
- `labebe-gemini-demo/public/assets/products/fox-plush-rocker.jpg`
- `labebe-gemini-demo/public/assets/products/blue-squirrel-plush-rocker.jpg`

The homepage now exposes a three-button switcher:

- `Gift Theater`
- `Room Builder`
- `Play Worlds`

Each mode changes the hero copy, palette, CTA path, central product card, and supporting product tiles. All linked products are real Labebe DTC products in the current prototype data layer.

## QA Evidence

Latest captures:

| View | Screenshot | Result |
|---|---|---|
| Gift Theater desktop | `qa/labebe-commerce-v2/home-design-gift-desktop-v5.png` | No horizontal overflow; headline no longer collides with product theater. |
| Gift Theater mobile | `qa/labebe-commerce-v2/home-design-gift-mobile-v5.png` | No horizontal overflow; product theater stacks below CTA. |
| Room Builder desktop | `qa/labebe-commerce-v2/home-design-room-desktop-v3.png` | No horizontal overflow; room-solution direction visible in first viewport. |
| Play Worlds desktop | `qa/labebe-commerce-v2/home-design-play-desktop-v3.png` | No horizontal overflow; pretend-play world direction visible in first viewport. |
| Play Worlds mobile | `qa/labebe-commerce-v2/home-design-play-mobile-v3.png` | No horizontal overflow; mobile nav and switcher remain usable. |

Build:

```text
npm run build
passed
```

HTTP:

```text
https://yogas2.tail594315.ts.net:10000/
200 OK
```

## Known Limits

- This is still a prototype switcher, not a final production personalization engine.
- Catalog packshots are doing most of the visual work; final production quality needs stronger lifestyle and motion assets.
- The switcher is useful for comparing creative directions with leadership, but the final public site should likely choose one dominant direction or make the modes implicit through navigation.
