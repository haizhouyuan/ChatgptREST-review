# OpenClaw + OpenMind Best-Practice Blueprint

Date: 2026-03-09

## Purpose

Define the production baseline for a single-user OpenClaw shell that uses OpenMind as its cognition substrate without re-growing a private OpenClaw fork.

This blueprint is based on:

- current live host validation on YogaS2
- latest upstream OpenClaw stable runtime (`v2026.3.7`)
- current official heartbeat / tool-policy / optional-plugin / community-plugin guidance
- the actual capabilities already built in this repository

## Executive Position

The correct model is:

- upstream OpenClaw is the shell/runtime/control plane
- OpenMind is the durable cognition substrate
- integration happens through plugins and explicit service boundaries
- the rebuilt baseline is defined by repo-owned config, not by inherited local plugin drift
- role agents exist to serve `main`, not to become independent product surfaces
- public/prod review context is fail-closed on `/v2/advisor/*` except the documented `/v2/advisor/health` exemption

The wrong model is:

- a long-lived private OpenClaw fork with shell-core patches for memory/intake
- uncontrolled plugin sprawl from a “plugin market” mentality
- treating every role agent as a first-class human-facing assistant

## What Official Guidance Actually Implies

### 1. Heartbeats are first-class and should stay cheap

Current upstream guidance is explicit:

- if any agent defines a heartbeat, only those agents run heartbeats
- `target: "none"` is the right choice for internal upkeep
- `HEARTBEAT.md` should stay small
- heartbeats run real agent turns and therefore should use a model/configuration that is cheap enough and reliable enough for repeated runs

Implication for this stack:

- internal watchdog agents should be quiet
- heartbeat lanes must be reliable under normal host load
- if a cheaper model is flaky on this host, reliability wins over theoretical savings

### 2. Tool policy should stay additive for optional plugin tools

Current official docs still describe `tools.profile` as the base allowlist and warn that plugin-only `tools.allow` entries do not replace core tools. Separate official optional-plugin docs now explicitly recommend additive `alsoAllow` for tools like Lobster.

Implication:

- keep `tools.profile` as the base surface
- use per-agent additive plugin opt-in for OpenMind bridge tools
- do not rely on plugin-only restrictive allowlists to define safe production behavior

For this host, the live-good pattern is:

- `main` in `lean`: `profile=coding` + additive OpenMind tools, with explicit deny for `sessions_send`, `sessions_list`, `sessions_history`, `sessions_spawn`, `subagents`, automation, UI, and image
- `main` in `ops`: `profile=coding` + additive OpenMind tools plus watchdog communication tools
- `maintagent`: `profile=minimal` + additive `sessions_send` / `sessions_list` only
- `main` does not keep a live `subagents.allowAgents` config in `ops`; watchdog coordination is via `sessions_send`, not subagent spawning

This is stricter and more stable than `full + deny`.

### 3. Community plugin surface is still thin

The current official community-plugin surface is not broad enough to justify a “load everything popular” strategy. At the time of this blueprint, the official page is effectively a single concrete entry, not a broad mature marketplace.

Implication:

- the right approach is a conservative plugin set tied to concrete user needs
- extra plugins should be added only when they fill a real gap that core/bundled + OpenMind plugins do not already cover

## Independent Conclusions

### 1. The plugin market is not the center of gravity

For this system, the most important plugins are not “popular marketplace add-ons”. They are:

- core runtime plugins
- channel plugins that match the user’s real messaging surface
- OpenMind bridge plugins that turn OpenClaw into a cognitive shell

That means the target set is intentionally small.

### 2. OpenMind must own cognition, not compete with shell-local memory plugins

OpenClaw already has other possible memory directions, including community memory plugins and official storage-oriented plugins.

For this deployment, those should not become the primary memory slot because they would compete with:

- `openmind-memory`
- `openmind-graph`
- `openmind-advisor`
- `openmind-telemetry`

The shell should not have two durable cognition centers.

### 3. `main` is the product surface

`main` should be the only default long-lived user-facing agent.

The old internal role lanes (`planning`, `research-orch`, `openclaw-orch`) were useful experiments, but they are not the current best-practice baseline because those capabilities now mostly live in OpenMind, skills, or ACP/on-demand workflows.

The architecture should keep that asymmetry explicit:

- `main` is user-facing and does real work
- `maintagent` is optional watchdog infrastructure, not a general specialist lane
- ACP harness lanes are execution backends, not human-facing assistants

## Recommended Production Baseline

### Runtime

- OpenClaw baseline: latest upstream stable runtime
- State dir: `~/.openclaw`
- ChatgptREST / OpenMind integrated host API: `http://127.0.0.1:18711`
- ChatgptREST API remains the canonical integrated host endpoint for:
  - `/v1/*`
  - `/v2/advisor/*`
  - OpenMind bridge plugins
- Public/prod baseline requires:
  - `OPENMIND_AUTH_MODE=strict`
  - `OPENMIND_API_KEY` configured on the integrated host
  - public evidence showing unauthenticated `/v2/advisor/ask` is rejected

If a separate advisor-only dev process is launched on another port, that is an override, not the baseline.

### Agent Topology

- `main`
  - primary human-facing assistant
  - default memory slot consumer
  - primary workbench for coding / orchestration / reports / research escalation
  - tool baseline: `coding` + additive OpenMind tools
  - in `lean`, explicit deny also covers `sessions_send`, `sessions_list`, and `sessions_history`
  - explicit deny: `sessions_spawn`, `subagents`, `group:automation`, `group:ui`, `image`
  - no configured `subagents.allowAgents` in the supported baseline
  - heartbeat enabled, quiet

- `maintagent`
  - optional watchdog lane
  - probes gateway/OpenMind/channel readiness
  - escalates only on actionable degradation
  - tool baseline: `minimal` + additive `sessions_send` / `sessions_list`
  - no repo skill baseline in the supported topology
  - should use the most reliable provider on the host, not merely the theoretically cheapest

Recommended deployment modes:

- `lean`
  - `main` only
  - default baseline for day-to-day use
- `ops`
  - `main + maintagent`
  - unattended / sleep / watchdog mode

### Communication Model

- `lean`
  - no persistent inter-agent topology
  - `tools.agentToAgent.enabled = false`

- `ops`
  - `main` may coordinate only with `maintagent`
  - use:
    - `sessions_send` for concise watchdog coordination
    - `sessions_list` / `sessions_history` for visibility
- internal escalation to `main` should use the stable session key `agent:main:main`
- in `ops`, this single-user baseline should keep:
  - `tools.agentToAgent.enabled = true`
  - `tools.agentToAgent.allow = [main, maintagent]`
  - `tools.sessions.visibility = "all"`

- do not widen `allowAgents` casually
- do not reintroduce old role-agent sessions as independent, user-facing long-lived inboxes

## Plugin Portfolio

### Keep enabled now

#### Core runtime

- `acpx`
  - ACP runtime bridge
  - required for serious coding/runtime delegation

- `diffs`
  - high-value read-only diff visualization/review tool

#### Auth/provider support

- `google-gemini-cli-auth`
  - needed for Gemini-backed on-demand work and provider availability

#### Channels

- `feishu`
  - primary real business messaging surface

- `dingtalk`
  - secondary but real business surface

#### OpenMind bridge set

- `openmind-memory`
  - canonical shell memory slot

- `openmind-graph`
  - graph retrieval bridge

- `openmind-advisor`
  - slow-path cognition / routed advisor bridge

- `openmind-telemetry`
  - execution feedback into EvoMap/OpenMind

### Optional later, but not required for this baseline

- `diagnostics-otel`
  - only if OpenTelemetry export becomes a separate ops requirement
  - currently redundant with Langfuse + OpenMind telemetry for this host

- `lobster`
  - the official optional deterministic workflow tool
  - worth adding only when resumable approval workflows become a real shell-level need

- `llm-task`
  - official optional structured LLM step
  - useful if shell-internal structured LLM microtasks become common
  - not necessary for the current OpenMind-led cognition path

- `device-pair`
  - useful if remote/device pairing becomes part of the real workflow
  - not necessary for the current local integrated host

### Do not enable for this deployment

- extra bundled channel plugins that the user does not actually use
- competing memory plugins (for example alternate durable memory centers)
- community plugins whose primary value overlaps OpenMind memory/cognition
- `env-http-proxy` in the supported baseline
  - if a host-specific proxy workaround is ever needed again, treat it as a local override, not part of the production baseline

Independent recommendation:

- do not install a second durable-memory plugin “because it is popular”
- do not install channel plugins for channels that are not active business surfaces

## Channel Strategy

### Feishu

- main Feishu account routes to `main`
- no secondary role-agent Feishu inboxes in the default baseline
- DM policy stays conservative (`pairing` / explicit allow strategy)
- heartbeat delivery target remains `none`

### Dingtalk

- keep routed to `main`
- treat it as a secondary but supported business surface

### No broad multi-channel expansion yet

Even though OpenClaw supports many channels, expanding channel count now would increase:

- auth burden
- webhook/WS surface area
- routing complexity
- heartbeat noise

without improving the core user outcome.

## OpenMind Integration Rules

### Memory

- `plugins.slots.memory = openmind-memory`
- `main` should treat OpenMind as the canonical memory substrate
- do not add a parallel shell-local durable memory center

### Graph

- `openmind-graph` remains tool-exposed
- repo graph is an augmentation layer, not an always-on hot-path dependency

### Advisor

- `openmind-advisor` is the slow-path cognition bridge
- it should stay behind deliberate tool use / escalation, not become the default response path for every small shell interaction

### Telemetry

- `openmind-telemetry` should stay enabled
- shell activity should keep feeding OpenMind/EvoMap
- gateway service should load `~/.config/chatgptrest/chatgptrest.env` so telemetry inherits `OPENMIND_API_KEY`
- telemetry should remain secondary to correctness; do not break agent turns for telemetry failures

## Heartbeat Rules

- `target: none`
- `lightContext: true`
- `HEARTBEAT.md` stays tiny and role-specific
- no document/wiki authoring in heartbeats
- no broad exploratory work in heartbeats
- `maintagent` should prefer `session_status` and `sessions_list` over shell/`exec`

## Validation Standard

### Public review acceptance

“Production usable” for the public mirrored package means all of the following are proven by the review-safe branch evidence:

1. Active topology is only the intended `lean` or `ops` set
2. Plugin trust/provenance is clean in `openclaw plugins doctor`
3. `main` returns a live READY/OpenMind probe and the OpenMind bridge tools are callable
4. In `ops`, watchdog escalation succeeds via `sessions_send` against `agent:main:main`
5. No stale private-fork shell-core path is required for normal operation
6. Controlled access is explicitly proven:
   - loopback gateway bind
   - explicit trusted proxies
   - token mode with token present
   - `allowTailscale = false`
7. Security audit is reduced to the known local residuals only

### Extended live-host checks

The following still matter operationally, but they are host-specific validation items rather than required public-branch acceptance criteria:

1. Codex auth sync is consistent across live agent stores
2. Feishu plugin tools register and WS startup completes

## What Not To Do Next

- do not go back to the old private OpenClaw fork as the mainline
- do not start loading extra plugins just because they exist
- do not split cognition across OpenMind and another durable memory plugin
- do not widen watchdog permissions before there is a concrete operational need

## Next Implementation Gaps

1. Keep Feishu doc/wiki/chat/drive/perm/scopes disabled in the single-user baseline unless a future variant explicitly re-opens that surface.
2. Package the resulting blueprint + live evidence for dual-model review.

## Sources

- OpenClaw Tools docs: `https://docs.openclaw.ai/tools`
- OpenClaw Cron vs Heartbeat: `https://docs.openclaw.ai/automation/cron-vs-heartbeat`
- OpenClaw Lobster docs: `https://docs.openclaw.ai/tools/lobster`
- OpenClaw community plugins page: `https://docs.openclaw.ai/plugins/community`
- OpenClaw latest stable release: `https://github.com/openclaw/openclaw/releases`
- live host validation on YogaS2 with public review-safe verifier snapshots under `docs/reviews/openclaw_openmind_verifier_{lean,ops}_20260309.md`
