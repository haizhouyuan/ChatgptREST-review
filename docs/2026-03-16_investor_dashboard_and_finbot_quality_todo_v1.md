# Investor Dashboard And Finbot Quality Todo v1

## Goal

Move the current `finbot` + dashboard stack from scout-grade output to investor-consumable output.

## Problems confirmed in live state

1. `finbot` writes duplicate radar/watch items for the same logical opportunity or thesis.
2. `theme_radar` stops at detection; it does not open a structured deepening brief.
3. investor dashboard is present but not yet wired as the primary investor entry in navigation.
4. run-report parsing is brittle and leaves some theme detail cards with blank posture / best-expression fields.
5. investor opportunity cards do not yet provide enough next-step / source / detail linkage.

## Implementation tasks

### P0. Inbox coalescing

- add stable logical keys for:
  - `watchlist_scout`
  - `theme_radar`
  - `theme_run`
- overwrite/update the current pending item instead of creating repeated copies
- add tests for repeated writes with changed payloads

### P0. Deepening brief

- when `theme_radar` emits an `opportunity`, also emit a linked `deepening_brief`
- include:
  - why now
  - next proving milestone
  - related theme(s)
  - suggested source lanes
  - suggested expression lanes
- make the brief clickable from dashboard and inbox markdown

### P0. Investor dashboard alignment

- add `Investor` into dashboard nav
- make `/v2/dashboard/finagent` and investor page feel like the primary human-facing research surface
- enrich opportunity cards with next action / deepening link / reader link
- ensure source and planning links resolve cleanly

### P0. Run summary parsing hardening

- parse both:
  - `recommended posture:`
  - `best expression:`
  - legacy backtick formats
- add tests using the transformer report format

### P1. Theme/run card upgrade

- include investor-grade summary in `theme_run` inbox markdown:
  - current action
  - why not now
  - forcing events
- keep raw payload hidden from the default human view

## Acceptance bar

1. repeated `daily-work` does not create duplicate pending items for the same logical opportunity
2. each open frontier opportunity can link to a structured deepening brief
3. transformer theme detail no longer shows blank posture / best-expression fields
4. investor dashboard can be used as the primary human-facing research entry
5. tests cover coalescing + run summary parsing + investor routes
