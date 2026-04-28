# WP-C Public Media Asset Probe Worker Prompt

You are a delegated worker in `/vol1/1000/projects/toyresearch`.

You are not alone in the codebase. Do not revert or modify files outside your assigned write scope.

Assigned write scope:

```text
/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/media_asset_probe/
```

Task:

Discover and classify existing public/local Labebe media assets for DTC prototype and Boss Gallery planning. Focus on source, role, scene, and usage caveat. Do not treat public capture as legal clearance.

Read first:

- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/01_MASTER_IMPLEMENTATION_PLAN.md`
- `/vol1/1000/projects/toyresearch/kimi_web_upload_website_pack/`
- `/vol1/1000/projects/toyresearch/data/labebe/`
- `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs/labebe_wow/`

Required outputs:

- `initial_media_probe.md`
- `brand_video_assets_draft.csv`
- `downloaded_media_manifest_draft.csv`
- `video_scene_index_draft.csv`
- `asset_rights_and_usage_notes_draft.md`
- `handoff.md`
- `evidence_manifest.json`

Acceptance:

- identify local image/video/media folders;
- classify likely media role: hero, PDP gallery, detail, room context, short-video candidate, Boss Gallery supporting asset;
- record source path/URL if known;
- state usage caveats.

Forbidden:

- do not call Pro/Gemini;
- do not invent source URLs;
- do not claim usage rights;
- do not edit prototype code.

