# Investor Dashboard Live Rollout v1

> Date: 2026-03-16
> Branch: `codex/finbot-runtime-deploy-20260316`

## What Was Deployed

The ChatgptREST API service was switched from the canonical repo checkout to the deployment worktree used for the current finbot runtime pass:

- worktree: `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316`
- live service: `chatgptrest-api.service`

The service override applied was:

```ini
[Service]
WorkingDirectory=/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316
Environment=PYTHONPATH=/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316
Environment=CHATGPTREST_DB_PATH=/vol1/1000/projects/ChatgptREST/state/jobdb.sqlite3
Environment=CHATGPTREST_ARTIFACTS_DIR=/vol1/1000/projects/ChatgptREST/artifacts
```

Location:

- `~/.config/systemd/user/chatgptrest-api.service.d/30-investor-dashboard-worktree.conf`

## Why

The canonical repo working tree is not safe to edit directly right now, but the investor dashboard and finbot quality fixes need to be live-testable against the actual API on `127.0.0.1:18711`.

Deploying the user service against the validated worktree keeps:

- code isolated
- db/artifacts pointed at canonical runtime state
- rollback simple

## Commands Run

```bash
systemctl --user daemon-reload
systemctl --user restart chatgptrest-api.service
systemctl --user --no-pager --full status chatgptrest-api.service
```

## Live Verification

Pages checked directly against live API:

```bash
curl -sS http://127.0.0.1:18711/v2/dashboard/investor
curl -sS http://127.0.0.1:18711/v2/dashboard/investor/themes/transformer
curl -sS http://127.0.0.1:18711/v2/dashboard/investor/opportunities/candidate_tsmc_cpo_cpo_d519030bd1
curl -sS http://127.0.0.1:18711/v2/dashboard/investor/sources/src_broadcom_ir
```

Observed:

- all pages returned `200`
- live investor page title: `Investor Research Desk`
- live transformer theme page title: `变压器超级周期 / AI 电力表达分层`
- live opportunity page title: `candidate_tsmc_cpo_cpo_d519030bd1`

## Live Data Quality Checks

The live pages now reflect the fixes from the quality pass:

- `transformer` now shows:
  - `recommended_posture = watch_with_prepare_candidate`
  - `best_expression = sntl_xidian_alt`
- `ai_energy_onsite_power` now shows:
  - `recommended_posture = watch_with_prepare_candidate`
  - `best_expression = sntl_gev_ai_power`
- `commercial_space` now shows:
  - `recommended_posture = watch_only`
  - `best_expression = sntl_rklb_space_systems`

Finbot inbox also now uses stable ids in pending:

- `finbot-radar-candidate-tsmc-cpo-cpo-d519030bd1`
- `finbot-brief-candidate-tsmc-cpo-cpo-d519030bd1`
- `finbot-watchlist-transformer-supercycle`

Legacy digest-style duplicates were moved to:

- `artifacts/finbot/inbox/archived/`

## Rollback

If the worktree deployment needs to be reverted:

1. remove or disable `30-investor-dashboard-worktree.conf`
2. `systemctl --user daemon-reload`
3. `systemctl --user restart chatgptrest-api.service`

This returns the service to the canonical repo checkout defined by the lower-priority drop-in.

## Remaining Limits

1. This rollout fixes the investor-facing dashboard surface and finbot inbox quality, not the deeper `finagent` research model itself.
2. The live service still warns when auth tokens are not configured.
3. GitNexus `impact` / `detect_changes` remained unavailable during this pass with `Transport closed`, so validation relied on:
   - targeted tests
   - finbot live smoke
   - direct live HTTP checks against `127.0.0.1:18711`
