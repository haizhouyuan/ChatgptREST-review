# 2026-03-20 OpenClaw / Finagent Cross-Repo Inventory Audit Walkthrough v1

## What I Did

This walkthrough records how the cross-repo inventory for `openclaw` and
`finagent` was produced from inside the `ChatgptREST` workspace.

The main goal was to avoid vague statements like:

- “OpenClaw is just the entry shell”
- “Finagent is just a side repo”

Both are too imprecise to support architecture decisions.

## Audit Method

I used six passes.

### 1. Git and directory pass

For both repos I first checked:

- current branch
- dirty status
- top-level directories

This mattered because both repos are actively changing, and the audit needed to
be read as a moving-system snapshot, not as a pristine release review.

### 2. Manifest and README pass

I read:

- `openclaw/package.json`
- `openclaw/pnpm-workspace.yaml`
- `openclaw/README.md`
- `finagent/pyproject.toml`
- `finagent/README.md`

That clarified the declared identity of each system before touching the code.

### 3. Code-shape and line-count pass

I measured code-heavy roots rather than raw whole-repo totals.

For OpenClaw, I excluded:

- `node_modules`
- `dist`
- `.worktrees`

because they would badly distort the real platform shape.

For Finagent, I split:

- core code
- scripts
- tests
- docs
- specs

because its document corpus is much larger than its executable code.

### 4. Runtime and protocol pass

For OpenClaw I inspected:

- gateway architecture docs
- session model docs
- queue docs
- gateway method list
- protocol index
- gateway client
- memory manager
- coding-team tool

This was enough to establish whether OpenClaw is merely a chat frontend or a
real runtime platform.

For Finagent I inspected:

- CLI
- DB schema
- views
- sentinel
- graph schema
- event run tracking
- OpenMind adapter

This was enough to establish whether Finagent is a notebook-like project or a
real vertical operating system.

### 5. Live DB pass

For Finagent I inspected:

- `finagent.db`
- `state/finagent.db`
- `state/finagent.sqlite`
- artifact-local `finagent.sqlite` files
- `.hcom/hcom.db`

This was the key pass for distinguishing:

- active DB path
- alternate-but-empty DB path
- empty residue

OpenClaw did not expose the same kind of repo-local SQLite center. Its docs
showed that session truth primarily lives in `~/.openclaw/...`, not inside the
repo root.

### 6. Test-surface pass

For OpenClaw I counted `.test.ts` files and inspected the visible test tree.

For Finagent I enumerated `tests/test_*.py`.

This was used only as a rough maturity signal, not as proof of behavioral
correctness.

## Most Important Findings From The Audit Process

### OpenClaw

The strongest evidence against calling OpenClaw a thin shell was:

1. the gateway docs and session docs
2. the 90-method typed gateway surface
3. the large `src/agents`, `src/gateway`, `src/memory`, and `src/channels` trees
4. the explicit coding-team subsystem and its large test surface

Those four points make it clear that OpenClaw is a runtime platform.

### Finagent

The strongest evidence for Finagent being a real vertical engine was:

1. the large SQLite domain schema
2. the active `state/finagent.sqlite` table counts
3. the enormous CLI surface
4. the large workbench-oriented `views.py`
5. the explicit event-mining responsibilities in `sentinel.py`

Those five points make it clear that Finagent is not just a notes repo.

## Why The Cross-Repo Conclusion Matters

The inventory changed the architecture picture in one important way:

the hard boundary problem is not “ChatgptREST vs Finagent”.

It is much more:

- `OpenClaw runtime concepts` vs `ChatgptREST runtime concepts`

That matters because both of those repos now contain:

- session concepts
- memory concepts
- orchestration concepts
- multi-agent or team-execution concepts

Finagent, by comparison, already looks more like a clean domain vertical.

## Outcome

The resulting document is intentionally opinionated:

- OpenClaw is classified as a runtime platform
- Finagent is classified as a vertical thesis/research operating system
- the main cross-repo risk is runtime overlap between OpenClaw and ChatgptREST

That is the main reason this cross-repo audit is worth keeping alongside the
main `ChatgptREST` inventory.

