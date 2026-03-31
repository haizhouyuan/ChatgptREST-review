# OpenMind Code Review Package Index

Generated: 2026-02-28
Target use: ChatGPT Research + Gemini Deep Research

## Upload limit strategy (Gemini <= 10 files)

This package is intentionally merged into 8 markdown files (+ optional zip) to stay below the upload limit.

## Files

1. `01_OPENMIND_REPO_SNAPSHOT.md`
   - OpenMind repo structure, README, pyproject.
2. `02_OPENMIND_KERNEL_CODE.md`
   - Core kernel code bundle (`artifact_store.py`, `event_bus.py`, `policy_engine.py`).
3. `03_AIOS_REQUIREMENTS_BACKGROUND.md`
   - AIOS requirement/context/background consolidated.
4. `04_MULTI_MODULE_DIR_SUMMARIES.md`
   - openclaw/homeagent/storyplay/research directory-level summaries.
5. `05_MULTI_MODULE_ARCHIVE_CONFLICTS.md`
   - Cross-module conflict and overlap background.
6. `06_PRIOR_REVIEW_REQUESTS_AND_OUTPUTS.md`
   - Previous review requests and major prior output.
7. `07_MODULE_ASSETS_LEDGER_OVERVIEW.md`
   - Quantitative overview from multi-module assets ledgers.
8. `08_RESEARCH_PROMPTS_CHATGPT_GEMINI.md`
   - Ready-to-use prompts for ChatGPT Research / Gemini Deep Research.
9. `09_OPENMIND_LATEST_MERGED_REVIEW_BRIEF_20260228.md`
   - Latest single-file merged brief (updated code snapshot + multi-module background + prior review context).

## Recommended upload order

1) `00_INDEX.md`
2) `09_OPENMIND_LATEST_MERGED_REVIEW_BRIEF_20260228.md`
3) `08_RESEARCH_PROMPTS_CHATGPT_GEMINI.md`

Alternative (multi-file detail mode):
1) `00_INDEX.md`
2) `01_OPENMIND_REPO_SNAPSHOT.md`
3) `02_OPENMIND_KERNEL_CODE.md`
4) `03_AIOS_REQUIREMENTS_BACKGROUND.md`
5) `04_MULTI_MODULE_DIR_SUMMARIES.md`
6) `05_MULTI_MODULE_ARCHIVE_CONFLICTS.md`
7) `06_PRIOR_REVIEW_REQUESTS_AND_OUTPUTS.md`
8) `07_MODULE_ASSETS_LEDGER_OVERVIEW.md`
9) `08_RESEARCH_PROMPTS_CHATGPT_GEMINI.md`

## Execution mode guide

- Mode A (preferred): Try code import / repo import first.
- Mode B (fallback): If import fails, continue using merged files above.

Do not stop on import failure; continue with fallback merged files.
