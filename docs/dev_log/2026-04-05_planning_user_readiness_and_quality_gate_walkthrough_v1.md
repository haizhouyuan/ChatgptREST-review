# 2026-04-05 Planning User Readiness and Quality Gate Walkthrough v1

## What I Changed

I stopped letting full-planning output pass just because it was long enough.

The key code change is in:

- `chatgptrest/api/routes_agent_v3.py`

The new rule is simple:

1. compact planning still only needs the requested short bullet output
2. full planning must now cover the required planning skeleton
3. if a full-planning answer is long but still misses key sections, it is no
   longer treated as finished

I also added a dedicated user-readiness acceptance pack:

- `chatgptrest/eval/planning_user_readiness_acceptance.py`
- `ops/export_planning_user_readiness_acceptance_pack.py`
- `tests/test_planning_user_readiness_acceptance.py`

## Why I Changed It

The previous gate still allowed a bad user experience:

- a response could be long
- it could look serious
- but it could still miss core sections the user needs to continue work

That is exactly the kind of “looks done, not actually usable” behavior that
breaks trust.

## What Is Better Now

The user-facing difference is:

1. common planning requests still route into the right profile
2. repo-backed implementation planning still defaults into the coding-agent lane
3. same-task continuation still works
4. thin full-planning output still fail-closes
5. long-but-missing-section full-planning output now also fail-closes
6. once fail-closed, the same truth remains visible in the response, the task
   checkpoint, and the session lookup

## Frozen Evidence

The final evidence bundle for this slice is:

- `docs/dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v2/`

The frozen summary is:

- `9` cases
- `9` passed
- `0` failed

The new case that mattered most is:

- `missing_sections_fail_closed`

That case proves a full implementation-plan answer can be long and still be
rejected if it does not contain enough of the required skeleton.

## Why This Matters

Before this batch, the system was already better than a raw chat flow, but it
could still reward “long enough” over “actually complete enough”.

After this batch, the system is closer to the intended user effect:

- answers are not only generated
- they are held to a minimum standard of completeness before being exposed as
  finished work
