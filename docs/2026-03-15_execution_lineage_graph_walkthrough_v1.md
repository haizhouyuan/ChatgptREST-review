# 2026-03-15 Execution Lineage Graph Walkthrough v1

## Why This Exists

The old `/v2/advisor/dashboard` graph page was effectively a placeholder. It hinted at a future knowledge graph, but it did not explain the one graph surface that already has enough trustworthy data in the control plane: execution lineage.

This pass intentionally does **not** try to visualize everything. It narrows the graph surface to:

- `task`
- `run`
- `job`
- `lane`
- `team_run`
- `checkpoint`
- `issue`
- `incident`

The goal is operational clarity first: explain why a run is stuck before layering on cognitive overlays.

## Scope Decisions

### What We Added

- A real execution-lineage graph projection in [chatgptrest/dashboard/service.py](/vol1/1000/worktrees/chatgptrest-autoorch/chatgptrest/dashboard/service.py)
- Three bounded graph APIs:
  - `/v2/dashboard/api/graph/lineage`
  - `/v2/dashboard/api/graph/run/{root_run_id}`
  - `/v2/dashboard/api/graph/neighborhood?id=...&depth=2`
- A rebuilt graph page at `/dashboard/graph` using Cytoscape.js
- Route tests for graph payloads and page rendering

### What We Deliberately Did Not Add

- Cognitive/OpenMind graph overlays
- Automation graph overlays
- Browser-side joins across raw sqlite files
- React/React Flow migration
- Unbounded full-graph force layout

## Architecture

### Read Model

The graph reads from the existing dashboard control-plane projection, not raw source databases. The main tables involved are:

- `run_index`
- `identity_map`
- `incident_index`
- `run_timeline`

This keeps the hot path deterministic and prevents the graph page from becoming a multi-database query engine.

### Graph Shape

The graph is rooted by `root_run_id`. For each root run, the service builds a bounded lineage subgraph:

1. root run node
2. identity nodes attached to that root
3. incident nodes attached to that root
4. typed edges between them

Neighborhood expansion works by selecting a node, resolving the related roots, and rehydrating only those roots.

### Frontend Choice

We use **Cytoscape.js** because the current dashboard is Jinja + vanilla JS. One graph library is enough for:

- DAG-like lineage views
- bounded relationship neighborhood views
- typed styling without a React rewrite

## API Contract

### `/v2/dashboard/api/graph/lineage`

Returns:

- selected root run
- bounded root list for the selector
- graph payload `{ nodes, edges }`
- legend
- status cards

### `/v2/dashboard/api/graph/run/{root_run_id}`

Returns a single-root lineage graph. This is the cleanest endpoint for linking from detail views later.

### `/v2/dashboard/api/graph/neighborhood`

Accepts a bounded node id:

- `root:<root_run_id>`
- `identity:<entity_type>:<entity_id>`
- `incident:<incident_key>`

Returns the merged lineage graph for nearby roots only. This keeps expansion explainable and cheap.

## UX Rules

- Default view shows one controlled lineage slice, not the whole world
- Root selection reloads the graph from a projection endpoint
- Neighborhood expansion requires an explicit selected node
- The right-hand detail panel only shows selected-node facts, not generated summaries

## Testing

Coverage added in [tests/test_dashboard_routes.py](/vol1/1000/worktrees/chatgptrest-autoorch/tests/test_dashboard_routes.py):

- graph page renders the new execution-lineage framing
- graph API returns `execution_lineage`
- root-run lineage endpoint returns the requested root
- neighborhood endpoint expands a bounded subgraph

One fixture issue surfaced during implementation: `execution_outcomes` is consumed by the dashboard control-plane but is not created by the main job DB helper. The correct fix was to create that table inside the dashboard route test fixture instead of mutating runtime DB initialization.

## GitNexus Note

Per repository policy, impact analysis was attempted before editing `graph_snapshot` and `make_dashboard_router`, but the GitNexus MCP calls timed out repeatedly at 120s. This walkthrough records that limitation explicitly instead of pretending a blast-radius result existed.

## Result

This is now a real operational graph page, but it is intentionally narrow. The next graph stage should be:

1. keep this execution lineage surface stable
2. let `autoorch` and inbox flows generate more execution artifacts
3. only then decide whether automation overlays are dense enough to deserve a second graph plane
