# 2026-04-27 Euphony Codex Session Reflection Loop v2

## Scope

Implement the V2 closed-loop prototype requested after the v1 Euphony experiment:

```text
Codex session JSONL
  -> automated extraction
  -> wiki candidates
  -> memory candidates
  -> skill update candidate
  -> review-gated promotion
```

This version is intentionally offline and reversible. It does not mutate installed skills, live memory DBs, or production runtime behavior.

## Implementation

Added:

- [codex_session_reflection_loop_v2.py](/vol1/1000/projects/ChatgptREST/scripts/prototypes/codex_session_reflection_loop_v2.py)

The script reuses the v1 session extractor and adds a routing layer:

- discovers or accepts explicit Codex session JSONL files
- enriches reflection candidates with session metadata and Euphony review references
- deduplicates candidates by stable fingerprint
- routes candidates into:
  - `wiki`
  - `memory`
  - `skill_candidate`
- writes review queue artifacts
- generates a candidate `codex-session-reflection` skill folder

Euphony remains part of the loop as the transcript review surface and parser reference:

- viewer: `http://127.0.0.1:8766/`
- parser reference: `/vol1/1000/tools/euphony/src/utils/codex-session.ts`

The agent pipeline does not depend on manually opening Euphony. It reads JSONL directly so the loop is batchable and testable. Euphony is used when a candidate needs transcript-level review.

## V2 run

Command:

```bash
python3 scripts/prototypes/codex_session_reflection_loop_v2.py \
  /vol1/1000/home-yuanhaizhou/.codex1/sessions/2026/04/25/rollout-2026-04-25T17-26-49-019dc3f6-9059-7732-8efe-36a6d9123194.jsonl \
  /vol1/1000/home-yuanhaizhou/.codex1/sessions/2026/04/26/rollout-2026-04-26T22-17-03-019dca26-a2fd-7e33-809a-e3fb6d151edd.jsonl \
  /vol1/1000/home-yuanhaizhou/.codex1/sessions/2026/04/27/rollout-2026-04-27T15-16-14-019dcdcb-bb9f-7b40-8453-7f674b9971d7.jsonl \
  --out-dir docs/dev_log/artifacts/euphony_codex_session_reflection_loop_20260427_v2
```

Result:

- sessions scanned: `3`
- unique candidates: `33`
- wiki candidates: `25`
- memory candidates: `20`
- skill candidates: `15`

Artifacts:

- [loop_report_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/euphony_codex_session_reflection_loop_20260427_v2/loop_report_v2.md)
- [loop_report_v2.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/euphony_codex_session_reflection_loop_20260427_v2/loop_report_v2.json)
- [memory_candidates.jsonl](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/euphony_codex_session_reflection_loop_20260427_v2/queue/memory_candidates.jsonl)
- [skill_update_plan_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/euphony_codex_session_reflection_loop_20260427_v2/queue/skill_update_plan_v2.md)
- [candidate SKILL.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/euphony_codex_session_reflection_loop_20260427_v2/queue/skill_candidates/codex-session-reflection/SKILL.md)

## Closed-loop behavior

### Wiki lane

The script writes one markdown draft per candidate under:

```text
docs/dev_log/artifacts/euphony_codex_session_reflection_loop_20260427_v2/queue/wiki_candidates/
```

These are not promoted into `.omx/wiki` yet. They are review queue items with:

- source session id
- source file path
- category
- confidence
- Euphony review pointer
- promotion checklist

### Memory lane

The script writes JSONL candidate records:

```text
docs/dev_log/artifacts/euphony_codex_session_reflection_loop_20260427_v2/queue/memory_candidates.jsonl
```

These are shaped as memory candidates, not live memory writes. They are useful for future import into `MemoryManager` or interaction-learning once a promotion gate exists.

### Skill lane

The script writes a candidate skill folder:

```text
docs/dev_log/artifacts/euphony_codex_session_reflection_loop_20260427_v2/queue/skill_candidates/codex-session-reflection/SKILL.md
```

The generated skill follows the skill-creator guardrail: it contains concise workflow and guardrails, not raw transcript bodies. The candidate procedural lessons from this run are:

- investigate recurring ChatgptREST incidents across job events, worker logs, exports, and wrapper behavior before patching symptoms
- do not treat backend `429` plus DOM fallback text as a complete answer until finality metadata is reconciled
- submit long Pro or external-review jobs through the public MCP async lane and continue local work
- preserve structured cooldown/rate-limit details instead of collapsing them into generic parse failures
- treat missing final answer artifacts as evidence-chain failure even when provider submission succeeded
- keep client-facing public MCP behavior stable while changing worker/runtime internals
- on resumed maintenance sessions, read handoff and git state before repeating work
- distinguish visible UI thinking indicators from backend model/preset evidence

## Promotion policy

V2 keeps promotion review-gated:

- raw sessions are never promoted directly
- single one-off failures should usually become wiki candidates, not skill changes
- skill changes require either repeated evidence or explicit maintainer approval
- installed skill mutation should be a separate commit with rollback notes
- live memory DB writes should be done by a separate importer with duplicate checks

## Current recommendation

This V2 shape is the right direction.

The missing production pieces are:

1. a small importer that can move approved wiki candidates into `.omx/wiki` or the existing llmwiki location
2. a memory importer that writes approved `memory_candidates.jsonl` through `MemoryManager`
3. a skill patch applier that compares candidate `SKILL.md` against an installed skill path and requires explicit approval before mutation
4. recurrence scoring across more sessions so the skill lane is not driven by one noisy session

Until those exist, the V2 queue is useful as an agent-operated review artifact and avoids the unsafe failure mode of turning raw session noise into permanent agent instructions.
