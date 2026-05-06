# 2026-03-11 Issue Reply Directional Routing Mainline Prefix Fix v2

## Why v1 was still insufficient

`v1` fixed controller tasking comments that start with `主线...`, for example:

- `主线已补上 ...`
- `主线这边继续推进 ...`

But a second self-echo remained: controller absorb / park replies often start with `收到...`, for example:

- `收到。你这条更像是上线前可能需要的准备项盘点...`

Those were still being classified as non-mainline replies and routed back to controller pane `%48`.

## v2 adjustment

- `_is_mainline_comment()` now treats the first non-empty line beginning with either:
  - `主线`
  - `收到`
  as controller-origin

## Effect

- controller tasking comments still route to the issue pane
- controller absorb / park comments no longer self-echo back into controller pane
- side-lane comments with explicit prefixes such as `education codex` and `evomap-import codex` remain on the controller route
