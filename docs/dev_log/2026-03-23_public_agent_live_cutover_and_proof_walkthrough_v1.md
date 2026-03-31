# Walkthrough: Public Agent Live Cutover And Proof v1

## Why This Package Was Needed

The contract-first upgrade had already landed in code, but a prior review correctly noted that
the live public surface was still not showing:

- `task_intake`
- `control_plane`
- `clarify_diagnostics`

At first glance that looked like either:

1. wrapper/MCP response shaping
2. stale runtime processes
3. missing live-path implementation

## What Was Checked

The investigation explicitly separated those possibilities.

### 1. Code Path Check

`routes_agent_v3.py` already injected the new fields on the generic clarify path.

`agent_mcp.py` already forwarded the northbound objects:

- `execution_profile`
- `task_intake`
- `workspace_request`
- `contract_patch`

`chatgptrest_call.py` was then checked and confirmed to print the MCP result as-is, without trimming
the new fields.

That ruled out "the code was never written" and "the wrapper cuts the fields away".

### 2. Live Runtime Check

The live service timestamps were then compared against the contract-first commits.

That showed the critical mismatch:

- API and MCP were started long before the contract-first commits landed

That made stale runtime the most likely explanation.

### 3. Runtime Refresh

`chatgptrest-api.service` first entered a slow graceful shutdown.

To complete the cutover cleanly:

- the old API process was killed
- the failed state was reset
- the API service was started again
- the MCP service was restarted

After refresh both services were running with `ExecMainStartTimestamp=2026-03-23 13:38:11 CST`.

## What The New Live Proof Covers

The new validation package checks 7 things:

1. API service is running after cutover
2. MCP service is running after cutover
3. raw API clarify path projects `task_intake/control_plane/clarify_diagnostics`
4. public MCP clarify path projects the same fields
5. wrapper path projects the same fields
6. same-session `contract_patch` exits clarify via deferred continuation
7. the refreshed session projection reflects the patched contract

## Why Deferred Patch Was Used

The second-turn patch proof intentionally uses `delivery_mode=deferred`.

That keeps the proof focused on:

- contract patch acceptance
- same-session continuation
- control-plane projection

without making the validation depend on downstream provider completion timing.

## Accepted Outputs

Accepted artifact bundle:

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/public_agent_live_cutover_validation_20260323/report_v1.json)
- [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/public_agent_live_cutover_validation_20260323/report_v1.md)

Accepted command:

```bash
PYTHONPATH=. ./.venv/bin/python ops/run_public_agent_live_cutover_validation.py
```

Accepted result:

- `7/7` passed

## Final Interpretation

The earlier review was directionally right:

- the code package had landed
- the live public surface had not fully reflected it yet

What changed here is that the gap is now closed.

The correct current statement is:

**the public-agent contract-first upgrade is now live on the public surface, not just in code and synthetic validation.**
