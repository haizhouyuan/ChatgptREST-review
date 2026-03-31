# Cognitive Substrate Full Implementation Walkthrough

Date: 2026-03-08
Branch: `codex/openmind-cognitive-substrate-impl-20260308`
PR: `#98`

This walkthrough records the second half of the blueprint implementation after
the backend API contract landed.

## Scope completed in this pass

1. Strengthened `repo_graph` federation so `/v2/graph/query` can normalize structured GitNexus payloads instead of returning only raw command stdout.
2. Extended telemetry-policy closure so `/v2/policy/hints` can summarize recent execution outcomes from EvoMap observer data.
3. Added four OpenClaw plugin packages:
   - `openmind-advisor`
   - `openmind-memory`
   - `openmind-graph`
   - `openmind-telemetry`
4. Added installation tooling and integration docs.

## Design decisions

### Keep high-risk runtime symbols untouched

GitNexus impact for:

- `ContextAssembler`
- `get_advisor_runtime`
- `EvoMapObserver`

was `CRITICAL`.

To avoid destabilizing the existing advisor runtime and quick-ask flows, this
implementation continued to extend only the new cognitive layer and plugin
assets. No edits were made inside:

- `chatgptrest/advisor/graph.py`
- `chatgptrest/advisor/runtime.py`
- `chatgptrest/kernel/context_assembler.py`
- `chatgptrest/evomap/observer.py`

### Repo graph normalization

`GitNexusCliAdapter` now recognizes three output classes:

1. normalized graph payloads
2. GitNexus process payloads
3. plain text fallback

That lets `/v2/graph/query` return usable `nodes`, `paths`, and `evidence`
whenever the adapter command emits structured JSON.

### Execution-aware policy hints

`TelemetryIngestService` now propagates `session_id` into observer payloads.
`PolicyHintsService` then aggregates recent session signals into:

- tool failure counts
- tool success counts
- negative feedback count
- delivery failure count

Those summaries are surfaced both as:

- `execution_summary`
- human-readable hints

### OpenClaw plugin split

The plugin packaging follows the blueprint package set:

- advisor
- memory slot
- graph
- telemetry

This keeps execution-shell concerns on the OpenClaw side while routing durable
cognition and storage back into OpenMind.

## Verification

Targeted cognitive regression:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_cognitive_api.py -k 'graph_query or telemetry_ingest or policy_hints'
```

Plugin package smoke:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_install_openclaw_cognitive_plugins.py
```

Compile sanity:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python -m py_compile \
  chatgptrest/cognitive/graph_service.py \
  chatgptrest/cognitive/policy_service.py \
  chatgptrest/cognitive/telemetry_service.py \
  scripts/install_openclaw_cognitive_plugins.py
```

## Remaining external step

The blueprint is now implemented inside ChatgptREST, but one external step
still remains outside this repository:

- install the plugin packages into a live OpenClaw workspace and enable them in
  OpenClaw config

That deployment step is intentional and separated from repository delivery.
