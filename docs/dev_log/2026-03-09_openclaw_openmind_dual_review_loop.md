# OpenClaw/OpenMind Dual Review Loop

Date: 2026-03-09

## Goal

Drive external dual-model review to a clean pass for the simplified OpenClaw/OpenMind topology:

- `lean` default: `main`
- `ops` optional: `main + maintagent`

The intent is not a one-shot bundle upload. The intent is a repeatable review loop: fix real external findings, resubmit, and keep iterating until the topology can survive public-code review without evidence-chain gaps.

## Baseline status before this loop

- Live topology rebuild was already complete.
- Local verifier had passed for both `lean` and `ops`.
- Gemini external review had already returned a non-blocking pass.
- ChatGPT Pro review was slower and more sensitive to evidence delivery quality.

## Round history

### ChatGPT Pro round 2

Job:

- `8d64a9b6c1cb47bf91ef1c791904c5aa`

Observation:

- conversation export moved beyond pure preamble and surfaced a real evidence-chain problem
- the conversation itself still remained in-progress; this was not a final verdict
- the bundle / review metadata still referenced an older synced public branch

Action taken:

- refreshed the topology review bundle links
- then made the bundle branch-agnostic so later syncs would not immediately make the document stale again

Commits:

- `5060102` `docs: refresh topology review bundle links`
- `0e74d5d` `docs: make review bundle branch-agnostic`

### ChatGPT Pro round 3

Job:

- `40470ed11cca49bfbe2b8c5c86cea84d`

Public branch used:

- `review-20260309-092126`

Observation:

- manual `chatgpt_web.conversation_export` succeeded
- exported review text reported that the mirror branch did not contain `scripts/rebuild_openclaw_openmind_stack.py`
- this was a real defect, not model confusion: `ops/sync_review_repo.py` did not include `scripts/` in `SOURCE_DIRS`

Action taken:

- added `scripts` to the public review sync source directories
- added a regression test to ensure `rebuild_openclaw_openmind_stack.py` is mirrored

Validation:

- `./.venv/bin/pytest -q tests/test_sync_review_repo.py`
- `./.venv/bin/python -m py_compile ops/sync_review_repo.py tests/test_sync_review_repo.py`
- verified latest public mirror branch exposes:
  - `scripts/rebuild_openclaw_openmind_stack.py`

Commit:

- `5af077c` `fix: include scripts in public review sync`

### ChatGPT Pro round 4

Job:

- `fa9a64ba30b04b77bca787ae5b2b0ccb`

Manual export job:

- `fbed40f2b15c4a999fef73daf3221baf`

Public branch used:

- `review-20260309-093244`

Current status at time of writing:

- prompt sent successfully
- conversation export works
- latest manual export is still a preamble, not a final verdict
- no new concrete blocker has been emitted yet on the fixed mirror

## Side work completed while waiting

Used idle time to scan the current open-source "self improving agents" landscape and capture the recommendation in:

- `docs/reviews/self_improving_agents_scan_20260309.md`

Key conclusion:

- `SIAS` is the most OpenClaw-relevant project
- useful as a pattern source
- not appropriate as a substrate replacement for OpenMind

Commit:

- `3fc9265` `docs: add self-improving agents scan`

## Practical conclusion

This external review loop has already paid for itself:

1. it caught stale public branch metadata
2. it caught a real public mirror omission (`scripts/`)
3. both were fixed and committed

At this point the remaining task is no longer "repair obvious evidence delivery mistakes". It is to wait for a real final ChatGPT Pro verdict on the now-complete public review branch and then respond only if that verdict contains substantive blockers.
