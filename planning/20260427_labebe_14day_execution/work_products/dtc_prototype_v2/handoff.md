# Handoff — DTC Prototype v2

Generated: 2026-04-27

## What Is Ready

- A rebuilt Labebe pure-commerce prototype in `labebe-gemini-demo/`.
- Desktop and mobile screenshots for Home and PDP.
- Desktop screenshot for Collection.
- A repeatable CDP screenshot tool at
  `work_products/runtime_qa_templates/capture_cdp_screenshot.mjs`.

## How To Run

```bash
cd /vol1/1000/projects/toyresearch/labebe-gemini-demo
npm run build
setsid python3 /vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/spa_static_server.py \
  --directory /vol1/1000/projects/toyresearch/labebe-gemini-demo/dist \
  --host 0.0.0.0 \
  --port 8790 \
  > /vol1/1000/projects/toyresearch/logs/labebe-commerce-v2-spa-8790.log 2>&1 < /dev/null &
```

Then open:

`http://100.124.54.52:8790/`

## Next Hardening Step

2026-04-28 update: items 1, 3, and 4 below were completed for demo/prototype
scope after this handoff was first written. Use
`CONTINUATION_UPDATE_20260428.md` and `11_NEXT_EXECUTION_QUEUE.md` as the current
source of truth.

1. Cart drawer flow: done for prototype scope; production checkout/backend is not
   implemented.
2. Room-builder interaction beyond the homepage module: still a production
   hardening candidate.
3. PDP source text for dimensions/materials/care: 8-SKU source capture done;
   claim-review queue remains manual-review-only.
4. DTC walkthrough video: desktop and mobile videos rendered and served.
5. Shared Browser Harness: local QA evidence exists; reusable shared service is
   still future work.
