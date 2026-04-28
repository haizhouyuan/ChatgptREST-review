# Labebe DTC Website Prototype

This is the current pure consumer-facing Labebe DTC prototype. It must stay
separate from Paperclip, Boss Gallery, AI Growth Studio, claim-gate internals,
and external-review process pages.

## Current External URL

```text
https://yogas2.tail594315.ts.net:10000/
```

The old DDNS path `http://fnos.dandanbaba.xyz:8790/` may return `502`; use the
Tailscale Funnel URL for external review.

## Commands

```bash
npm install
npm run build
npm run lint
```

Serve the built app from the repo root:

```bash
python3 planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/spa_static_server.py \
  --directory /vol1/1000/projects/toyresearch/labebe-gemini-demo/dist \
  --host 0.0.0.0 \
  --port 8790
```

Expose through Tailscale Funnel:

```bash
bash /vol1/1000/home-yuanhaizhou/.codex-shared/skills/tailscale-external-deploy/scripts/publish_funnel.sh 8790 10000
```

## Structure

| Path | Purpose |
|---|---|
| `src/routes/Home.tsx` | Homepage and design direction switcher |
| `src/routes/CollectionPage.tsx` | Collection route |
| `src/routes/ProductPage.tsx` | PDP route |
| `src/components/CartDrawer.tsx` | Local cart and checkout handoff |
| `src/data/products.ts` | Prototype product data |
| `src/data/collections.ts` | Product-world collection data |
| `public/assets/products/` | Local product images |

## Boundaries

- This is a prototype, not a production checkout backend.
- Do not add fake ratings, fake reviews, fake certifications, fake awards, or
  unsupported safety/material claims.
- Keep Amazon/marketplace signals out of public copy unless they pass identity,
  source and claim review.
- Production reuse of product images still requires brand/legal approval.
