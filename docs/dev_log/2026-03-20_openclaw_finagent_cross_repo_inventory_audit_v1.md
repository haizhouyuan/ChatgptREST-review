# 2026-03-20 OpenClaw / Finagent Cross-Repo Inventory Audit v1

## Scope

This audit extends the earlier full-repo audit of `ChatgptREST` into two
sibling repositories that materially shape the current system:

1. `openclaw`
2. `finagent`

The goal is not to re-document every file. The goal is to answer:

- what each repo actually is
- what its runtime center of gravity is
- how much real code vs docs/runtime state it contains
- what the durable state looks like
- what is active, transitional, or residue
- how it relates back to `ChatgptREST`

Method:

- repository structure audit
- manifest and README audit
- code line-count / file-count inventory
- targeted module and docs audit
- live SQLite snapshot inspection where relevant
- GitNexus repo stats inspection

Important constraint:

- this audit is read-only
- neither sibling repo was modified
- both repos currently have dirty worktrees, so this document treats them as
  active development surfaces rather than stable release baselines

## Executive Summary

The two repos play very different roles.

### OpenClaw

`openclaw` is not just a shell or bot frontend. It is a **large TypeScript
assistant operating system / gateway runtime** with:

- a typed WebSocket gateway
- multi-channel messaging integration
- agent runtime and session control
- device/node orchestration
- memory indexing
- browser/canvas/tooling
- coding-team / multi-agent workflow substrate
- plugin and extension ecosystem
- UI and mobile/desktop companion surfaces

It is much larger and more mature than a simple ingress layer.

### Finagent

`finagent` is not a daemon platform. It is a **local-first investment research
workbench and thesis operating system**, centered on:

- a single Python package
- a SQLite domain model
- a very large CLI command surface
- view builders and workbench outputs
- event-mining / sentinel workflows
- artifact-driven research state
- a huge accompanying documentation and run archive

It is much smaller in code than `openclaw`, but far denser in domain-specific
workflow semantics.

### Cross-repo conclusion

Together with `ChatgptREST`, the current three-repo shape looks like this:

- `openclaw` = always-on gateway / session runtime / client and channel OS
- `ChatgptREST` = web execution substrate + OpenMind runtime host + cognitive APIs
- `finagent` = vertical investment-research operating system

That means the system is not one monolith. It is already a **three-repo
federation**, but the boundaries are still informal enough to create overlap.

## Git and Repo Status Snapshot

### OpenClaw

Path:

- `/vol1/1000/projects/openclaw`

Git status at audit time:

- branch: `feature/ui-evomap-session-manager`
- ahead of upstream: `2`
- dirty tracked changes present
- many untracked docs, extensions, protocol additions, and coding-team related files

This means OpenClaw is under active feature development, not frozen.

### Finagent

Path:

- `/vol1/1000/projects/finagent`

Git status at audit time:

- branch: `main`
- ahead of upstream: `1`
- dirty due to `.gitnexus` updates and `artifacts/`

This looks more like an active working research repo with runtime residue than a
clean product release branch.

## GitNexus Snapshot

### OpenClaw

GitNexus stats:

- files = `5055`
- nodes = `21849`
- edges = `61058`
- communities = `1403`
- processes = `300`

### Finagent

GitNexus stats:

- files = `597`
- nodes = `1690`
- edges = `4552`
- communities = `88`
- processes = `99`

Interpretation:

- OpenClaw is a large platform codebase
- Finagent is much smaller as code, but still structurally non-trivial

## 1. OpenClaw Inventory

### What OpenClaw actually is

The repo itself defines OpenClaw as a personal AI assistant with a gateway as
control plane, not as a thin client. That is consistent with the code.

Manifest and docs show:

- Node monorepo
- runtime: `Node >= 22`
- package manager: `pnpm`
- typed protocol generation
- UI build
- apps for Android/iOS/macOS
- many extensions
- many channels

The gateway architecture doc is unambiguous:

- one long-lived Gateway owns messaging surfaces
- clients and nodes connect over WebSocket
- the Gateway is the source of truth for session state
- WebChat, mac app, CLI, and nodes all ride the same control plane

Key sources:

- [package.json](/vol1/1000/projects/openclaw/package.json)
- [README.md](/vol1/1000/projects/openclaw/README.md)
- [architecture.md](/vol1/1000/projects/openclaw/docs/concepts/architecture.md)
- [session.md](/vol1/1000/projects/openclaw/docs/concepts/session.md)
- [queue.md](/vol1/1000/projects/openclaw/docs/concepts/queue.md)

### Code size and shape

OpenClaw code-focused inventory excluding `.worktrees`, `node_modules`, and
`dist` noise:

| Root | Files | Lines |
|---|---:|---:|
| `src` | 2756 | 511088 |
| `extensions` | 587 | 107064 |
| `ui` | 172 | 49430 |
| `scripts` | 81 | 11261 |
| `apps` | 14 | 1511 |
| `skills` | 62 | 6546 |
| `docs` | 713 | 190607 |

Interpretation:

- `src` alone is already a major platform codebase
- extensions are not incidental; they are a second large code surface
- docs are enormous, which usually indicates a mature, externally facing platform

### Core subsystem map

OpenClaw `src/` is broad and intentional rather than chaotic. Major directories
include:

- `src/gateway`
- `src/agents`
- `src/channels`
- `src/memory`
- `src/browser`
- `src/canvas-host`
- `src/cron`
- `src/config`
- `src/providers`
- `src/routing`
- `src/sessions`
- `src/web`
- `src/acp`
- `src/evomap`

This is enough to say clearly:

OpenClaw is a **runtime platform**, not just a transport shell.

### Protocol and control surface

The gateway method list currently exposes:

- `base_methods = 90`
- `events = 19`
- plus channel plugin methods layered on top

That is already a large typed control surface.

Notable gateway methods include:

- config
- exec approvals
- wizard
- models
- agents
- sessions
- node pair / device pair
- cron
- send / agent
- browser
- evomap
- `coding-team.status`
- chat history / send / abort

Key files:

- [server-methods-list.ts](/vol1/1000/projects/openclaw/src/gateway/server-methods-list.ts)
- [protocol/index.ts](/vol1/1000/projects/openclaw/src/gateway/protocol/index.ts)
- [client.ts](/vol1/1000/projects/openclaw/src/gateway/client.ts)

### Session and state model

OpenClaw does not appear to center itself on repo-local SQLite state.

From the session docs:

- gateway is the source of truth
- session store lives under `~/.openclaw/agents/<agentId>/sessions/sessions.json`
- transcripts are JSONL per session

This is important because it makes OpenClaw fundamentally different from
`ChatgptREST` and `finagent`, both of which are SQLite-heavy.

Verdict:

- OpenClaw is file/state-store centric for session truth
- not DB-centric inside the repo
- its durable state mostly lives outside the repo root

### Memory subsystem

OpenClaw includes a substantial memory indexing layer, not just a key-value
store.

`src/memory/manager.ts` shows:

- SQLite-backed memory index manager
- embedding providers
- vector / FTS hybrid search
- transcript watching
- session and workspace indexing
- batch embedding support

This is a real memory/search subsystem, but it is **OpenClaw-native memory**,
not the same thing as OpenMind memory in `ChatgptREST`.

Key file:

- [manager.ts](/vol1/1000/projects/openclaw/src/memory/manager.ts)

### Coding-team / multi-agent development layer

This matters directly for your system goals.

OpenClaw now contains a large coding-team subsystem under:

- `src/agents/coding-team/*`
- `src/agents/tools/coding-team-tool.ts`
- gateway method `coding-team.status`
- many tests around team dispatch, gates, runtime store, watchdogs, merge policy

`coding-team-tool.ts` alone shows:

- runtime store locking
- lane scheduling
- merge and codeowner gates
- branch / PR assembly
- dispatch and replay analysis

This means OpenClaw is already experimenting with an internal team-runtime /
coding-team control surface.

Key file:

- [coding-team-tool.ts](/vol1/1000/projects/openclaw/src/agents/tools/coding-team-tool.ts)

### Extensions and channel platform

OpenClaw currently has:

- `39` extension directories under `extensions/`

These include:

- channel connectors
- memory and KB cores
- intake/task cores
- auth helpers
- voice / phone / device control

This confirms that OpenClaw is designed as an extensible assistant platform,
not as a narrow client.

### Test estate

OpenClaw has a very large `.test.ts` surface:

- `.test.ts` files counted under `src` and `ui`: `1047`

The visible tests heavily cover:

- agents
- auth profiles
- memory
- sessions
- coding-team
- gateway models and live profiles
- security

That is enough to call it a heavily tested platform codebase.

### OpenClaw verdict

OpenClaw is best described as:

**assistant gateway OS + session runtime + multi-channel control plane + local
agent/tool platform**

It is not just:

- a bot shell
- a front end
- a thin ingress layer

It already contains serious runtime concepts that overlap with some of the
things being prototyped in `ChatgptREST`.

## 2. Finagent Inventory

### What Finagent actually is

The repo defines itself as:

`Local-first thesis operating system for personal investing research.`

That description matches the code and DB.

Manifest and README indicate:

- Python package
- local-first
- domain-specific research workspace
- OpenClaw / OpenMind integration intent
- artifact-centric working style
- many CLI-driven workbench outputs

Key sources:

- [pyproject.toml](/vol1/1000/projects/finagent/pyproject.toml)
- [README.md](/vol1/1000/projects/finagent/README.md)

### Code size and shape

Finagent code-focused inventory:

| Root | Files | Lines |
|---|---:|---:|
| `finagent` | 28 | 17085 |
| `scripts` | 20 | 6013 |
| `tests` | 22 | 4643 |
| `specs` | 21 | 2626 |
| `docs` | 343 | 494766 |

Interpretation:

- core code is compact compared with OpenClaw
- docs outweigh code by a large margin
- this is a research/workbench repo with a heavy document corpus

### Main code hotspots

Largest Python files:

| File | Lines | Comment |
|---|---:|---|
| `finagent/views.py` | 5076 | workbench / dashboard / report builders |
| `finagent/cli.py` | 4482 | central command surface |
| `finagent/sentinel.py` | 1796 | event-mining engine |
| `finagent/theme_report.py` | 988 | theme report generation |
| `finagent/db.py` | 751 | central schema |

Interpretation:

- the system is centered on CLI + views + DB + sentinel
- this is not an API-first service
- it is a local operating workbench

### CLI shape

`finagent/cli.py` is large because the repo is command-driven.

Measured command-surface indicators:

- `add_parser_calls = 98`
- `set_defaults_calls = 98`
- `view_build_functions = 36`

This means the CLI is not just developer tooling. It is the primary interface
to the system.

Key file:

- [cli.py](/vol1/1000/projects/finagent/finagent/cli.py)

### Database model

Finagent is strongly SQLite-backed.

`finagent/db.py` defines a large domain schema, including:

- sources
- artifacts
- claims
- entities
- themes
- theses
- thesis versions
- targets
- target cases
- timing plans
- monitors
- reviews
- claim routes
- validation cases
- source viewpoints
- operator decisions

This is not a toy schema. It is a thesis/research operating model in database
form.

Key file:

- [db.py](/vol1/1000/projects/finagent/finagent/db.py)

### Live state snapshot

Relevant repo DBs found:

- `finagent.db`
- `state/finagent.db`
- `state/finagent.sqlite`
- many run-local `state/finagent.sqlite` files under `artifacts/` and `state/smoke_runs/`
- `.hcom/hcom.db`

The actual live center of gravity is clearly:

- `state/finagent.sqlite`

Current live snapshot from `state/finagent.sqlite`:

- `sources = 50`
- `artifacts = 571`
- `claims = 5905`
- `entities = 63`
- `themes = 15`
- `theses = 14`
- `thesis_versions = 15`
- `targets = 35`
- `target_cases = 28`
- `timing_plans = 15`
- `monitors = 23`
- `reviews = 14`
- `events = 2196`
- `analysis_runs = 383`
- `claim_routes = 6207`
- `validation_cases = 136`
- `source_viewpoints = 17`

Two important contrasts:

1. `state/finagent.sqlite` is real and active
2. `state/finagent.db` has the schema but all audited core tables were `0`
3. root `finagent.db` is empty

Interpretation:

- there is one clearly active DB path
- older or alternate DB paths still exist
- storage-path convergence is not fully cleaned up

### View and workbench layer

`finagent/views.py` is the largest file because it composes the operator-facing
working views.

It includes builders for:

- integration snapshot
- weekly decision note
- thesis focus
- thesis board
- theme map
- today cockpit
- watch board
- source board
- source track record
- validation board
- route normalization queue
- review remediation queue
- anti-thesis board

This is the signature of a **research workbench**, not just a data collector.

Key file:

- [views.py](/vol1/1000/projects/finagent/finagent/views.py)

### Sentinel and event-mining engine

`finagent/sentinel.py` is the real engine-like core.

It explicitly handles:

- validation and normalization of event drafts
- spec validation and sync
- append-only event ledger updates
- state projections
- opportunity candidate generation
- stalled event emission
- prompt builder for external extraction

This is the strongest evidence that Finagent is not only a note-taking repo. It
has a structured event-mining engine.

Key file:

- [sentinel.py](/vol1/1000/projects/finagent/finagent/sentinel.py)

### Graph surface

Finagent includes a smaller, domain-specific graph layer:

- claim / thesis / evidence / review graph
- conflict detection
- support-chain analysis

It is not trying to be a universal knowledge graph. It is a targeted reasoning
graph over investment-research objects.

Key file:

- [graph/schema.py](/vol1/1000/projects/finagent/finagent/graph/schema.py)

### OpenMind integration intent

`finagent/openmind_adapter.py` explicitly exports:

- theses
- entities
- claims
- edges

into an OpenMind-compatible graph format.

That is an important signal:

Finagent was already designed to become a domain producer into a larger
OpenMind-like substrate rather than a completely isolated island.

Key file:

- [openmind_adapter.py](/vol1/1000/projects/finagent/finagent/openmind_adapter.py)

### Test estate

Finagent test surface:

- `pytest_files = 21`

Coverage includes:

- CLI integration
- DB
- contracts
- consensus
- graph
- promotion lifecycle
- sentinel
- source adapters
- theme report
- writeback
- full simulation

This is modest compared with OpenClaw, but substantial for a small vertical repo.

### Finagent verdict

Finagent is best described as:

**a SQLite-backed thesis/research operating system with a large CLI workbench
and a structured event-mining pipeline**

It is not:

- a generic platform
- an always-on gateway runtime
- a bot shell

It is a vertical domain engine.

## 3. Cross-Repo Relationship to ChatgptREST

### OpenClaw vs ChatgptREST

OpenClaw already owns:

- gateway
- session truth
- channels
- devices/nodes
- user-facing always-on runtime
- local memory/search
- coding-team experimentation

ChatgptREST already owns:

- web LLM execution substrate
- job queue and repair plane
- OpenMind runtime host
- cognitive APIs
- KB / memory / event-bus / EvoMap substrate

This means the biggest architectural risk is **runtime overlap**, not missing pieces.

Specifically:

- OpenClaw has its own memory/index system
- ChatgptREST has its own OpenMind memory/KB/graph system
- OpenClaw has coding-team / team runtime experiments
- ChatgptREST has controller / team / CC-native / `cc_sessiond`
- both are growing orchestration concepts

### Finagent vs ChatgptREST

Finagent is much cleaner conceptually:

- it is a vertical research/thesis engine
- it is not trying to be the universal runtime host
- it already has a clear DB-centered domain model

Its natural relationship to ChatgptREST is:

- consume heavy execution or OpenMind capabilities where useful
- export structured domain knowledge upward
- remain independently operable as a vertical system

### OpenClaw vs Finagent

These two repos are not competitors.

The likely clean relationship is:

- OpenClaw = runtime shell / assistant OS / user and agent coordination substrate
- Finagent = domain app / vertical intelligence system

In other words:

- OpenClaw should host, route, and supervise
- Finagent should think, store, and operate within its domain

## 4. Classification Matrix

### OpenClaw

| Area | Verdict |
|---|---|
| Gateway / protocol / sessions | foundational and active |
| Agents / tools / sessions runtime | foundational and active |
| Memory manager | real subsystem |
| Coding-team layer | active and strategically important for your multi-agent goals |
| Extensions | first-class platform layer |
| UI / apps | real product surfaces |
| Repo-local durable DB | not the center of gravity |

### Finagent

| Area | Verdict |
|---|---|
| CLI and views | foundational and active |
| SQLite schema | foundational and active |
| Sentinel / event mining | real engine |
| Domain graph | useful but scoped |
| OpenMind adapter | important bridge surface |
| Docs archive | extremely heavy and itself a major asset |
| Alternate DB paths (`finagent.db`, `state/finagent.db`) | low-centrality / transitional |

## 5. Strategic Findings

1. OpenClaw is more powerful than “entry shell”.
   It is already a serious assistant runtime platform.

2. Finagent is more coherent than “just a side repo”.
   It already has a real vertical operating model.

3. The biggest unresolved architecture problem across the three repos is not
   Finagent. It is the overlap between OpenClaw runtime concepts and
   ChatgptREST runtime concepts.

4. Finagent already has a cleaner role:
   domain-specific, DB-centered, CLI/workbench-first, artifact-rich, and
   export-capable.

5. If you later do strategic convergence work, OpenClaw and ChatgptREST need
   the hardest boundary clarification. Finagent needs less boundary surgery and
   more disciplined evolution.

## 6. Recommended Next Document

The next useful artifact should not be another inventory.

It should be a **three-repo boundary map** that explicitly chooses:

- what OpenClaw owns
- what ChatgptREST owns
- what Finagent owns
- where orchestration authority lives
- where knowledge authority lives
- where vertical domain apps plug in

