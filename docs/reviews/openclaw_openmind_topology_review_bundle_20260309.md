# OpenClaw + OpenMind Lean/Ops Topology Review Bundle

Date: 2026-03-09
Repo: `ChatgptREST`
Source commit under review: see `REVIEW_SOURCE.json` in the synced public review branch
Review repo: `https://github.com/haizhouyuan/ChatgptREST-review`
Review branch: supplied by the review prompt for the current synced mirror branch

## Goal and scope

Review the current OpenClaw + OpenMind deployment after collapsing the old five-agent persistent topology into two supported modes:

- `lean`: `main` only
- `ops`: `main + maintagent`

The review target is not the older "service-lane mesh" anymore. The question is whether this simplified topology is now the correct production baseline for a single-user OpenClaw shell backed by OpenMind.

## Sources used for this bundle

- `scripts/rebuild_openclaw_openmind_stack.py`
- `ops/verify_openclaw_openmind_stack.py`
- `ops/sync_review_repo.py`
- `ops/nginx_openmind.conf`
- `openclaw_extensions/openmind-memory/*`
- `openclaw_extensions/openmind-graph/*`
- `openclaw_extensions/openmind-advisor/*`
- `openclaw_extensions/openmind-telemetry/*`
- `docs/integrations/openclaw_openmind_best_practice_blueprint_20260309.md`
- `docs/dev_log/2026-03-09_openclaw_openmind_best_practice_rebuild.md`
- public code mirror branch:
  - use the current `review-YYYYMMDD-HHMMSS` branch emitted by `python3 ops/sync_review_repo.py --sync --push`
  - mirror now includes `openclaw_extensions/` and `skills-src/` so repo-owned plugin and skill surfaces are reproducible from branch contents
  - the same synced content is also mirrored to the review repo default import branch so Gemini code import can read the latest package from the repo root
- public provenance / evidence index expected on that same review branch:
  - `REVIEW_SOURCE.json`
  - `ops/nginx_openmind.conf`
  - `openclaw_extensions/openmind-memory/*`
  - `openclaw_extensions/openmind-graph/*`
  - `openclaw_extensions/openmind-advisor/*`
  - `openclaw_extensions/openmind-telemetry/*`
- review-safe verifier evidence copied from local artifacts:
  - lean baseline proof:
    - `docs/reviews/openclaw_openmind_verifier_lean_20260309.md`
    - `docs/reviews/openclaw_openmind_verifier_lean_20260309.json`
  - ops mode proof:
    - `docs/reviews/openclaw_openmind_verifier_ops_20260309.md`
    - `docs/reviews/openclaw_openmind_verifier_ops_20260309.json`
- public raw evidence mirror for reproducibility:
  - `docs/reviews/evidence/openclaw_openmind/B1/openclaw_openmind_config_lean_20260309.json`
  - `docs/reviews/evidence/openclaw_openmind/B1/openclaw_openmind_config_ops_20260309.json`
  - `docs/reviews/evidence/openclaw_openmind/B1/openclaw_openmind_transcript_lean_20260309.json`
  - `docs/reviews/evidence/openclaw_openmind/B1/openclaw_openmind_transcript_ops_20260309.json`
  - `docs/reviews/evidence/openclaw_openmind/B2/openmind_advisor_auth_lean_20260309.json`
  - `docs/reviews/evidence/openclaw_openmind/B2/openmind_advisor_auth_ops_20260309.json`
  - `artifacts/` remains excluded by `ops/sync_review_repo.py`; public review must use these mirrored review-safe evidence files instead of local artifact paths

## Current baseline architecture

- OpenClaw is the shell/runtime/control plane.
- ChatgptREST/OpenMind on `http://127.0.0.1:18711` is the cognition substrate.
- The review-safe nginx ingress sample points at the same integrated host endpoint `http://127.0.0.1:18711`.
- Integration happens through plugins and service boundaries, not shell-core fork patches.
- `main` is the only default long-lived user-facing agent.
- `maintagent` exists only as an optional watchdog lane in `ops` mode.
- `planning`, `research-orch`, and `openclaw-orch` are no longer part of the persistent baseline.
- review evidence now proves the public package from config to runtime:
  - repo-owned skill surface only
  - repo-owned skill wrapper uses repo-relative root discovery by default
  - no host-local plugin load paths
  - loopback gateway with explicit trusted proxies
  - raw verifier JSON mirrored into `docs/reviews/*.json`
  - redacted config snapshots and transcript excerpts mirrored into `docs/reviews/evidence/openclaw_openmind/...`
  - unauthenticated `/v2/advisor/ask` rejection proven in public auth evidence

## Supported topologies

### `lean` (default)

- active agents: `main`
- `tools.agentToAgent.enabled = false`
- `main.tools.profile = coding`
- `main` additive tools:
  - `openmind_memory_status`
  - `openmind_memory_recall`
  - `openmind_memory_capture`
  - `openmind_graph_query`
  - `openmind_advisor_ask`
- `main` explicit deny:
  - `group:automation`
  - `group:ui`
  - `image`
  - `sessions_send`
  - `sessions_list`
  - `sessions_history`
  - `sessions_spawn`
  - `subagents`

### `ops` (optional unattended/watchdog mode)

- active agents: `main`, `maintagent`
- `tools.agentToAgent.enabled = true`
- `tools.agentToAgent.allow = [main, maintagent]`
- `main.tools.profile = coding`
- `main` additive tools:
  - `sessions_send`
  - `sessions_list`
  - `sessions_history`
  - all OpenMind tools listed above
- `maintagent.tools.profile = minimal`
- `maintagent` additive tools:
  - `sessions_send`
  - `sessions_list`
- `maintagent` carries no repo skill baseline; it is a minimal watchdog lane, not a background task worker

## Enabled plugin set

Enabled now:

- `acpx`
- `diffs`
- `feishu`
- `google-gemini-cli-auth`
- `dingtalk`
- `openmind-advisor`
- `openmind-graph`
- `openmind-memory`
- `openmind-telemetry`

Important constraints:

- Feishu doc/wiki/chat/drive/perm/scopes are disabled by default.
- There is no parallel durable-memory plugin competing with `openmind-memory`.
- Stable runtime behavior on this host is `profile + alsoAllow`, not restrictive allowlist-only policy.

## What changed in this round

1. Removed the persistent role-agent topology (`planning`, `research-orch`, `openclaw-orch`) from the rebuilt baseline.
2. Made `main` the real workbench instead of a thin messaging dispatcher.
3. Kept `maintagent` only as an optional watchdog lane.
4. Updated the rebuild script so topology is explicit:
   - `--topology lean`
   - `--topology ops`
5. Updated the live verifier so it validates:
   - topology recognition
   - absence of legacy role agents
   - repo-only `skills.load.extraDirs` and empty `skills.allowBundled`
   - repo-public agent skills (`chatgptrest-call` only)
   - no host-local plugin `load.paths`
   - `env-http-proxy` removed from the enabled plugin baseline
   - loopback gateway posture with explicit `trustedProxies`
   - unauthenticated `/v2/advisor/ask` rejection on the integrated host
   - OpenMind tool availability on `main`
   - no effective `sessions_spawn` or `subagents` exposure on `main` after profile expansion
   - negative runtime probes proving `main` cannot actually invoke `sessions_spawn` or `subagents`
   - `maintagent -> main` communication only in `ops` mode
6. Left the host in `lean` mode after validating both topologies.
7. Removed arbitrary plugin state inheritance from the rebuild baseline:
   - plugin `allow` is now deterministic from the baseline entries
   - random preexisting plugin `load.paths` are no longer carried forward
   - review-safe verifier output now records `plugins_allow`, `plugins_load_paths`, and `gateway_config`
8. Removed host-specific root assumptions from the public `chatgptrest-call` skill wrapper:
   - default ChatgptREST root is discovered from the script location
   - interval state defaults under the discovered repo root
   - if the skill is copied outside the repository, `CHATGPTREST_ROOT` can override discovery
9. Published review-safe raw evidence so the public mirror can reproduce the baseline claims without local `artifacts/` access:
   - raw verifier JSON
   - redacted `openclaw.json` snapshots
   - transcript excerpts for probe rounds
   - advisor auth probe results

## Live validation summary

### Lean mode

Artifact:

- `docs/reviews/openclaw_openmind_verifier_lean_20260309.md`
- `docs/reviews/openclaw_openmind_verifier_lean_20260309.json`
- `docs/reviews/evidence/openclaw_openmind/B1/openclaw_openmind_config_lean_20260309.json`
- `docs/reviews/evidence/openclaw_openmind/B1/openclaw_openmind_transcript_lean_20260309.json`
- `docs/reviews/evidence/openclaw_openmind/B2/openmind_advisor_auth_lean_20260309.json`

Key results:

- `topology = lean`
- `heartbeat_agent_count = expected=1`
- `legacy_role_agents_removed = true`
- `main_profile_coding = true`
- `main_has_openmind_tools = true`
- `skills_repo_only = true`
- `main_skills_repo_public = true`
- `main_no_sessions_spawn = true`
- `main_no_subagents_tool = true`
- `plugins_no_local_load_paths = true`
- `plugins_env_http_proxy_disabled = true`
- `gateway_bind_loopback = true`
- `gateway_trusted_proxies_configured = true`
- `gateway_auth_token_mode = true`
- `advisor_unauth_ingress_rejected = true`
- `main_sessions_spawn_negative_probe = true`
- `main_subagents_negative_probe = true`
- `lean_agent_to_agent_disabled = true`
- `lean_maintagent_absent = true`
- `openmind_tool_round = true`

### Ops mode

Artifact:

- `docs/reviews/openclaw_openmind_verifier_ops_20260309.md`
- `docs/reviews/openclaw_openmind_verifier_ops_20260309.json`
- `docs/reviews/evidence/openclaw_openmind/B1/openclaw_openmind_config_ops_20260309.json`
- `docs/reviews/evidence/openclaw_openmind/B1/openclaw_openmind_transcript_ops_20260309.json`
- `docs/reviews/evidence/openclaw_openmind/B2/openmind_advisor_auth_ops_20260309.json`

Key results:

- `topology = ops`
- `heartbeat_agent_count = expected=2`
- `ops_main_has_watchdog_comm_tools = true`
- `skills_repo_only = true`
- `main_skills_repo_public = true`
- `maint_skills_repo_public = true`
- `maint_skills_absent = true`
- `maintagent_profile_minimal = true`
- `maintagent_tools_hardened = true`
- `ops_agent_to_agent_allow = [main, maintagent]`
- `plugins_no_local_load_paths = true`
- `plugins_env_http_proxy_disabled = true`
- `gateway_bind_loopback = true`
- `gateway_trusted_proxies_configured = true`
- `gateway_auth_token_mode = true`
- `advisor_unauth_ingress_rejected = true`
- `main_sessions_spawn_negative_probe = true`
- `main_subagents_negative_probe = true`
- `maintagent_probe_reply = SENT`
- `maintagent_to_main_transcript = true`
- `main_latest_transcript_token_matches = true`

### Security summary

Both lean and ops live verifiers report:

- `critical=0 warn=0 info=1`

Remaining warnings/findings are non-blocking for loopback single-user review:

1. `summary.attack_surface`
   - expected informational attack-surface summary in the security audit output

## Review request

Please review this simplified baseline and answer:

1. Is collapsing the persistent topology to `lean` default + `ops` optional the right production shape, or is there still a missing persistent lane that should exist?
2. Is `main` now overpowered or still underpowered as a real workbench in `lean` mode?
3. Is `maintagent` sufficiently constrained in `ops` mode, or does it still have unnecessary access?
4. Is there any blocker or unproven assumption that still makes it premature to call this baseline production-usable?
5. If you see issues, separate:
   - blocking findings
   - non-blocking hardening suggestions

## Important context

- This is a single-user personal system, not a hostile shared multi-tenant deployment.
- The old half-finished OpenClaw custom/fork workflow is intentionally being retired.
- Most cognition/memory/business orchestration now lives in OpenMind/ChatgptREST, not in OpenClaw-internal specialist lanes.
