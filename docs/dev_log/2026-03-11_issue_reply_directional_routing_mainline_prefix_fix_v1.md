# 2026-03-11 Issue Reply Directional Routing Mainline Prefix Fix v1

## Problem

`ops/poll_coordination_issues.py` originally treated only comments whose first text started with `主线 Codex` as controller-origin comments.

That was too narrow for current controller comment shapes such as:

- `主线已补上 ...`
- `主线这边继续推进 ...`

As a result, valid controller tasking on `#115` was misclassified as a side-lane reply and got routed back to the controller pane `%48` instead of the issue pane `%32`.

## Fix

- broadened `_is_mainline_comment()` so it inspects the first non-empty line
- any first non-empty line starting with `主线` is now treated as controller-origin

This keeps the routing rule simple:

- controller-origin comment -> issue pane
- non-controller comment -> controller pane

## Regression coverage

- retained the old `主线 Codex ...` case
- added a regression test for `主线已补上 ...` comments to ensure they route to the issue-specific pane
- kept side-lane comments such as `education codex ...` on the controller route
