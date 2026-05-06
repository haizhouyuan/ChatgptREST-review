# Finbot Continuous Runtime Rollout v1

## Goal

Make `finbot` actually run continuously in production without depending on the unstable OpenClaw `agentTurn` cron lane.

The acceptance bar for this rollout was:

1. background discovery must execute unattended
2. the background lane must not depend on an LLM turn succeeding
3. `finbot` manual agent turns should still work for interactive delegation
4. OpenClaw state should no longer contain stale `finbot` cron jobs that can fail noisily

## Root cause

The earlier `finbot` rollout only installed OpenClaw cron jobs of type `agentTurn`:

- `finbot-daily-work-morning`
- `finbot-theme-batch-evening`

Those jobs depended on the embedded model lane completing a prompt turn before any deterministic `finagent` work happened. In practice this made unattended execution brittle:

- `openai-codex` refresh-token reuse caused auth failures
- `google-gemini-cli` could timeout on an isolated agent turn
- background work stalled before `openclaw_finbot.py` ever ran

So the problem was not the `finbot` helper script itself. The problem was that the scheduler was using the wrong execution substrate.

## Final design

### Background execution

Background `finbot` work now runs through **systemd user timers**, not OpenClaw cron:

- `chatgptrest-finbot-daily-work.timer`
- `chatgptrest-finbot-theme-batch.timer`

Those timers run deterministic commands:

- `ops/openclaw_finbot.py daily-work`
- `ops/openclaw_finbot.py theme-batch-run`

This means unattended discovery no longer depends on an LLM lane.

### OpenClaw role

OpenClaw keeps `finbot` as an interactive agent identity for:

- manual delegation from `main`
- heartbeat/inbox summary
- interactive review when a human wants `finbot` to explain or summarize the latest run

### Finbot daily loop

`daily-work` now does:

1. dashboard projection refresh
2. bounded `finagent daily-refresh`
3. watchlist scout
4. theme radar scout
5. optional batch themes only when explicitly requested elsewhere

The important change is that the daily lane now includes real source/data refresh instead of only replaying existing boards.

## Code changes

### Runtime + scheduling

- `chatgptrest/finbot.py`
  - added bounded `_run_finagent_daily_refresh()`
  - `daily_work()` now records `source_refresh`
  - `daily_work()` continues even if source refresh fails
- `ops/openclaw_finbot.py`
  - added `--skip-source-refresh`
  - added `--refresh-limit`
- `ops/systemd/chatgptrest-finbot-daily-work.service`
- `ops/systemd/chatgptrest-finbot-daily-work.timer`
- `ops/systemd/chatgptrest-finbot-theme-batch.service`
- `ops/systemd/chatgptrest-finbot-theme-batch.timer`
- `ops/systemd/enable_finbot_continuous.sh`
  - installs/enables the new timers
  - starts `daily-work` once immediately
  - disables legacy OpenClaw `finbot` cron jobs when they still exist

### OpenClaw state generation

- `scripts/rebuild_openclaw_openmind_stack.py`
  - `build_cron_jobs()` now returns no `finbot` jobs
  - background discovery authority moved to systemd timers

### Tests

- `tests/test_finbot.py`
  - daily work now covers `source_refresh`
  - verifies graceful continuation when refresh fails
- `tests/test_rebuild_openclaw_openmind_stack.py`
  - now asserts `build_cron_jobs(topology=\"ops\")["jobs"] == []`

## Live rollout steps executed

### 1. Rebuilt OpenClaw state

```bash
python3 scripts/rebuild_openclaw_openmind_stack.py --topology ops --prune-volatile
```

Observed:

- `~/.openclaw/cron/jobs.json` became:

```json
{
  "version": 1,
  "jobs": []
}
```

### 2. Enabled deterministic finbot timers

```bash
./ops/systemd/enable_finbot_continuous.sh
```

This installed and enabled:

- `/home/yuanhaizhou/.config/systemd/user/chatgptrest-finbot-daily-work.service`
- `/home/yuanhaizhou/.config/systemd/user/chatgptrest-finbot-daily-work.timer`
- `/home/yuanhaizhou/.config/systemd/user/chatgptrest-finbot-theme-batch.service`
- `/home/yuanhaizhou/.config/systemd/user/chatgptrest-finbot-theme-batch.timer`

### 3. Verified timer state

`systemctl --user list-timers --all | rg 'chatgptrest-finbot'` showed:

- `chatgptrest-finbot-daily-work.timer`
- `chatgptrest-finbot-theme-batch.timer`

with future trigger times scheduled.

## Live proof that finbot now runs

### A. `daily-work` succeeded under systemd

`systemctl --user status chatgptrest-finbot-daily-work.service` showed:

- `status=0/SUCCESS`

The service journal ended with:

- `candidate_tsmc_cpo_cpo_d519030bd1`
- `route = opportunity`
- `created_count = 2`

This means unattended daily work completed and emitted fresh output.

### B. `theme-batch-run` succeeded under systemd

`systemctl --user status chatgptrest-finbot-theme-batch.service` showed:

- `status=0/SUCCESS`

The journal included five theme results:

- `transformer -> 中国西电`
- `ai_energy_onsite_power -> GE Vernova`
- `silicon_photonics -> 中际旭创`
- `memory_bifurcation -> SK Hynix`
- `commercial_space -> Rocket Lab`

### C. Finbot inbox contains live pending work

`python3 ops/openclaw_finbot.py inbox-list --format json --limit 10` returned:

- a fresh `TSMC CPO` frontier radar item
- a live `transformer-supercycle` watchlist item
- theme-run items for the five active themes

### D. Manual finbot agent turn still works

This interactive smoke passed:

```bash
openclaw agent --agent finbot --message "Run `python3 .../ops/openclaw_finbot.py inbox-list --format json --limit 3` and reply with one-sentence Chinese summary only." --json --timeout 120
```

Observed result:

- `status = ok`
- provider = `google-gemini-cli`
- model = `gemini-2.5-pro`
- duration ≈ `8.6s`

So the agent identity still works for manual delegation, while background execution no longer depends on it.

## What changed in production behavior

Before:

- `finbot` continuous work = OpenClaw cron + LLM turn
- if the model lane failed, the job never reached deterministic research logic

After:

- `finbot` continuous work = systemd timer + deterministic Python CLI
- OpenClaw agent turns are now only needed for interactive delegation and summaries

## Remaining limitation

Interactive `finbot` still depends on the OpenClaw model lane. It is now usable again, but its reliability is still tied to provider health.

That is acceptable because background discovery no longer depends on it.

## Bottom line

`finbot` is now genuinely continuous:

- unattended background discovery runs under systemd
- OpenClaw `finbot` cron jobs are removed from active state
- daily and nightly finbot jobs complete successfully
- manual `finbot` agent turns still work

This is the first rollout where `finbot` is not just configured to keep working, but is actually running on a deterministic substrate that can keep working even when the LLM lane is flaky.
