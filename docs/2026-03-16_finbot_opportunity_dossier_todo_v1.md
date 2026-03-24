# 2026-03-16 Finbot Opportunity Dossier TODO v1

## Goal

Make `finbot` go one level deeper than radar/brief:

- detect a frontier opportunity
- deepen it automatically into an investor-grade dossier
- expose the dossier in the investor dashboard
- keep the continuous runtime stable and deduplicated

## Work Items

- [ ] Add `opportunity-deepen` workflow to `chatgptrest.finbot`
- [ ] Use `coding_plan` API lane as the primary synthesis engine
- [ ] Add freshness guard so the same candidate is not re-deepened every run
- [ ] Persist dossier artifacts under `artifacts/finbot/opportunities/<candidate_id>/`
- [ ] Emit a stable `research_package` inbox item
- [ ] Auto-trigger deepening from `theme_radar_scout` for top actionable candidates
- [ ] Add CLI entry in `ops/openclaw_finbot.py`
- [ ] Extend dashboard service to load latest dossier for an opportunity
- [ ] Extend investor opportunity page to render dossier summary and links
- [ ] Add tests for dossier generation, auto-deepen trigger, and dashboard rendering
- [ ] Run targeted tests
- [ ] Run live finbot smoke and verify dossier artifacts + dashboard pages
- [ ] Record walkthrough v2 and final rollout notes

## Constraints

- Keep `finbot` on the stable API lane (`coding_plan` / MiniMax-M2.5 path)
- Do not spam duplicate dossiers for the same candidate
- Keep outputs investor-readable; avoid dumping raw JSON into the dashboard
- Preserve artifact history while exposing a stable latest pointer
