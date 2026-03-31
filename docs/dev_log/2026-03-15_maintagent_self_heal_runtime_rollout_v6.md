## Scope

This final rollout follow-up closed one last deployment drift that remained
after the runtime-worktree/self-heal alignment:

- `chatgptrest-api.service` still had a stale hand-written
  `99-current-working-tree.conf`
- that drop-in shadowed the managed `20-runtime-worktree.conf`
- result: API kept its `WorkingDirectory` and `PYTHONPATH` pinned to the primary
  checkout even though maint/MCP/workers were already aligned to the clean
  runtime worktree

## Root Cause

`enable_maint_self_heal.sh` was only writing the managed runtime-worktree
drop-ins. It did not neutralize higher-priority local overrides left behind by
previous manual debugging.

Because systemd applies later-numbered drop-ins last, the stale API override won
silently.

## Change

Updated:

- `ops/systemd/enable_maint_self_heal.sh`
- `docs/runbook.md`

The rollout script now:

- checks each managed unit drop-in directory for `99-current-working-tree.conf`
- moves any such stale override aside to
  `99-current-working-tree.conf.disabled-by-maint-self-heal`
- then writes the managed runtime-worktree drop-in and restarts the services

## Live Validation

After rerunning `ops/systemd/enable_maint_self_heal.sh`:

- `chatgptrest-api.service` picked up the clean worktree `WorkingDirectory`
- `chatgptrest-api.service` kept `CHATGPTREST_DB_PATH` and
  `CHATGPTREST_ARTIFACTS_DIR` on `/vol1/1000/projects/ChatgptREST`
- `chatgptrest-mcp.service`, maint daemon, and workers stayed aligned with the
  same code checkout and shared state root

## Why This Matters

Without this fix, the system would look aligned in documentation and env output
while the API still executed from a different checkout than maintagent and MCP.

That kind of hidden override directly undermines:

- diagnosis trustworthiness
- reproducible self-heal behavior
- operator confidence when reading live memory and issue artifacts
