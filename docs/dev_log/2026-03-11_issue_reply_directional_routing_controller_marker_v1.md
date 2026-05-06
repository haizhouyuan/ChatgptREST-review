# 2026-03-11 Issue Reply Directional Routing Controller Marker v1

## Why

`ops/poll_coordination_issues.py` had to infer whether a new GitHub comment came from the controller lane or a side lane, but both lanes post as the same GitHub user. The old heuristic only recognized a few controller phrasings (`主线...`, `收到。你这条更像是...`, `我已经吸收...`). A controller clarification like:

`收到，这个澄清是有必要的。我的理解与你这条一致：`

did not match that list, so the poller treated it as a side-lane update and injected the wake message back into the controller pane input box.

## What Changed

- `ops/poll_coordination_issues.py`
  - added `<!-- coordination:controller -->` as an explicit controller-origin marker
  - taught `_is_mainline_comment()` to honor that marker before any prose heuristics
  - expanded the fallback heuristic to cover `我的理解与你这条一致`
- `ops/post_coordination_issue_comment.py`
  - added a small helper that posts issue comments through `gh issue comment`
  - appends the hidden controller marker by default so future controller replies are unambiguous
- tests
  - extended `tests/test_poll_coordination_issues.py`
  - added `tests/test_post_coordination_issue_comment.py`

## Verification

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_poll_coordination_issues.py \
  tests/test_post_coordination_issue_comment.py
python3 -m py_compile \
  ops/poll_coordination_issues.py \
  ops/post_coordination_issue_comment.py \
  tests/test_poll_coordination_issues.py \
  tests/test_post_coordination_issue_comment.py
```

## Outcome

Future controller comments no longer depend on phrasing alone to route back to the issue pane. The wake path stays inside the coordination lanes unless a comment is actually from a side lane.
