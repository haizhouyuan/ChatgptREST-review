# Boss Gallery Walkthrough Video Update

**Date:** 2026-04-28  
**Scope:** Internal Boss Gallery only. This is separate from the Labebe consumer DTC website.

## Output

Desktop walkthrough:

- `paperclip_runtime_duel/outputs/boss_gallery_v0/labebe_boss_gallery_walkthrough.mp4`
- H.264, 1920x1080, about 48.97 seconds.
- Public URL: `http://fnos.dandanbaba.xyz:8778/boss_gallery_v0/labebe_boss_gallery_walkthrough.mp4`

Mobile walkthrough:

- `paperclip_runtime_duel/outputs/boss_gallery_v0/labebe_boss_gallery_walkthrough_mobile.mp4`
- H.264, 1080x1920, about 44.97 seconds.
- Public URL: `http://fnos.dandanbaba.xyz:8778/boss_gallery_v0/labebe_boss_gallery_walkthrough_mobile.mp4`

Supporting artifacts:

- `paperclip_runtime_duel/outputs/boss_gallery_v0/labebe_boss_gallery_walkthrough_poster.jpg`
- `paperclip_runtime_duel/outputs/boss_gallery_v0/labebe_boss_gallery_walkthrough_contact_sheet.jpg`
- `paperclip_runtime_duel/outputs/boss_gallery_v0/labebe_boss_gallery_walkthrough_mobile_poster.jpg`
- `paperclip_runtime_duel/outputs/boss_gallery_v0/labebe_boss_gallery_walkthrough_mobile_contact_sheet.jpg`
- `paperclip_runtime_duel/outputs/boss_gallery_v0/walkthrough_frames/`

## Method

The renderer opens the live Boss Gallery URL in headless Chrome through CDP, captures section-level desktop/mobile frames at multiple scroll positions, and turns those frames into walkthrough MP4s with FFmpeg.

Renderer:

- `work_products/presentation_strategy/render_boss_gallery_walkthrough.mjs`

## Verification

- Desktop URL returned HTTP 200.
- Mobile URL returned HTTP 200.
- Desktop ffprobe: H.264, 1920x1080, 30fps, about 48.97 seconds.
- Mobile ffprobe: H.264, 1080x1920, 30fps, about 44.97 seconds.
- Browser capture metrics from the renderer:
  - desktop `horizontalOverflow=false`
  - mobile `horizontalOverflow=false`

## Boundary

This is not a consumer-site asset and must not be embedded into the Labebe DTC website. It is an internal presentation video for the Paperclip / AI Boss Gallery surface.
