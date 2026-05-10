# Toyresearch

Toyresearch is the Labebe research and demo workspace. It contains product data
research, DTC website prototypes, Paperclip/Boss Gallery demo assets, external
review packets, QA evidence, and final handoff packages.

## Open First

| Need | URL / Path |
|---|---|
| Current Labebe DTC website | `https://yogas2.tail594315.ts.net:10000/` |
| Internal Boss Gallery | `http://fnos.dandanbaba.xyz:8778/boss_gallery_v0/index.html` |
| Current execution review | `planning/20260427_labebe_14day_execution/MASTERPLAN_EXECUTION_REVIEW_20260428.md` |
| Final delivery index | `planning/20260427_labebe_14day_execution/FINAL_DELIVERY_INDEX.md` |
| Closeout report | `planning/20260427_labebe_14day_execution/CLOSEOUT_REPORT.md` |
| Latest package | `planning/20260428_labebe_product_marketplace_dtc_live_update.zip` |

The old raw DDNS URL `http://fnos.dandanbaba.xyz:8790/` may return `502`
through router/DDNS/proxy. Use the Tailscale Funnel URL above for external
review.

## Current Status

- Labebe DTC website: working prototype, not production checkout.
- Boss Gallery: internal static executive demo, separate from the consumer site.
- Product research: 60 visible DTC SKUs plus product strategy matrix.
- Marketplace research: identity-first method, 7 review/VOC seed rows, 60-SKU
  enrichment backlog; no full Amazon truth claim yet.
- Browser Harness: P0 QA scripts and localhost service wrapper exist.
- Media rights: 26 active DTC product images are queued for brand/legal review;
  no production approval is implied.

## Directory Map

| Path | Purpose | Governance |
|---|---|---|
| `labebe-gemini-demo/` | Current React/Vite DTC website prototype | Source code lives here; build output `dist/` is generated. |
| `planning/20260427_labebe_14day_execution/` | Current masterplan, evidence, work products, closeout | Main continuity source after context loss. |
| `paperclip_runtime_duel/outputs/boss_gallery_v0/` | Current internal Boss Gallery static output | Generated demo output; source decisions are in planning docs. |
| `paperclip_runtime_duel/outputs/labebe_site_walkthrough/` | DTC desktop/mobile walkthrough videos | Generated presentation media. |
| `data/` | Product data, review samples and scraped assets | Do not invent facts; record source and observation date. |
| `clean/` | Earlier cleaned conversation/doc packages | Reference library, not current implementation source. |
| `archive/` | Raw uploads, old exports, duplicated source packages | Keep for provenance; do not use as current truth without revalidation. |
| `pro_requests/` | External advisor packets and answers | Reference only; do not block local execution unless explicitly requested. |
| `qa/` | Screenshot, Browser Harness and visual QA outputs | Generated evidence, often bulky. |
| `research/` | Design/strategy research notes | Reference input for future design work. |
| `docs/` | Repo-level governance and index docs | Start here for repository operations. |
| `tools/` | Local helper binaries/scripts | Verify before relying on downloaded binaries. |

## Common Commands

Build the DTC app:

```bash
cd labebe-gemini-demo
npm run build
```

Serve the DTC app locally:

```bash
python3 planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/spa_static_server.py \
  --directory /vol1/1000/projects/toyresearch/labebe-gemini-demo/dist \
  --host 0.0.0.0 \
  --port 8790
```

Expose DTC through Tailscale Funnel:

```bash
bash <REDACTED_LOCAL_HOME>/.codex-shared/skills/tailscale-external-deploy/scripts/publish_funnel.sh 8790 10000
```

Check the route:

```bash
bash <REDACTED_LOCAL_HOME>/.codex-shared/skills/tailscale-external-deploy/scripts/check_route.sh 8790 https://yogas2.tail594315.ts.net:10000/
```

## Repo Rules

- Keep the consumer DTC website separate from Paperclip/Boss Gallery/internal AI
  demos.
- Do not copy Amazon search-page data into public copy.
- Do not use fake reviews, ratings, certifications, awards, safety claims,
  production CAD claims, or market-demand claims.
- Keep new raw uploads under `archive/YYYYMMDD/` or `clean/`, not in the repo
  root.
- Keep generated QA/video/build artifacts out of git unless a specific release
  requires them.
- Update `docs/ARTIFACT_INDEX.md` and this README when a new current entrypoint
  replaces an old one.

## More Docs

- `docs/REPO_GOVERNANCE.md`
- `docs/ARTIFACT_INDEX.md`
- `docs/DEPLOYMENT.md`
- `docs/STATUS.md`

