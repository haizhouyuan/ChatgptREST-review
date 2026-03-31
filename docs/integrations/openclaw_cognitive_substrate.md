# OpenClaw Cognitive-Substrate Integration

Date: 2026-03-08

This document describes the implementation that turns the architecture plan
from issue `#97` into concrete integration assets.

## Positioning

OpenMind is positioned as the durable cognitive substrate. OpenClaw is an
optional execution front-end, not a survival dependency.

That means:

- OpenMind must remain independently valuable through its own memory, KB,
  graph, telemetry, and advisor surfaces.
- OpenClaw integration is an acceleration layer for ecosystem reach, not the
  product-defining source of truth.
- Any OpenClaw plugin should degrade cleanly without changing OpenMind's
  authority boundaries.

## Current maturity gates

This integration exists today, but it is not a blanket claim that OpenClaw is
the primary shell for OpenMind.

Current M1 focus:

- stabilize EvoMap and governed writeback behavior
- keep semantic/vector recall available through OpenMind-owned APIs
- harden graph federation instead of assuming repo graph is always present on
  the hot path
- prove at least one internal recall -> graph -> answer -> capture -> improved
  follow-up loop before broadening ecosystem dependence

Later M2/M3 work:

- tighten contracts for external execution shells
- validate failure semantics and tenant boundaries across shells
- expand OpenClaw integration once the substrate is stable enough to be treated
  as infrastructure rather than an experiment

## Delivered assets

Backend APIs:

- `GET /v2/cognitive/health`
- `POST /v2/context/resolve`
- `POST /v2/memory/capture`
- `POST /v2/graph/query`
- `POST /v2/knowledge/ingest`
- `POST /v2/kb/upsert`
- `POST /v2/telemetry/ingest`
- `POST /v2/policy/hints`

OpenClaw plugins:

- `openmind-advisor`
- `openmind-memory`
- `openmind-graph`
- `openmind-telemetry`

Operational helper:

- `scripts/install_openclaw_cognitive_plugins.py`

## Authority split

- OpenClaw remains authoritative for:
  - sessions
  - channels
  - tool execution
  - workflow execution
  - user-visible delivery
- OpenMind remains authoritative for:
  - long-term memory
  - KB writeback
  - personal graph
  - repo-graph federation
  - telemetry-backed policy hints
  - slow-path advisor cognition

## Plugin roles

### `openmind-advisor`

Purpose:

- expose OpenMind slow-path cognition as a plugin tool

Tool:

- `openmind_advisor_ask`

Backends:

- `/v2/advisor/ask`
- `/v2/advisor/advise`

### `openmind-memory`

Purpose:

- occupy the OpenClaw memory slot when OpenClaw is used as a front-end
- inject OpenMind context on `before_agent_start`
- ingest user-memory candidates on `agent_end`

Hooks:

- `before_agent_start`
- `agent_end`

Manual tools:

- `openmind_memory_recall`
- `openmind_memory_capture`
- `openmind_memory_status`

### `openmind-graph`

Purpose:

- expose first-class graph retrieval to OpenClaw

Tool:

- `openmind_graph_query`

Backend:

- `/v2/graph/query`

### `openmind-telemetry`

Purpose:

- bridge execution telemetry into EvoMap

Hooks:

- `after_tool_call`
- `agent_end`
- `message_sent`

Tool:

- `openmind_telemetry_flush`

Backend:

- `/v2/telemetry/ingest`

## Install

Preferred: use the official OpenClaw CLI so plugin provenance is tracked and
`plugins.load.paths` is updated correctly.

```bash
cd /vol1/1000/projects/ChatgptREST
openclaw plugins install --link ./openclaw_extensions/openmind-advisor
openclaw plugins install --link ./openclaw_extensions/openmind-graph
openclaw plugins install --link ./openclaw_extensions/openmind-memory
openclaw plugins install --link ./openclaw_extensions/openmind-telemetry
```

Fallback helper: stage all local plugins into the default OpenClaw extensions dir:

```bash
cd /vol1/1000/projects/ChatgptREST
python3 scripts/install_openclaw_cognitive_plugins.py --force --print-config
```

Copy instead of symlink:

```bash
python3 scripts/install_openclaw_cognitive_plugins.py --copy --force
```

Install only the memory plugin:

```bash
python3 scripts/install_openclaw_cognitive_plugins.py \
  --plugin openmind-memory \
  --target-root ~/.openclaw/extensions \
  --force
```

## Recommended OpenClaw config

```yaml
plugins:
  enabled: true
  entries:
    openmind-advisor:
      enabled: true
      config:
        endpoint:
          baseUrl: "http://127.0.0.1:18711"
          apiKey: ""
    openmind-graph:
      enabled: true
      config:
        endpoint:
          baseUrl: "http://127.0.0.1:18711"
          apiKey: ""
        defaultRepo: "ChatgptREST"
    openmind-telemetry:
      enabled: true
      config:
        endpoint:
          baseUrl: "http://127.0.0.1:18711"
          apiKey: ""
    openmind-memory:
      enabled: true
      config:
        endpoint:
          baseUrl: "http://127.0.0.1:18711"
          apiKey: ""
        graphScopes: ["personal", "repo"]
        repo: "ChatgptREST"
  slots:
    memory: "openmind-memory"
```

## Runtime behavior

### Hot path

`openmind-memory` calls `/v2/context/resolve` before agent start.

Important constraints:

- retrieval-only by default
- no frontier LLM on the default hot path
- prompt prefix wrapped as untrusted evidence
- short TTL local cache in the plugin
- repo graph may still be partial on the hot path; callers must respect degraded
  hints instead of assuming full repository context is always injected

### Warm path

`openmind-memory` captures only user-side memory candidates and sends them to
`/v2/memory/capture`.

Guardrails:

- user messages only
- prompt-injection pattern rejection
- capped capture length
- capture is stored as cross-session episodic memory with audit evidence
- durable KB / graph ingest remains a separate path via `/v2/knowledge/ingest`

### Cold path

`openmind-advisor` routes deep tasks into OpenMind advisor APIs.

Use it for:

- research
- report generation
- critique
- structured plans

Not for:

- per-turn recall
- cheap policy hints
- repo graph neighborhood fetches

## Repo graph federation

`/v2/graph/query` now accepts structured repo-graph payloads from a GitNexus
command adapter.

Supported output normalization:

- already-normalized `{nodes, edges, paths, evidence}`
- GitNexus-style `{processes, process_symbols, definitions, markdown}`
- plain text fallback as evidence

This keeps GitNexus authoritative for code graph indexing while making the
repo graph consumable from OpenMind APIs.

## Telemetry and policy feedback

`/v2/telemetry/ingest` now propagates `session_id` into observer payloads so
`/v2/policy/hints` can summarize recent execution outcomes for the current
session.

Current policy feedback summary includes:

- recent tool failures
- recent tool successes
- recent negative user feedback
- recent delivery failures

That makes EvoMap-driven hints execution-aware instead of context-only.

## Migration notes

If you currently rely on `memory-lancedb`:

1. keep it disabled once `plugins.slots.memory = "openmind-memory"`
2. keep OpenClaw as the shell truth source
3. let OpenMind become the durable memory / KB / graph truth source

Do not run two durable memory owners at once.
