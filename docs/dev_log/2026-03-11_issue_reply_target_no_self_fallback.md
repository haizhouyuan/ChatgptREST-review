## 2026-03-11 Issue Reply Target No-Self Fallback

问题：
- issue reply watcher 在没有显式目标 pane 时，会回退到当前 `TMUX_PANE`
- 这会把 `#114/#115` 的新评论打回 watcher 自己所在的 pane，而不是 controller 或指定 side lane

修复：
- [`ops/watch_github_issue_replies.py`](/vol1/1000/projects/ChatgptREST/ops/watch_github_issue_replies.py) 的 `_default_wake_target()` 不再回退到 `TMUX_PANE`
- 现在只认显式的 `CODEX_CONTROLLER_PANE`
- 没有显式 target 时，wake target 为空，调用方必须：
  - 显式传 `--wake-pane-target`
  - 或显式传 `--wake-pane-map`
  - 或设置 `CODEX_CONTROLLER_PANE`

结果：
- 默认行为从“可能错误回送到自己”变成“宁可不发，也不发错 pane”
- `poll_coordination_issues.py` 这种带显式 issue→pane 映射的调用不受影响
