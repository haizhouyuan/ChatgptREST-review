# Finbot Continuous Discovery Walkthrough v1

## What changed

This pass upgraded `finbot` from a narrow scout into a continuously running investment-research helper backed by `/vol1/1000/projects/finagent`.

Changed files:

- `chatgptrest/finbot.py`
- `ops/openclaw_finbot.py`
- `scripts/rebuild_openclaw_openmind_stack.py`
- `config/finbot_theme_catalog.json`
- `tests/test_finbot.py`
- `tests/test_rebuild_openclaw_openmind_stack.py`

## New runtime behaviors

### New finbot commands

- `theme-radar-scout`
- `theme-batch-run`
- `daily-work`
- `theme-catalog`

### New cron contract

- `finbot-daily-work-morning`
- `finbot-theme-batch-evening`

### New catalog

- `config/finbot_theme_catalog.json`

## Verification

### Targeted pytest

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_finbot.py \
  tests/test_autoorch.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_verify_openclaw_openmind_stack.py
```

Result: pass

### CLI help

```bash
python3 ops/openclaw_finbot.py --help
```

Result: new commands are exposed.

### Live-ish smokes against real finagent data

#### Watchlist scout

```bash
python3 ops/openclaw_finbot.py watchlist-scout \
  --format json \
  --finbot-root /tmp/finbot-live-watchlist \
  --scope today \
  --limit 6
```

Observed:

- inbox item created
- top priority target = `tc_transformer_tbea`
- thesis = `transformer-supercycle`

#### Theme radar scout

```bash
python3 ops/openclaw_finbot.py theme-radar-scout \
  --format json \
  --finbot-root /tmp/finbot-live-smoke \
  --limit 6
```

Observed:

- inbox item created
- top candidate = `candidate_tsmc_cpo_cpo_d519030bd1`
- route = `opportunity`
- residual_class = `frontier`

#### Theme batch run

```bash
python3 ops/openclaw_finbot.py theme-batch-run \
  --format json \
  --finbot-root /tmp/finbot-live-batch5 \
  --limit 5
```

Observed:

- 5 theme runs completed
- created inbox items for:
  - transformer → 中国西电
  - ai_energy_onsite_power → GE Vernova
  - silicon_photonics → 中际旭创
  - memory_bifurcation → SK Hynix
  - commercial_space → Rocket Lab

#### Daily work

```bash
python3 ops/openclaw_finbot.py daily-work \
  --format json \
  --finbot-root /tmp/finbot-live-daily \
  --scope today \
  --limit 3 \
  --include-theme-batch
```

Observed:

- dashboard refresh ran
- watchlist scout ran
- theme radar scout ran
- 3 theme batch runs completed
- `created_count = 5`

## GitNexus note

Required `gitnexus_impact` / `gitnexus_context` / `gitnexus_detect_changes` calls were attempted for:

- `build_cron_jobs`
- `watchlist_scout`

All timed out at 120s in MCP. The implementation proceeded with cautious local inspection and explicit test coverage.

## Outcome

`finbot` can now:

- keep the control plane fresh
- surface known watchlist deltas
- mine new theme-radar candidates
- rerun multiple theme research packages
- hand off everything through a stable inbox contract
