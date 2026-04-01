---
description: How to review ChatgptREST refactors and branches with GitNexus without using the wrong baseline or the wrong symbol lookup pattern.
---

# ChatgptREST GitNexus Review Workflow

Use this workflow when reviewing:

- refactors in `ChatgptREST`
- large branch deltas
- `maint_daemon` / `ops_shared` extraction work
- “is the GitNexus object/index target correct?” questions

## 1. Decide the review target first

There are three different review modes. Pick one before using GitNexus.

### A. Current branch vs release baseline

Use when you want to know what the active development branch changed relative to release.

- Prefer: `origin/master`
- Do **not** default to local `master`

Reason:

- local `master` may lag behind `origin/master`
- that inflates `detect_changes(compare)` and makes review look worse than the actual intended delta

### B. Narrow review of the last N commits

Use when the user asks for “review these 4 commits” or “review the latest refactor chunk”.

- Do **not** use branch-wide `detect_changes(compare, base_ref="origin/master")`
- Use the exact commit boundary instead
- Then inspect touched symbols/files directly with `context` and `impact`

### C. Review of merged/latest release head

Use when the user asks for “review latest master”.

- First confirm the index is built from the same commit as the release checkout
- If the index still points to a branch head, re-analyze the release checkout/worktree first

## 2. Confirm index freshness against the review target

Before trusting GitNexus answers, compare:

- review target commit
- `.gitnexus/meta.json:lastCommit`

Safe cases:

- reviewing current branch and `HEAD == lastCommit`
- reviewing release checkout and `origin/master checkout == lastCommit`

Unsafe case:

- asking questions about merged/latest master while the index still points to a feature branch

## 3. Use the right GitNexus tool for the job

### For broad branch-wide scope

Use:

- `detect_changes(scope="compare", base_ref="origin/master")`

Only for:

- branch-vs-release review
- not for “latest 4 commits”

### For exact refactor objects

Use:

- `context(name="SubsystemRunner", file_path="chatgptrest/ops_shared/subsystem.py")`
- `context(name="CircuitState", file_path="chatgptrest/ops_shared/subsystem.py")`
- `context(name="main", file_path="ops/maint_daemon.py")`
- `impact(target="SubsystemRunner", direction="upstream", minConfidence=0.8)`

Reason:

- broad `query("maint_daemon subsystem refactor")` is too fuzzy for precise review
- exact symbol + file path lookup is the correct path for new refactor objects

### For suspicious routing/query results

If `query()` returns unrelated hot processes:

1. stop using broad natural-language search
2. switch to exact `context(name=..., file_path=...)`
3. only go back to `query()` for execution-flow discovery after the symbol set is anchored

## 4. Review sequence

### Refactor / subsystem extraction review

1. confirm branch and baseline
2. confirm index commit matches the review target
3. inspect exact new symbols with `context`
4. inspect edited orchestrator entrypoints with `context`
5. run `impact` on extracted/shared symbols
6. use `detect_changes(compare, base_ref="origin/master")` only if the question is truly branch-wide

### Recent-commit review

1. identify the exact commit range
2. inspect touched files/symbols from that range
3. use `context` and `impact` on those touched objects
4. avoid branch-wide `detect_changes` unless the user explicitly wants total branch scope

## 5. Hard rules

- Never assume local `master` is the release baseline.
- Never use broad `query()` as the primary tool for reviewing a known refactor object.
- Never review “latest master” with an index that still points to a feature branch.
- When the target is precise, prefer exact `context(name, file_path)` over fuzzy discovery.

## 6. Typical failure mode this workflow prevents

Bad path:

- feature branch indexed
- local `master` stale
- run `detect_changes(compare, base_ref="master")`
- get huge changed-symbol count
- conclude GitNexus is wrong

Correct path:

- verify target commit
- verify indexed commit
- compare to `origin/master` for branch-wide review
- use exact symbol lookups for subsystem refactors
