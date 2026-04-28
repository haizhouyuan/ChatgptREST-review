# Repo Governance

Created: 2026-04-28

## Intent

This repository is a working research/demo workspace, not a clean product repo.
The goal of governance is to make it resumable without destroying provenance.

## Current Organization Policy

| Class | Where It Belongs | Notes |
|---|---|---|
| Current website source | `labebe-gemini-demo/` | React/Vite app. Keep internal AI/Paperclip routes out. |
| Current masterplan and work products | `planning/20260427_labebe_14day_execution/` | Main source of truth for this sprint. |
| Current static executive demo output | `paperclip_runtime_duel/outputs/boss_gallery_v0/` | Generated output, served from port `8778`. |
| Current walkthrough videos | `paperclip_runtime_duel/outputs/labebe_site_walkthrough/` | Generated media, not git source. |
| Raw uploads and old zip packages | `archive/YYYYMMDD/` | Keep provenance, but do not treat as current truth. |
| Cleaned documents | `clean/` | Use for reference and external packets. |
| External advisor packets | `pro_requests/` | Store prompt, context, answer and evidence. |
| Browser/visual QA outputs | `qa/` | Generated evidence. Keep indexed by docs, not usually git-tracked. |
| Product data | `data/` | Source-tagged data only. Do not mix guessed facts. |
| Repo-level docs | `docs/` | Governance, artifact index, deployment and status. |

## Root Directory Policy

The root should contain only:

- `README.md`
- `.gitignore`
- small root scripts that are still used directly;
- stable top-level project directories;
- a small number of legacy files retained for path compatibility.

Existing top-level legacy files are not moved in this pass because prior docs and
messages reference their absolute paths. New raw files should not be added to the
root.

## Current Legacy Top-Level Files

| File | Reason Retained |
|---|---|
| `pro反馈网站设计.md` | User-referenced Pro feedback document. |
| `sdd.md` | User/worker-referenced Paperclip/Labebe context. |
| `my - 红队审核与建议.md` | User/worker-referenced critique document. |
| `未命名 140.md` | External review answer referenced during execution. |
| `teamdemopro答案20260425.md` | Historical Pro/team demo answer. |
| `skill-mcp-migration-plan.md` | Runtime governance reference. |
| `scrape_labebe.py` | Original Labebe scraper entrypoint. |
| `fetch_amazon_reviews_apify.py` | Original Amazon review fetcher entrypoint. |

Future cleanup can move these into `archive/` or `docs/legacy/` only after
adding compatibility links and updating known references.

## Git Hygiene

Do not add by default:

- `node_modules/`
- Vite `dist/`
- generated videos/audio;
- zip/tar/7z packages;
- bulk QA screenshots;
- downloaded product image corpora;
- raw Kimi/Pro export packages.

Do add:

- source code;
- small governance docs;
- deterministic scripts;
- small CSV/JSON source tables when needed for reproducibility;
- manifests and indexes.

## Safety Boundaries

- Do not delete raw inputs unless they are exact duplicates and an archive
  manifest names the canonical copy.
- Do not rewrite product facts without source/observation date.
- Do not move served directories without updating deployment docs and testing URLs.
- Do not expose internal tools publicly through Funnel without auth review.

