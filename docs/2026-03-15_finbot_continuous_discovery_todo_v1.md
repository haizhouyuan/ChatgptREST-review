# Finbot Continuous Discovery TODO v1

## Goal

让 OpenClaw 里的 `finbot` 不只刷新 dashboard 和扫 watchlist，而是持续：

- 发现新机会
- 重跑既有主题研究
- 把 actionable 结果写入 inbox
- 只把高价值变化回传给 `main`

## Work Items

1. Extend `chatgptrest.finbot`
   - add generic finagent CLI runner
   - add `theme_radar_scout`
   - add `theme_batch_run`
   - add `daily_work`
   - add theme catalog loading

2. Extend `ops/openclaw_finbot.py`
   - add `theme-radar-scout`
   - add `theme-batch-run`
   - add `daily-work`
   - add `theme-catalog`

3. Add finbot theme catalog
   - transformer
   - ai_energy_onsite_power
   - silicon_photonics
   - memory_bifurcation
   - commercial_space

4. Update OpenClaw rebuild/runtime contract
   - finbot tools/role text
   - finbot heartbeat wording
   - finbot cron jobs for continuous discovery

5. Add tests
   - theme radar scout inbox creation
   - theme batch run summary creation
   - daily work composition
   - cron jobs include new finbot automation

6. Run verification
   - targeted pytest
   - finbot CLI smokes

7. Write docs
   - blueprint v3
   - walkthrough v1

## Notes

- GitNexus impact/context timed out at 120s for `build_cron_jobs` and `watchlist_scout`; proceed cautiously and record this limitation in walkthrough.
- Do not touch the dirty main worktree.
- Push directly to `origin/master` after tests pass.
