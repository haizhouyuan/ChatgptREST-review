# 2026-03-09 OpenClaw/OpenMind Rebuild Round 8

## Summary

- Normalized plugin provenance paths in the rebuild script so OpenClaw can correctly recognize tracked local installs after path resolution.
- Added explicit provenance coverage for the locally maintained `env-http-proxy` plugin.
- Switched `maintagent` from Gemini to Codex after live validation showed that the Gemini lane timed out repeatedly for even trivial READY probes.

## Why This Round Was Needed

After Round 7, the active agent topology was correct, but two integration-quality issues remained:

1. `openclaw plugins list` / `plugins doctor` still emitted repeated provenance warnings such as:
   - `loaded without install/load-path provenance`
2. `maintagent` no longer hit session-lock contention when probed with an isolated session id, but it still timed out at 120 seconds on a trivial `Reply ONLY READY.` request.

The provenance warning was not a functional outage, but it meant the OpenClaw trust model still viewed key plugins as effectively untracked local code.

The `maintagent` timeout was more serious: the watchdog lane was configured, but not reliably usable.

## Root Cause

### Plugin provenance drift

The rebuild script copied `plugins.installs` and `plugins.load.paths` from the existing config as raw strings.

That was not stable enough on this host:

- install records often used `/home/...`
- runtime-loaded plugin sources resolved to `/vol1/1000/home-yuanhaizhou/...`

OpenClaw’s provenance matcher works on normalized paths. Because the recorded path and the resolved runtime path did not match, correctly installed plugins were still flagged as untracked.

`env-http-proxy` had an additional gap: it was present as a local plugin, allowed by config, and loaded successfully, but it did not have install/load-path provenance at all.

### `maintagent` model mismatch

Live probe results showed a clear split:

- `main` with Codex returned quickly
- `openclaw-orch` with Codex returned quickly
- `planning` with Gemini returned quickly
- `maintagent` with Gemini timed out even on a trivial READY message

This was not a session-lock artifact anymore. With an explicit isolated session id, the lane still timed out.

For this host and this watchdog role, reliability mattered more than the marginal savings of keeping the maintenance lane on Gemini.

## Code Changes

### `scripts/rebuild_openclaw_openmind_stack.py`

Added:

- `_normalize_plugin_path(...)`
- `normalize_plugin_load_paths(...)`
- `normalize_plugin_installs(...)`

These changes now:

- resolve existing `plugins.load.paths` to normalized real paths
- resolve install record `installPath` / `sourcePath` entries to normalized real paths
- add explicit provenance for the local `env-http-proxy` plugin root when present

Also changed:

- `maintagent.model` from `google-gemini-cli/gemini-2.5-pro`
- to `openai-codex/gpt-5.4`

### `tests/test_rebuild_openclaw_openmind_stack.py`

Added coverage that:

- build-time plugin load paths are normalized to resolved paths
- install records are normalized to resolved real paths
- local proxy provenance paths are retained in the generated config
- `maintagent` now builds with `openai-codex/gpt-5.4`

## Validation

### Code-level

Passed:

```bash
./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py
./.venv/bin/python -m py_compile scripts/rebuild_openclaw_openmind_stack.py tests/test_rebuild_openclaw_openmind_stack.py
```

### Live rebuild

Executed:

```bash
systemctl --user stop openclaw-gateway.service
./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --openclaw-bin /home/yuanhaizhou/.local/bin/openclaw
systemctl --user start openclaw-gateway.service
```

### Plugin trust / provenance

Observed after rebuild:

```bash
openclaw plugins doctor
```

Result:

- `No plugin issues detected.`

The old untracked-local-code provenance warnings for:

- `dingtalk`
- `env-http-proxy`
- `openmind-advisor`
- `openmind-graph`
- `openmind-memory`
- `openmind-telemetry`

no longer appeared in `plugins doctor`.

Residual note:

- Node/undici still emits `EnvHttpProxyAgent is experimental`
- this is an upstream runtime warning, not a provenance/trust failure

### Live agent probe

Executed:

```bash
openclaw agent --agent maintagent --session-id probe-maintagent-... --message 'Reply ONLY READY.' --json --timeout 120
```

Result:

- reply returned `READY`
- provider `openai-codex`
- model `gpt-5.4`
- end-to-end duration about `14.7s`

This replaced the previous behavior where the same watchdog lane timed out at `120s`.

## Current Assessment

After this round:

- the active OpenClaw state is pruned to the intended five-agent topology
- Codex auth sync is repaired
- plugin provenance is recognized by OpenClaw’s trust model
- `maintagent` is now actually usable as a heartbeat/watchdog lane

That is a materially stronger baseline for the next phase: upstream/community best-practice review and the final OpenClaw + OpenMind blueprint.
