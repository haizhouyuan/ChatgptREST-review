# Finbot Continuous Discovery Blueprint v1

## Goal

让 OpenClaw 里的 `finbot` 从“dashboard refresh + watchlist scout”升级为持续运行的投研助理：

- 持续刷新控制平面
- 持续发现新机会
- 持续重跑既有主题研究
- 把 actionable 结果沉淀到 inbox
- 只把高价值变化回传给 `main`

## Runtime Shape

### Heartbeat

Heartbeat 继续保持轻量，只做：

- `dashboard-refresh`
- `inbox-list`
- 对 net-new actionable inbox delta 做静默升级

Heartbeat 明确不做：

- 广泛 discovery
- KOL sweep
- theme batch research

### Cron

`ops` 拓扑下，`finbot` 新增两条正式自动化任务：

1. `finbot-daily-work-morning`
   - `0 7 * * *`
   - 运行 `python3 ops/openclaw_finbot.py daily-work --format json --scope today --limit 8`
   - 内含：
     - dashboard refresh
     - watchlist scout
     - theme radar scout

2. `finbot-theme-batch-evening`
   - `30 20 * * *`
   - 运行 `python3 ops/openclaw_finbot.py theme-batch-run --format json --limit 5`
   - 用 `/vol1/1000/projects/finagent` 的事件引擎重跑多主题研究

## Finbot Command Surface

Canonical CLI: `ops/openclaw_finbot.py`

### Commands

- `dashboard-refresh`
- `watchlist-scout`
- `theme-radar-scout`
- `theme-batch-run`
- `daily-work`
- `theme-catalog`
- `inbox-list`
- `inbox-ack`

## Data / Handoff

### Inbox

- pending:
  - `artifacts/finbot/inbox/pending/*.json`
  - `artifacts/finbot/inbox/pending/*.md`
- archived:
  - `artifacts/finbot/inbox/archived/*.json`
  - `artifacts/finbot/inbox/archived/*.md`

### Categories

- `watchlist_scout`
- `theme_radar`
- `theme_run`

## Theme Catalog

Repo-owned catalog:

- `config/finbot_theme_catalog.json`

Default themes:

- `transformer`
- `ai_energy_onsite_power`
- `silicon_photonics`
- `memory_bifurcation`
- `commercial_space`

Each entry points into `finagent`:

- `spec_path`
- `events_path`
- `as_of`
- `timeout_seconds`

## Design Rules

1. Reuse `finagent` rather than reimplementing research logic in ChatgptREST.
2. Use stable-content inbox ids so unchanged runs do not spam `main`.
3. Keep heartbeat cheap; push heavier research into cron.
4. Prefer file inbox over direct interrupt.

## Phase Result

This slice does not invent new investment logic. It turns existing `finagent` capabilities into a continuously running OpenClaw research lane.
