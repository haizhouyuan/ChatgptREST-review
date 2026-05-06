# 2026-03-20 Full Repo Inventory Audit Walkthrough v1

## What I Did

This walkthrough records how the full-repo inventory in
`2026-03-20_full_repo_inventory_audit_v1.md` was produced.

The goal was not to make a pretty directory list. The goal was to separate:

- code that exists
- code that is wired into runtime
- code that currently has live data behind it
- code that looks legacy or transitional

## Audit Method

I used five passes.

### 1. Surface scan

I scanned the repository root and the main code directories to confirm the repo
shape:

- `chatgptrest/`
- `chatgpt_web_mcp/`
- `ops/`
- `scripts/`
- `openclaw_extensions/`
- `state/`
- `data/`
- `artifacts/`
- `docs/`

This immediately showed that the repo is not just an API service. It is a
combined product/runtime/ops/archive repo.

### 2. Line-count and file-count pass

I measured file counts and line counts for:

- `chatgptrest/`
- `chatgpt_web_mcp/`
- `ops/`
- `tests/`
- `openclaw_extensions/`
- `scripts/`

I also ranked the largest Python hotspots under:

- `chatgptrest/`
- `ops/`
- `tests/`

That pass made the structural hotspots visible immediately:

- `worker.py`
- `mcp/server.py`
- `finbot.py`
- `controller/engine.py`
- `routes_advisor_v3.py`
- `routes_agent_v3.py`
- `maint_daemon.py`

### 3. API/runtime wiring pass

I inspected:

- `chatgptrest/api/app.py`
- `routes_jobs.py`
- `routes_advisor_v3.py`
- `routes_agent_v3.py`
- `routes_cognitive.py`
- `routes_consult.py`
- `routes_dashboard.py`
- `routes_evomap.py`

I also instantiated the FastAPI app and counted routes by prefix to verify that
the repo is carrying several API generations simultaneously.

### 4. Subsystem head-reading pass

I read the top of the major modules that define subsystem responsibility:

- `advisor/runtime.py`
- `advisor/graph.py`
- `kernel/routing/fabric.py`
- `kernel/llm_connector.py`
- `kernel/model_router.py`
- `kernel/routing_engine.py`
- `controller/store.py`
- `controller/contracts.py`
- `dashboard/control_plane.py`
- `dashboard/service.py`
- `chatgpt_web_mcp/server.py`
- `evomap/observer.py`
- `finbot.py`
- `openclaw_extensions/README.md`
- `ops/openclaw_runtime_guard.py`
- `ops/openclaw_guardian_run.py`

That pass was important because names in this repo are misleading unless they
are checked against the code’s own declared role.

### 5. Live SQLite snapshot pass

I inspected the current live databases, including:

- `state/jobdb.sqlite3`
- `state/controller_lanes.sqlite3`
- `state/dashboard_control_plane.sqlite3`
- `state/cc_sessiond/registry.sqlite3`
- `state/knowledge_v2.sqlite3`
- `state/knowledge_v2/canonical.sqlite3`
- `data/evomap_knowledge.db`
- `~/.openmind/memory.db`
- `~/.openmind/kb_search.db`
- `~/.openmind/kb_registry.db`
- `~/.openmind/kb_vectors.db`
- `~/.openmind/events.db`
- `data/kb/*`

This was the most useful pass for distinguishing:

- active systems
- projection stores
- transitional stores
- likely legacy residue

## Why The Conclusions Changed

Before the live DB pass, some layers could still have been described as
"conceptually important but maybe not really in use."

After the live DB pass, several things became much clearer:

1. `jobdb.sqlite3` is the real operational gravity center.
2. the dashboard control plane is real but lightly populated.
3. `cc_sessiond` still exists, but its live centrality is low.
4. the knowledge substrate is absolutely real.
5. there are multiple old storage paths that should no longer be treated as
   equal citizens.

## Most Important Evidence Points

These were the strongest facts behind the final write-up:

1. `state/jobdb.sqlite3` contains both classic jobs and newer controller /
   advisor / issue data, not just queue rows.

2. `state/controller_lanes.sqlite3` is tiny and lane-oriented, which means it
   is not the main controller truth source.

3. `state/dashboard_control_plane.sqlite3` is populated but much smaller than
   the underlying runtime stores.

4. `data/evomap_knowledge.db` is large and active, so EvoMap can no longer be
   described as future-only.

5. `~/.openmind/*` stores are materially more active than old `data/kb/*`
   stores.

6. `state/knowledge_v2.sqlite3` is empty while
   `state/knowledge_v2/canonical.sqlite3` is populated, which strongly suggests
   an incomplete or mid-stream migration pattern.

## Judgment Rules Used

I used these rules while classifying subsystems:

- `active` means code exists, runtime wiring exists, and live data or route use
  exists now.
- `partial` means code exists and some wiring exists, but authority or live use
  is fragmented.
- `legacy` means code or state still exists, but current live centrality is low
  and a newer path already appears dominant.
- `projection` means the store or service is useful, but should not be treated
  as canonical truth.

## Main Risk I Wanted To Avoid

The main failure mode for a repo audit like this is to confuse "interesting
code" with "active system."

This repo has enough historical layers that a pure grep-based audit would
overestimate several paths. That is why the live SQLite pass was necessary.

## Outcome

The resulting inventory is opinionated on purpose.

It does not just say what exists. It also says:

- what appears foundational
- what appears duplicated
- what appears transitional
- where future convergence work should focus

