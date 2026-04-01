## Goal

Land the useful team-control-plane/runtime feature from PR `#178` as a clean implementation on top of current `master`, with the previously identified correctness gaps fixed.

## Scope

- Include:
  - team catalog / topology / gate configuration
  - persistent team control plane
  - advisor runtime integration
  - advisor v3 team-control routes
  - native multi-role team dispatch
- Exclude:
  - unrelated historical docs/reviews from PR `#178`
  - any behavior that cannot be made correct and testable in this pass

## Known Gaps To Fix

1. `team_run` must not finalize while checkpoints remain pending.
2. `topology_id + explicit team` must produce deterministic merged team behavior.
3. `max_concurrent` must be enforced for parallel fan-out.

## Execution Steps

1. Cherry-pick the clean feature commit into a fresh branch.
2. Run symbol impact/context checks via a fresh agent session with working GitNexus.
3. Patch checkpoint resolution semantics.
4. Patch topology overlay semantics.
5. Patch runtime concurrency enforcement.
6. Add regression coverage for the above.
7. Run focused tests, then broader advisor/kernel regressions.
8. Write adjudication + walkthrough, detect changes, push, and open PR.

## Acceptance

- Clean branch contains only team-control-plane runtime feature plus fixup commits/docs.
- Multi-checkpoint approval/rejection semantics are correct.
- Route contract for `team + topology_id` is actually honored.
- Parallel topology runtime respects configured concurrency cap.
- Focused tests pass.
- Broader integration tests pass.
