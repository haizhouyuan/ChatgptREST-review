# 2026-03-11 Issue Reply Directional Routing Mainline Prefix Fix v3

## Why v2 still needed refinement

`v2` broadened controller-origin detection to include comments beginning with `收到...`.

That fixed controller absorb replies such as:

- `收到。你这条更像是...`
- `收到，这轮 ... 我已经吸收：...`

But taken literally, `收到...` is too broad because side-lane replies can also start that way, for example:

- `收到这条校正。 我这边不再把 validator alias 当成主线待办源问题...`

Those must still route to controller pane, not back to the issue pane.

## v3 rule

The first non-empty line is now classified as controller-origin only when:

- it starts with `主线`
- or it starts with `收到` and the full comment contains controller absorb markers such as:
  - `我已经吸收`
  - `已吸收：`
  - `你这条更像是`
  - `这里先明确`
  - `不批准`
  - `只批准`

Explicit side-lane prefixes such as `education codex` and `evomap-import codex` remain side-lane replies.

## Effect

- controller tasking comments route to issue panes
- controller absorb / park comments stop self-echoing into `%48`
- side-lane correction replies that begin with `收到...` still route back to controller pane
