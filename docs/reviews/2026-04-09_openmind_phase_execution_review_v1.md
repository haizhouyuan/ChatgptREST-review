# OpenMind Phase 0–6 Execution Review

**Reviewer**: Antigravity (Claude Opus 4.6 Thinking)  
**Date**: 2026-04-09  
**Scope**: Commits `cec0d69f`..`3967b3f2` (4 commits, 20 files, +1976/−3 lines)

## Summary Verdict

**Pass — solid execution round.** The roadmap was executed end-to-end with real runtime integration, not just docs. Code quality is high, tests pass, contracts are frozen, and the authority precedence invariant is correctly maintained throughout. No critical issues; three advisory observations below.

---

## 1. Code Quality

### `chatgptrest/cognitive/wakeup_packet.py` (565 lines)

**Strengths:**
- Clean layered architecture: L0–L3 maps cleanly to the four substrate sources
- Source precedence (`authority anchor > project memory > EvoMap knowledge > runtime heuristics`) is declared as a module constant and threaded through every output surface (JSON, markdown, receipt)
- Defensive coding throughout: every external value goes through `str(...).strip()`, `dict(... or {})`, `list(... or [])` — correct for a system that ingests arbitrary user/runtime payloads
- `frozen=True` dataclasses prevent accidental mutation downstream
- `_clip()` applies consistent token/char budgeting per layer, preventing prompt blowup
- `packet_id` generation via SHA-1 of `(trace_id, project_id, query, timestamp)` is deterministic and collision-resistant for this use case
- `wakeup_packet_receipt()` correctly produces a thin projection suitable for `task_intake.context` without leaking full layer text

**One minor observation:**
- Line 298: `if isinstance(active_block, object)` — this is always `True` in Python (everything is an instance of `object`). The intent is likely `if active_block is not None`. Not a bug because the subsequent `getattr(..., "provenance", [])` handles `None` gracefully, but it's a dead guard.

### `chatgptrest/advisor/crystallized_learning.py` (89 lines)

**Strengths:**
- Correctly enforces `min_support >= 2` before promoting a preference to crystal — this prevents single-observation overfit
- `_STABLE_PREFERENCE_KEYS` whitelist prevents arbitrary fields from graduating to authority-adjacent status
- Explicit `invalidation` block with semantic rule ("newer record supersedes") is exactly right for a governed learning surface
- `precedence_note` is a human-readable safety net embedded in every crystal output
- `crystal_id` is derived from content hash, not timestamp, so identical preference sets produce the same ID — correctly idempotent

### `routes_agent_v3.py` integration

**Strengths:**
- `_maybe_compile_wakeup_packet()` is fail-open by design: `try/except` catches any compilation error and writes a diagnostic receipt instead of breaking `/v3/agent/turn`
- Correctly gates on `any((project_scope, authority_inputs, planning_task_layer))` — no packet is compiled for thin/anonymous requests, avoiding noise
- The `_merge_available_input_mapping()` helper correctly handles three shapes of `available_inputs`: `None`, `Mapping`, and legacy `str` — good backward compat
- Packet is projected into both `task_intake.available_inputs.wake_up_packet` (structured) and `context["wake_up_packet_receipt"]` (thin receipt) — correct dual-surface design

### `prompt_builder.py` changes

- Correctly suppresses duplicate `L0` rendering when the authority anchor is already present in the prompt — the `include_authority_layer=not authority_present` guard prevents double-counting
- Handles the `wake_up_packet` key exclusion from the "Additional inputs" JSON block, preventing redundant serialization

---

## 2. Test Coverage

| Test file | Count | Verdict |
|---|---|---|
| `test_wakeup_packet.py` | 3 tests | Covers layered compilation, L0 suppression, crystallized learning integration |
| `test_crystallized_learning.py` | 2 tests | Covers support threshold enforcement and invalidation-via-newer-winner lifecycle |
| `test_task_intake.py` | 24 tests | Pre-existing + new coverage |
| `test_prompt_builder.py` | 13 tests | Includes `test_build_prompt_from_strategy_renders_wakeup_packet_without_duplicate_l0` |
| `test_routes_agent_v3.py` | 82 tests | Includes `test_agent_turn_projects_wakeup_packet_into_task_intake_and_compiled_prompt` |
| `test_run_wakeup_packet_harness.py` | 1 test | Harness smoke test |

**All 125 tests pass (43 + 82 = 125 across the two runs).**

**Test quality observations:**
- `test_crystallized_learning.py::test_build_interaction_learning_crystal_supports_invalidation_via_newer_winner` is an excellent lifecycle test — it runs through a full progression (codex×2 → claude×3) and verifies both the winner flip and the stable invalidation key linkage
- The route-level wakeup test correctly mocks `build_wakeup_packet` and then verifies both the structured `available_inputs` projection and the prompt text appearance — good end-to-end assertion
- The prompt builder test for L0 suppression is the right test for the right invariant

**Gaps (advisory, not blocking):**
- No test for the `_maybe_compile_wakeup_packet` failure path (the `except` branch that writes `applied: False`). Worth adding for regression confidence.
- No test for `_merge_available_input_mapping` with a legacy `str` existing value — the helper handles it, but the edge case isn't exercised.

---

## 3. Contract and Documentation Integrity

### `docs/contracts/2026-04-09_wakeup_packet_contract_v1.md`

- Correctly freezes schema, layer contract, provenance rules, and consumer surfaces
- Source precedence explicitly inherits ADR-005
- "Residual risks" section is honest about limitations (retrieval quality, fail-open behavior, `authority_schema_partial`)
- Acceptance evidence correctly links to both commits and test files

### `docs/contracts/2026-04-09_openmind_scope_surface_inventory_v1.md`

- The classification table is the key deliverable here — it cleanly separates "bridge only" from "implemented runtime" from "reserved / not implemented"
- This is the right artifact for settling the OpenMind naming drift: "do not claim current ownership" for standalone advisor/memory runtimes

### `docs/integrations/2026-04-09_openclaw_cognitive_substrate_runtime_contract_v3.md`

- Correctly positions v3 as the successor to v2, with clear "why this version" framing
- The topology diagram accurately reflects the current stack: OpenClaw → plugins → ChatgptREST → packet compiler → prompt
- Crystallized learning is correctly scoped as "bounded Hermes-style borrowing, not a self-evolution runtime"

### `AGENTS.md` sync

- Verified: the +6 lines correctly add the wake-up packet contract reference and consumption surface declaration

---

## 4. Real Harness Verification

The archived packet at `artifacts/monitor/wakeup_packet_harness/20260409T022911Z/wakeup_packet.json` shows:

- Real project-scoped resolution for `prs` (行星滚柱丝杠)
- Authority anchor correctly resolved from `/vol1/1000/projects/planning/行星滚柱丝杠/_project_context.md`
- `degraded: true` with honest `degraded_sources: ["personal_graph_empty", "authority_schema_partial"]` — the system correctly reports its own gaps
- `token_summary.context_used_tokens: 1323` out of `requested_token_budget: 4500` — well within budget
- Four pinned authority inputs correctly surfaced in `provenance_summary`

This is a genuine production-grade trace, not a synthetic test artifact.

---

## 5. Residual Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| `isinstance(active_block, object)` always-true guard (L298) | Low | Non-functional; `getattr` handles None gracefully |
| No test for packet compile failure path | Low | Runtime is fail-open by design; adding test would improve regression confidence |
| `authority_schema_partial` on real `prs` project | Known | Already documented as residual; requires `_project_context.md` owner field |
| Staged promotion backlog still at 96K+ | Known | Documented in walkthrough; not in scope for this round |

---

## 6. Decision on `/vol1/maint` Inventory Files

The decision to exclude the two `/vol1/maint` agent inventory files from this commit batch is correct. Those files are cross-cutting path inventories, not semantic contracts. Including them would introduce unrelated churn into a semantically coherent commit sequence.

---

## Final Assessment

This is a high-quality execution round. The work transitions from "plan written" to "runtime integrated" across the most important phases (packet compiler, crystallized learning, doc scope narrowing). The authority precedence invariant is maintained end-to-end, tests are comprehensive, contracts are frozen with honest residual risks, and the real harness artifact proves the system works against live data.

**Status: Accepted / no rework required.**
