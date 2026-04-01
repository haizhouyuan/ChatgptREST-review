# 2026-03-11 Planning EvoMap Execution Walkthrough v1

## Objective

Finish the `planning -> EvoMap` workstream at the correct boundary:

- do not pull raw `planning` content into live runtime retrieval
- do materialize lineage/review-plane structure inside canonical EvoMap
- do produce a reviewed bootstrap active set

## Execution Notes

### Review-plane path, not runtime cutover

The execution stayed aligned with the intended architecture:

- `planning` raw files stay authoritative in the `planning` repo
- review-plane objects are projected into canonical EvoMap
- service activation is restricted to the reviewed allowlist

This avoided mixing `planning` archive material into the live execution telemetry workstream.

### Tooling used for reviewer throughput

The review stage used multiple lanes:

- `Gemini CLI` for split-pack review
- `Claude` detached review runs
- `Codex ambient` for `rest_all`
- heuristic baseline as a deterministic fallback

Practical outcome:

- `Gemini CLI` worked reliably when prompts were passed through `stdin`, not long argv
- `Claude` direct detached runs produced usable JSON payloads, but the current `cc runner` wrapper still has a long-prompt/argv weakness
- `Codex ambient` worked for the smaller `rest_all` pack

The merged reviewer set produced a better final allowlist than the earlier partial merge.

### Why bootstrap logic had to be adjusted

The first canonical bootstrap run imported review-plane successfully, but promotion stalled in the planning-specific groundedness step.

Root cause:

- `planning` content often does not need runtime grounding checks
- the generic groundedness path is more appropriate for atoms with concrete runtime anchors
- using it on all planning candidates made bootstrap too slow and operationally noisy

Fix applied:

- `planning_review_plane.apply_bootstrap_allowlist()` now distinguishes:
  - runtime-anchored atoms -> normal groundedness gate
  - review-verified planning deliverables without runtime anchors -> planning-specific fast path
- bootstrap now also reconciles out atoms that were promoted under an older allowlist but are no longer present in the final merged decision set

### Final state

The workstream now has these durable outcomes:

- review-plane imported into canonical EvoMap
- all planning docs tagged with review metadata
- final merged reviewer decisions captured
- bootstrap active set created and reconciled

Operationally, this means `planning` is no longer only “large staged archive content”; it now has an initial reviewed service slice.

## Files Changed

Code:

- [planning_review_plane.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_review_plane.py)
- [import_planning_review_plane_to_evomap.py](/vol1/1000/projects/ChatgptREST/ops/import_planning_review_plane_to_evomap.py)
- [test_planning_review_plane.py](/vol1/1000/projects/ChatgptREST/tests/test_planning_review_plane.py)

Artifacts:

- [planning_review_plane snapshot root](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane/20260311T022504Z)
- [bootstrap_active_v3](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane/20260311T022504Z/bootstrap_active_v3)

## Validation

Code validation:

```bash
./.venv/bin/python -m py_compile \
  chatgptrest/evomap/knowledge/planning_review_plane.py \
  tests/test_planning_review_plane.py \
  ops/import_planning_review_plane_to_evomap.py

./.venv/bin/pytest -q tests/test_planning_review_plane.py
```

Execution validation:

- review decisions re-merged with the full available multi-runner output set
- bootstrap verified on a temporary copy of canonical EvoMap before re-running against the live canonical DB
- final canonical counts re-queried after the `v3` bootstrap run

## Boundary Reminder

This run completed `planning -> EvoMap` as a review-plane/bootstrap project. It did **not** claim that full `planning` retrieval should now read all staged planning atoms in production.

That boundary is still correct.

