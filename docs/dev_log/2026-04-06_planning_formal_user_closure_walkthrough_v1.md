# 2026-04-06 Planning Formal User Closure Walkthrough v1

## Goal

Turn the earlier "almost closed" planning mainline into one concrete formal
work product that is both:

- completed on the planning task plane
- and actually used in the repo

## Sequence

1. Re-checked the controller-backed coding-agent lane and confirmed the
   remaining blocker was the runtime budget, not executor discovery or parsing.
2. Added a timeout decoupling fix so Claude-family executors no longer inherit
   the same small budget as the foreground turn wait window.
3. Replayed the same explicit task lineage
   `impl_6cafdcc331fa` on the same formal session
   `openclaw-real-closure-card-codex2-session-20260406a`.
4. Observed two outcomes on that same lineage:
   - `f2e0419e2ebd49ad9ea58a2503e15cf9`:
     `claudegac + medium` timed out even with the widened `900s` budget
   - `d91bdf586da141c98df51551deaa805c`:
     `claudegac` without explicit `medium` completed in about `103.7s`
5. Verified the final session file and planning checkpoint both reached
   `completed`.
6. Took the completed planning output and used it as the source content for:
   - `planning_formal_user_closure_acceptance_card_v1`
   - this walkthrough
   - the execution review
   - `master v68`
7. Re-ran the same closure ask through the actual OpenClaw tool surface
   (`openmind_advisor_ask`) and confirmed a fresh answer-first completed
   session on:
   - session `openclaw-real-closure-plugin-session-f4a2254d`
   - run `766edfdd57f643f0a9485be750f6cd1b`
   - executor `claudegac`

## Why This Counts As Closure Progress

Before this batch, the planning system had already proven:

- route selection
- fail-close behavior
- session/task truth on many paths
- OpenClaw adapter main-path observability

But it had not yet proven that one planning output was actually used.

This batch adds exactly that missing proof.

It also adds one strengthening point:

- the fresh actual OpenClaw plugin surface can now be cited together with the
  repo-used closure output, instead of relying only on an earlier live review

## Concrete Outcome

Final successful references:

- session:
  `openclaw-real-closure-card-codex2-session-20260406a`
- task:
  `impl_6cafdcc331fa`
- successful run:
  `d91bdf586da141c98df51551deaa805c`
- fresh plugin run:
  `766edfdd57f643f0a9485be750f6cd1b`

The final session state now shows:

- `status=completed`
- `planning_task.status=completed`
- `checkpoint.current_status=completed`

## Remaining Boundary

This does not mean every executor/effort combination is good.

It specifically shows:

- `claudegac medium` is still too slow for this task shape
- `claudegac` default/no-effort is practical enough to complete and land

So the remaining judgment is now about executor operating envelopes and future
product confidence, not whether the mainline can produce one real formal result
or whether the answer-first OpenClaw surface can still complete a fresh formal
planning ask.
