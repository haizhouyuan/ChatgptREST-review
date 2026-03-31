# 2026-03-15 Main Finbot Delegation Prompt Contract v1

## Goal

Make `main` reliably avoid resource misallocation for investment-research work.

The problem is not only ingress routing. Even with a single human-facing ingress, `main` can still waste context and attention if its prompt contract does not clearly say:

- what to keep in `main`
- what to delegate to `finbot`

## Product Rule

For investment-research work, `main` should be an orchestrator first, not the default executor.

`finbot` should be the default execution lane for:

- theme scans
- watchlist refreshes
- KOL/source sweeps
- opportunity discovery
- multi-ticker / multi-expression comparisons
- recurring market-monitoring work

`main` should keep:

- triage
- prioritization
- cross-theme synthesis
- final judgment
- quick conceptual answers that do not require running the research lane

## Implementation

Updated prompt-contract sources in `scripts/rebuild_openclaw_openmind_stack.py`:

- `HEARTBEATS["main"]`
- `TOOLS.md` content for `main`
- `AGENTS.md` content for `main`

The contract now explicitly tells `main` to use:

- `sessions_send`
- `sessionKey="agent:finbot:main"`

when investment-research execution belongs in `finbot`.

## Why This Matters

Without this instruction, `main` is likely to:

- directly handle market scans
- consume primary-context tokens on routine research
- blur the separation between orchestration and execution

That creates the exact resource mismatch we want to avoid.

## Validation

Regression coverage updated in:

- `tests/test_rebuild_openclaw_openmind_stack.py`

The tests now assert that the generated `main` workspace files and heartbeat text contain:

- explicit `finbot` delegation language
- the `agent:finbot:main` session key

## Outcome

This pass does not create a second human-facing ingress.

It strengthens the real contract that matters:

- user -> `main`
- `main` -> `finbot` for execution
- `main` keeps synthesis and judgment
