# 2026-03-09 OpenMind Memory Recall/Capture Vertical Slice

## Why this slice exists

### Strategic target

OpenClaw should be the shell. OpenMind should be the cognition substrate.

That only becomes true if the shell can:

1. capture durable user guidance into OpenMind
2. recall it safely in a later session
3. expose audit evidence for what was remembered and why

Without that loop, the integration is still only "bridge tools are installed",
not "the shell actually benefits from the substrate."

### Business need

The real user need is not generic KB writeback. It is:

- "remember how I want answers structured"
- "remember decisions I already made"
- "remember this preference next time, even in a new session"

That is a memory substrate problem, not a report artifact problem.

### Product slice

This round implements a narrow but complete path:

- OpenClaw `openmind-memory` plugin
- `POST /v2/memory/capture`
- OpenMind episodic memory storage with audit trail
- `/v2/context/resolve` cross-session `Remembered Guidance` block

KB / graph ingest stays on `/v2/knowledge/ingest`. User memory capture no
longer piggybacks on that durable-artifact path.

## Acceptance checkpoints

### CP1 Capture -> Dedup

- repeated capture of the same memory updates one memory record
- duplicate merges are visible in audit trail
- `memory.capture` event is emitted

### CP2 Recall -> Safe Context Block

- later `/v2/context/resolve` requests surface remembered guidance
- prompt prefix gets an explicit `## Remembered Guidance` section
- remembered guidance is treated as memory evidence, not tool instructions

### CP3 Cross-session Persistence + Audit Evidence

- captured memory survives advisor runtime reset
- a different session can still recall it
- audit trail is queryable by `record_id`

## Implementation

### New backend service

- `chatgptrest/cognitive/memory_capture_service.py`

Responsibilities:

- stage captured memory into OpenMind memory
- promote to episodic tier
- keep capture path append-safe and auditable
- emit `memory.capture` events

### API changes

- `chatgptrest/api/routes_cognitive.py`
  - new `POST /v2/memory/capture`

### Recall changes

- `chatgptrest/cognitive/context_service.py`
  - adds a dedicated `captured` memory source
  - appends `## Remembered Guidance` to the prompt prefix
  - falls back to recent captured memory when lexical query matching misses

### OpenClaw plugin changes

- `openclaw_extensions/openmind-memory/index.ts`
  - manual capture now writes to `/v2/memory/capture`
  - `agent_end` auto-capture now writes to `/v2/memory/capture`

## Validation

Targeted API / plugin tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_cognitive_api.py \
  tests/test_openclaw_cognitive_plugins.py
```

Broader integration regression:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_cognitive_api.py \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_verify_openclaw_openmind_stack.py \
  tests/test_install_openclaw_cognitive_plugins.py \
  tests/test_issue_graph_api.py
```

Both passed during this round.

## Follow-up

This closes the first reference implementation slice agreed in issue #110.

The next useful expansion should be:

1. promote selected captured memories into a typed profile/claim model
2. tighten transport/domain-service parity tests
3. add a live business simulation that exercises capture from a real OpenClaw session
