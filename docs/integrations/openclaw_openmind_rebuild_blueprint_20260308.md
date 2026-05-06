# OpenClaw + OpenMind Rebuild Blueprint

Date: 2026-03-08

## Goal

Replace the current heavily diverged OpenClaw fork + stale state sprawl with:

- latest upstream OpenClaw as the runtime baseline
- preserved auth/channel/device identity assets
- OpenMind integrated through plugins, not shell-core patching
- a small role-agent topology around one primary user-facing agent
- reproducible migration and rollback

## Why Rebuild Instead of Patching In Place

The current local OpenClaw setup is not a stable base:

- repo `/vol1/1000/projects/openclaw` is a dirty feature branch
- local fork is `17` commits ahead but `7827` commits behind `upstream/main`
- `~/.openclaw/openclaw.json` references old custom plugin trees and many historical agents
- `~/.openclaw` contains quarantine snapshots, legacy workspaces, deleted session tombstones, and stale lock artifacts

This is no longer a "tune the config" problem. It is a state-shape problem.

## Official / Current Guidance Applied

The rebuild is aligned to current OpenClaw guidance:

- onboarding / migration entrypoint is `openclaw onboard` + `openclaw doctor`
- per-agent auth lives in `~/.openclaw/agents/<agentId>/agent/auth-profiles.json`
- DM channels should default to `pairing`
- plugins are installed/loaded via plugin manifests and `plugins.entries` / `plugins.slots`
- local development plugins should be linked with `openclaw plugins install --link <path>`, not hand-copied into `~/.openclaw/extensions`
- external coding harnesses should use `ACP + acpx`, not shell-core hacks or old custom intake plugins
- agent coordination should use `sessions_spawn`, `sessions_send`, `tools.agentToAgent`, per-agent `subagents.allowAgents`, and ACP runtime sessions where appropriate
- heartbeat is a first-class mechanism; cron is for explicit scheduled jobs

## Preserve vs Rebuild

### Preserve

- `~/.openclaw/agents/*/agent/auth-profiles.json`
- `~/.openclaw/secrets/*`
- `~/.openclaw/credentials/feishu-*`
- `~/.openclaw/identity/*`
- `~/.openclaw/devices/*`
- gateway auth token and loopback binding
- current Dingtalk install metadata

### Rebuild

- `openclaw.json`
- agent topology
- channel bindings
- plugin wiring
- OpenMind integration config
- heartbeat files and prompts
- selected workspaces

### Do Not Carry Forward

- old fork-specific plugin load paths:
  - `kb-core`
  - `intake-core`
  - custom `gemini-cli`
- `feishu-intake` as the main Feishu route target
- historical agent sprawl unrelated to the new control plane
- direct shell-core customization as the primary extension strategy

## Target Runtime Baseline

- OpenClaw runtime baseline:
  - latest upstream stable (`v2026.3.7` at time of rebuild)
  - clean upstream checkout:
    `/vol1/1000/projects/_worktrees/openclaw-upstream-main-latest-20260308_093548`
- OpenMind backend:
  - ChatgptREST / OpenMind v3 at `http://127.0.0.1:18711` on the integrated host
  - if you run a dedicated advisor-only process elsewhere, override the plugin endpoint explicitly

## Target Agent Topology

### Primary

- `main`
  - primary user-facing assistant
  - default agent for main Feishu account
  - full tool profile
  - OpenMind memory slot active
  - can dispatch to role agents
  - heartbeat enabled

### Role Agents

- `planning`
  - long-form planning / report / coordination role
  - default target for current Dingtalk route
  - heartbeat enabled but quiet (`target: none`)

- `research-orch`
  - research / synthesis role
  - bound to Feishu `research` account if retained
  - may use OpenMind advisor/graph tools

- `openclaw-orch`
  - coding / integration role
  - workspace pinned to the clean upstream OpenClaw checkout
  - delegates to ACP harness sessions when coding work belongs in Codex / Gemini / Claude Code

- `maintagent`
  - health / gateway / OpenMind guard role
  - heartbeat enabled
  - should escalate to `main` only on actionable issues

### ACP Harness Targets

- `codex`
- `gemini`
- `claude`

These are not separate OpenClaw route owners. They are ACP harness ids exposed through `acpx`, with `main` / `openclaw-orch` using them on demand.

## Channel Strategy

### Feishu

- keep `dmPolicy: pairing`
- route `feishu/main` to `main`
- optionally retain `feishu/research` -> `research-orch`
- do not keep `feishu/main` -> `feishu-intake` as the primary production route

### Dingtalk

- preserve current Dingtalk account material
- keep current default binding to `planning`
- treat Dingtalk as compatible-but-secondary until revalidated on the rebuilt stack

## OpenMind Integration Strategy

OpenMind must stay plugin-driven, not OpenClaw-core-driven.

Bundled upstream plugins such as `feishu`, `acpx`, `diffs`, and `google-gemini-cli-auth`
should be enabled from the upstream runtime bundle. Do not re-copy them into
`~/.openclaw/extensions`, or you recreate duplicate-plugin drift.

### Active plugins

- `openmind-memory`
  - active `plugins.slots.memory`
  - auto recall + auto capture

- `openmind-telemetry`
  - enabled
  - emits OpenClaw lifecycle/tool telemetry into OpenMind

- `openmind-graph`
  - enabled
  - tool exposure for repo/personal graph retrieval

- `openmind-advisor`
  - enabled
  - slow-path research / report / funnel bridge

- `acpx`
  - enabled
  - provides ACP runtime bridge to Codex / Gemini / Claude Code

- `diffs`
  - enabled
  - safe high-value coding review / diff visualization plugin

### Explicitly dropped old custom plugin paths

- `/vol1/1000/projects/openclaw/extensions/kb-core`
- `/vol1/1000/projects/openclaw/extensions/intake-core`
- `/vol1/1000/projects/openclaw/extensions/gemini-cli`

## Heartbeat Design

Use heartbeat for internal upkeep, not chat spam.

- `main`
  - `every: 30m`
  - `target: none`
  - `lightContext: true`
  - purpose: review pending follow-ups and use role agents when needed

- `planning`
  - `every: 2h`
  - `target: none`
  - purpose: review planning backlog / writing follow-ups

- `maintagent`
  - `every: 1h`
  - `target: none`
  - purpose: check OpenClaw gateway / OpenMind health and notify `main` only on actionable degradation

## Communication Model

- cross-agent communication is enabled via `tools.agentToAgent`
- orchestration uses:
  - `sessions_spawn`
  - `sessions_send`
  - per-agent `subagents.allowAgents`
- coding-harness execution uses:
  - `acp.enabled=true`
  - `acp.backend=acpx`
  - `acp.allowedAgents=[codex, gemini, claude]`
- keep cross-agent allowlist small and explicit

## Migration Phases

1. Backup essential state only
2. Generate a new `openclaw.json`
3. Preserve / sync auth-profiles for selected agents
4. Install or link OpenMind plugins
5. Prepare role workspaces + `HEARTBEAT.md`
6. Validate config
7. Start runtime and test:
   - config validation
   - plugin discovery
   - gateway health
   - Feishu account resolution
   - selected OpenMind tool paths

## Success Criteria

- latest upstream OpenClaw baseline is the active runtime
- `main` routes through OpenClaw and uses OpenMind memory successfully
- Feishu main account reaches `main`
- role agents can be listed, spawned, and messaged from `main`
- ACP doctor succeeds and Codex / Gemini / Claude ACP sessions can be spawned
- `maintagent` heartbeat runs without external spam
- OpenMind plugins are loaded and memory slot is active
- old half-finished agents/plugins are no longer part of live routing

## Non-Goals

- reviving the old fork as trunk
- carrying over every historical agent/workflow
- preserving stale session history as live runtime state
- reintroducing shell-core customizations when a plugin or config boundary is sufficient
