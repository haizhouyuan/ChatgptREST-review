# 2026-04-03 OpenClaw Dynamic Replay Runner Walkthrough v1

## What I changed

1. Reproduced the current runner failure: `ModuleNotFoundError: chatgptrest`.
2. Verified the gate itself is green when imported with `PYTHONPATH=.`.
3. Added repo-root bootstrap to the runner.
4. Added env-overridable output directory support.
5. Added `manifest.json` emission so the runner behaves like the newer live gates.
6. Added dedicated runner tests.

## Why this matters

之前我们把这条线当成“harness 本体还坏着”，但现场核实后更准确的是：

- gate 本体可运行
- runner 断了

把这件事收口后，后续就不该再沿用过期的 `fetch failed` 口径来描述当前状态。
