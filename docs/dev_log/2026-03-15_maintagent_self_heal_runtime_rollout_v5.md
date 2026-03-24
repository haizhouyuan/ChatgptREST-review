## Scope

This follow-up closed two deployment-quality gaps that became visible only after
running maintagent live against the clean runtime worktree:

- API and MCP were still not guaranteed to run from the same checkout as maint
  daemon and workers.
- maintagent repo memory still described `state/` and `artifacts/` as if they
  lived under the worktree, even though the live runtime uses the primary repo
  root as the shared persistent state root.

## Root Cause

The previous rollout only partially aligned runtime units:

- maint daemon and workers already had `20-runtime-worktree.conf`
- API still pointed at the primary checkout
- MCP still executed the primary-checkout `chatgptrest_mcp_server.py`

Separately, `chatgptrest/ops_shared/maint_memory.py` derived repo memory paths
directly from `_REPO_ROOT`, which is correct for canonical docs but wrong for
shared runtime state when code is deployed from a clean worktree.

## Change

Updated:

- `ops/systemd/enable_maint_self_heal.sh`
- `chatgptrest/ops_shared/maint_memory.py`
- `chatgptrest/executors/sre.py`
- `docs/runbook.md`
- `docs/maint_daemon.md`

The rollout script now:

- writes runtime-worktree drop-ins for `chatgptrest-api.service`
- writes runtime-worktree drop-ins for `chatgptrest-mcp.service`
- keeps `state/` and `artifacts/` pinned to the primary repo root
- restarts API/MCP/maint/workers together

The repo-memory helper now:

- records `code_checkout`
- records `shared_state_root`
- renders `key_state_paths` from the shared state root rather than the worktree

`sre.fix_request` request artifacts now persist those repo-memory fields in
structured JSON, so later diagnosis can see both the code checkout and the live
data root explicitly.

## Validation

Regression suite:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_maint_bootstrap_memory.py \
  tests/test_sre_fix_request.py
```

Expected result:

- `11 passed`

Live validation:

- reran `ops/systemd/enable_maint_self_heal.sh`
- confirmed API/MCP/maint/workers all run with `PYTHONPATH` and
  `WorkingDirectory` set to the clean worktree
- confirmed `CHATGPTREST_DB_PATH` and `CHATGPTREST_ARTIFACTS_DIR` still point
  to `/vol1/1000/projects/ChatgptREST/state` and `/vol1/1000/projects/ChatgptREST/artifacts`
- confirmed the previously stuck `sre.fix_request` job
  `c8a52240b1b6473ba09a49e4a7d73c23` completed in `0.3s` after restart

## Why This Matters

Without this fix, maintagent could hold the right code in memory but still point
its repo facts at the wrong operational state paths, which degrades diagnosis
quality and makes self-heal recommendations less trustworthy.

This change makes the live runtime model explicit:

- clean worktree for code
- primary repo root for shared state
- the same view reflected in maintagent memory, service config, and SRE lane
  artifacts
