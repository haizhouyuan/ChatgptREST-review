# Finbot Continuous Runtime Rollout v2

## What changed after v1

`v1` proved that the continuous runtime design worked, but the first live systemd rollout still pointed to a temporary worktree under `/tmp`. That was functional but not production-safe because a temp checkout is not an acceptable long-lived execution root.

This `v2` rollout closes that last production gap:

1. move the live systemd services from the temporary checkout to a stable deployment worktree under `/vol1/1000/worktrees/`
2. rebuild OpenClaw state again to keep `finbot` cron empty
3. re-enable timers from the stable deployment checkout
4. run another full live proof from the stable path

## Stable deployment root

The live `finbot` systemd services now point to:

- working directory: `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316`
- CLI entrypoint: `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316/ops/openclaw_finbot.py`
- Python runtime: `/vol1/1000/projects/ChatgptREST/.venv/bin/python`

This keeps the execution root stable while still using the shared canonical virtualenv.

## Live rollout steps executed in v2

### 1. Created a stable deployment worktree

A dedicated deployment worktree was created for the already-tested runtime branch:

```bash
git -C /vol1/1000/projects/ChatgptREST branch codex/finbot-runtime-deploy-20260316 b92babb
git -C /vol1/1000/projects/ChatgptREST worktree add \
  /vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316 \
  codex/finbot-runtime-deploy-20260316
```

### 2. Rebuilt OpenClaw state again

```bash
cd /vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316
python3 scripts/rebuild_openclaw_openmind_stack.py --topology ops --prune-volatile
```

Observed again:

```json
{
  "version": 1,
  "jobs": []
}
```

So `finbot` still has no active OpenClaw cron jobs and background authority remains outside the LLM lane.

### 3. Reinstalled timers from the stable deployment checkout

```bash
cd /vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316
./ops/systemd/enable_finbot_continuous.sh
```

### 4. Verified the installed user services point to the stable path

`systemctl --user cat chatgptrest-finbot-daily-work.service chatgptrest-finbot-theme-batch.service` now shows:

- `WorkingDirectory=/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316`
- `ExecStart=/vol1/1000/projects/ChatgptREST/.venv/bin/python /vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316/ops/openclaw_finbot.py ...`

## Live proof after stable-path cutover

### A. Timers remain active

`systemctl --user list-timers --all | rg 'chatgptrest-finbot'` showed:

- `chatgptrest-finbot-daily-work.timer`
- `chatgptrest-finbot-theme-batch.timer`

with future trigger times scheduled.

### B. Daily work was manually triggered from the stable path and succeeded

```bash
systemctl --user start chatgptrest-finbot-daily-work.service
systemctl --user status chatgptrest-finbot-daily-work.service
```

Observed result:

- `status=0/SUCCESS`
- `ExecStart` used the stable worktree path
- journal ended with:
  - `candidate_tsmc_cpo_cpo_d519030bd1`
  - `route = opportunity`
  - `created_count = 2`

### C. Inbox continues to accumulate real work

`python3 ops/openclaw_finbot.py inbox-list --format json --limit 10` from the stable worktree returned:

- a fresh `TSMC CPO` frontier radar item
- a live `transformer-supercycle` watchlist item
- multiple theme-run items for the active theme set
- `pending_count = 12`

### D. Interactive finbot still works

A manual `openclaw agent --agent finbot ...` smoke again completed successfully with:

- `status = ok`
- provider = `google-gemini-cli`
- model = `gemini-2.5-pro`

This confirms the interactive lane still works while background discovery remains deterministic.

## Production conclusion

After `v2`, `finbot` is no longer only “working in principle”. It is now running from a stable deployment root with:

- no active OpenClaw cron dependency for background discovery
- active systemd timers
- successful daily unattended work
- successful nightly theme batch capability
- live inbox growth from real outputs
- working interactive agent delegation for manual use

## Remaining limitation

The only meaningful remaining limitation is still the same as in `v1`:

- interactive `finbot` depends on the OpenClaw model lane and therefore inherits provider health

That is acceptable because background discovery no longer depends on that lane.

## Final bottom line

`finbot` is now production-usable for continuous discovery:

- it runs unattended
- it no longer depends on an LLM turn to start work
- it is deployed from a stable non-temporary path
- it is writing real opportunity and watchlist outputs into the inbox
- it can still be interactively delegated to when needed
