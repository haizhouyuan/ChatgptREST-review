# 2026-03-09 OpenClaw + OpenMind Best-Practice Rebuild

## Goal

Rebuild the local OpenClaw shell around latest upstream runtime and the OpenMind bridge, without carrying forward the old private fork as the operational trunk.

## What changed

### 1. Rebuild baseline hardened

- kept the shell on the official OpenClaw CLI/runtime path
- normalized the enabled plugin set to a conservative baseline:
  - bundled/runtime: `acpx`, `diffs`, `feishu`, `google-gemini-cli-auth`
  - installed/local: `dingtalk`
  - OpenMind bridge: `openmind-advisor`, `openmind-graph`, `openmind-memory`, `openmind-telemetry`
- local note:
  - `env-http-proxy` may still exist on the host as an installed plugin, but it is no longer part of the supported enabled baseline
- normalized Feishu:
  - `default` routes to `main`
  - `research` stays disabled by default
- changed the topology baseline from five persistent lanes to two supported modes:
  - `lean`: `main` only
  - `ops`: `main + maintagent`
- set `main` to `tools.profile = coding`
  - `lean`: additive OpenMind tools only
  - `ops`: additive OpenMind tools + `sessions_send` / `sessions_list` / `sessions_history`
  - in `lean`, explicit deny also covers `sessions_send` / `sessions_list` / `sessions_history`
  - explicit deny now covers automation/ui/image plus `sessions_spawn` and `subagents`
  - supported baseline no longer writes `subagents.allowAgents` for `main`
- kept `maintagent` as an optional watchdog only:
  - `tools.profile = minimal`
  - additive `sessions_send` / `sessions_list`
  - no direct OpenMind tool surface in the supported baseline

### 2. OpenMind tool exposure fixed

Root cause was narrower than “plugin broken”:

1. OpenMind bridge plugins were loaded correctly.
2. `main` still did not consistently receive OpenMind tools in live runs.
3. The stable fix was to use additive optional-tool opt-in (`alsoAllow`) for the OpenMind bridge tools on top of a normal profile.

Important runtime reality:

- the installed stable runtime on this host does **not** accept `tools.allowlistMode`
- generic plugin docs still mention `allow`, but official optional-plugin docs now recommend additive `alsoAllow`
- live-good configuration for this host is therefore `profile + alsoAllow`, not plugin-only restrictive allowlists

### 3. Cross-agent handoff reduced to the only lane that still matters

The previous rebuild still assumed `planning/research/openclaw-orch` were permanent service lanes. That was no longer aligned with the real product shape, because those capabilities had already moved into OpenMind, skills, and ACP/on-demand workflows.

The live-good communication model is now:

- `lean`
  - no persistent agent-to-agent topology
  - `tools.agentToAgent.enabled = false`
- `ops`
  - `tools.agentToAgent.enabled = true`
  - `tools.agentToAgent.allow = [main, maintagent]`
  - `maintagent -> main` uses `sessions_send(sessionKey="agent:main:main", ...)`
  - `main` gets `sessions_send` / `sessions_list` / `sessions_history` only in this mode

The rebuild script and generated workspace instructions now encode that directly.

### 4. Workspace instructions made explicit

Generated workspace docs now encode the simplified contract directly:

```text
main -> primary workbench
maintagent -> optional watchdog
```

This removes the model guesswork that previously led to:

- stale role lanes being treated as production dependencies
- watchdog logic overreaching into `gateway` and transcript tools
- verifier logic being coupled to `planning` spawn behavior

### 5. OpenMind telemetry auth fixed

The gateway process was still missing `OPENMIND_API_KEY`, so `openmind-telemetry` kept flushing `401 Invalid or missing API key` to `/v2/telemetry/ingest`.

The stable fix is not to embed the key into `openclaw.json`, but to give `openclaw-gateway.service` the same env file authority as the integrated ChatgptREST host:

- managed drop-in: `~/.config/systemd/user/openclaw-gateway.service.d/20-openmind-cognitive.conf`
- contents: `EnvironmentFile=-~/.config/chatgptrest/chatgptrest.env`

After `daemon-reload + restart`, telemetry `401` noise stopped.

### 6. Topology simplification pass

The final correction was architectural, not cosmetic:

1. stop treating `planning/research/openclaw-orch` as if they were still required production lanes
2. make `main` the real workbench instead of a thin messaging dispatcher
3. keep `maintagent` only as an optional unattended watchdog

This matches the current OpenMind-heavy product reality much better than the previous five-lane layout.

## Validation

### Script / test validation

- `./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py tests/test_verify_openclaw_openmind_stack.py`
- `./.venv/bin/python -m py_compile scripts/rebuild_openclaw_openmind_stack.py ops/verify_openclaw_openmind_stack.py tests/test_rebuild_openclaw_openmind_stack.py tests/test_verify_openclaw_openmind_stack.py`

### Live rebuild

- `./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw --topology lean --prune-volatile`
- `systemctl --user daemon-reload`
- `systemctl --user restart openclaw-gateway.service`

### Live status

- `openclaw plugins doctor`
  - `No plugin issues detected.`
- `openclaw status --json`
  - expected topology after this pass: `main` only for `lean`, or `main + maintagent` for `ops`
  - actual live topology after this rebuild: `lean`
  - security summary: `critical=0 warn=2 info=1`
  - residual findings: `summary.attack_surface`, `gateway.trusted_proxies_missing`, `fs.state_dir.symlink`

### OpenMind bridge

- forced smoke:
  - `openclaw agent --agent main ...`
  - result: `FORCED_TOOL_OK`
- verifier transcript proof:
  - `tool_called=True`
  - `tool_result=True`
  - `assistant='OPENMIND_OK OPENMIND_PROBE_*'`

### Cross-agent communication

- `lean`
  - no communication probe is required because there is no persistent secondary lane
- `ops`
  - verifier now probes `maintagent -> main` directly with `sessions_send`
  - no `planning` spawn dependency remains

### Automated verifier

Added:

- `ops/verify_openclaw_openmind_stack.py`
- `tests/test_verify_openclaw_openmind_stack.py`

The live verifier now checks:

- `openclaw plugins doctor`
- `openclaw status --json`
- recognized topology is `lean` or `ops`
- legacy role agents are absent
- `main` OpenMind bridge tools
- `main` has no effective `sessions_spawn` or `subagents` after profile expansion
- negative runtime probes proving `main` returns `SESSIONS_SPAWN_UNAVAILABLE` / `SUBAGENTS_UNAVAILABLE` instead of invoking those tools
- `maintagent` watchdog tools only when `ops` mode is enabled
- `main` OpenMind bridge probe
- `maintagent -> main` communication in `ops` mode by injecting a unique `VERIFY_PING_*` token and confirming it lands in the `main` transcript

Latest passing artifact bundle from this pass:

- `docs/reviews/openclaw_openmind_verifier_lean_20260309.md`
- `docs/reviews/openclaw_openmind_verifier_ops_20260309.md`

Public review reproducibility also changed in this round:

- `ops/sync_review_repo.py` now mirrors `openclaw_extensions/` into the public review branch
- the public branch therefore includes the exact plugin sources referenced by `scripts/rebuild_openclaw_openmind_stack.py`

Additional live validation completed after the topology simplification landed:

- `ops` mode live verification:
  - rebuild command: `./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw --topology ops --prune-volatile`
  - verifier snapshot:
    - `docs/reviews/openclaw_openmind_verifier_ops_20260309.md`
  - result:
    - `main + maintagent` topology recognized
    - `main_sessions_spawn_negative_probe = true`
    - `main_subagents_negative_probe = true`
    - `maintagent_probe_reply = SENT`
    - `maintagent_to_main_transcript = true`
    - `main_latest_transcript_token_matches = true`

- final restore to default `lean` mode:
  - rebuild command: `./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw --topology lean --prune-volatile`
  - verifier snapshot:
    - `docs/reviews/openclaw_openmind_verifier_lean_20260309.md`
  - final host state left in `lean`

## Outcome

The rebuilt baseline is now aligned with the intended product shape:

- upstream OpenClaw stays the shell/runtime
- OpenMind is the cognition substrate
- `main` is the human-facing surface
- default topology is now `lean`
- `maintagent` is the only optional persistent secondary lane
- `main` now has live-proven OpenMind tool access
- `maintagent` no longer trips the permissive-plugin policy warning

## Remaining gap

Two non-blocking findings remain:

1. `gateway.trusted_proxies_missing`
   - acceptable while the gateway remains loopback-only
2. `fs.state_dir.symlink`
   - expected on this host because the managed OpenClaw home is a symlinked operational path
