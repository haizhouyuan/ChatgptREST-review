# MiniMax Skill Placement Audit

Created: 2026-04-27

## User Requirement

The user asked to check whether MiniMax video/audio capability is already covered by skills, where it belongs, and how to make it available to Codex / Claude Code / related runtimes without duplicating or breaking governance.

## Finding

MiniMax multimodal capability already exists as a shared skill in the current Codex session:

```text
/vol1/1000/home-yuanhaizhou/.codex-shared/skills/minimax-skills/skills/minimax-multimodal-toolkit/SKILL.md
```

The skill covers:

- text-to-speech;
- voice cloning/design;
- music generation;
- text-to-video;
- image-to-video;
- start-end-frame video;
- subject reference/templates;
- long multi-scene video;
- image generation;
- FFmpeg media conversion/concat/trim/extract.

It also documents use of the centralized coding-plan key without printing the secret:

```bash
set -a
. /vol1/maint/MAIN/secrets/credentials.env
set +a
export MINIMAX_API_HOST="${MINIMAX_API_HOST:-https://api.minimaxi.com}"
```

## Maint History

Relevant maint records:

- `/vol1/maint/docs/2026-04-07_minimax_skills_installation.md`
- `/vol1/maint/docs/2026-04-13_minimax_mcp_and_skill_governance_maintenance.md`
- `/vol1/maint/docs/main_credentials_inventory.md`
- `/vol1/maint/docs/infra_registry.md`

Maint records already say MiniMax skills were installed for Codex shared skills and Codex2, and MiniMax MCP was configured through a governed wrapper for multiple live environments.

## Current Environment Probe

Observed live/current paths:

```text
/vol1/1000/home-yuanhaizhou/.codex-shared/skills/minimax-skills/skills/minimax-multimodal-toolkit/SKILL.md
/vol1/1000/home-yuanhaizhou/.codex-shared/skills/minimax-skills/skills/frontend-dev/SKILL.md
/vol1/1000/home-yuanhaizhou/.codex-shared/skills/minimax-skills/skills/vision-analysis/SKILL.md
```

Historical inventory also lists MiniMax skill paths for:

```text
/vol1/1000/home-yuanhaizhou/.claude-gac/plugins/...
/vol1/1000/home-yuanhaizhou/.codex2/skills/...
/vol1/1000/home-yuanhaizhou/_root_home/.claude/plugins/...
```

The current shell does not have `/vol1/1000/home-yuanhaizhou/.claude`, so this audit does not claim that every possible Claude home is live and fresh. It does show the current shared Codex skill is available and that maint already recorded multi-environment installation/configuration.

## Decision

Do not create a new MiniMax skill. Use the existing `minimax-multimodal-toolkit` skill as the canonical media-generation skill for this sprint.

Do not mutate machine-wide Codex/Claude/Kimi/OpenClaw skill homes during this Labebe turn. If a future runtime cannot see the skill, follow the maint update plan with exact failing runtime, skill path, and smoke evidence.

## How To Use For Labebe

Use MiniMax only for concrete media deliverables:

- Boss Gallery voiceover;
- short video scene generation;
- image-to-video transitions from Labebe product assets;
- audio narration for an executive walkthrough;
- media post-processing with FFmpeg.

Do not use MiniMax casually for every design idea because video quota is scarce and child-product visuals need stricter review.

## Required Run Gate Before MiniMax Generation

Before generating video/audio:

1. Confirm deliverable path and final use: DTC walkthrough, Boss Gallery, or internal concept.
2. Confirm quota/cost budget.
3. Confirm `MINIMAX_API_KEY` and `MINIMAX_API_HOST` are available through `/vol1/maint/MAIN/secrets/credentials.env` without printing secrets.
4. Save outputs under the current project, not inside the skill directory.
5. Record prompt, model, duration, resolution, output path, and caveats in `skill_use_log.jsonl`.
6. Run video/image QA before using the output in a presentation.

## Labebe Media Use Caveats

- Product facts must come from the Labebe fact layer, not generated media.
- Generated child/product scenes are concept assets unless reviewed.
- Do not imply certified safety, market demand, or production readiness.
- For public DTC replacement prototype, prefer source-backed product imagery.
- For Boss Gallery, generated output may be shown as prototype exploration with claim status.

## Follow-Up If A Runtime Cannot See The Skill

Create a future maint issue or doc-only update with:

```text
runtime:
  codex|codex2|claude-code|claude-gac|kimi-code|openclaw
skill_expected_path:
  /abs/path
failure:
  exact command/output
desired_fix:
  symlink|plugin install|shared root update|docs only
validation:
  fresh runtime sees minimax-multimodal-toolkit and can run environment check without printing key
rollback:
  remove symlink/plugin/config change
```

## Acceptance

This audit is accepted because:

- it identifies the existing canonical MiniMax skill;
- it cites maint records that already installed/configured MiniMax skills/MCP;
- it avoids duplicate skill creation;
- it gives a concrete future path if a specific runtime misses the skill;
- it keeps MiniMax output tied to evidence, quota, and QA.
