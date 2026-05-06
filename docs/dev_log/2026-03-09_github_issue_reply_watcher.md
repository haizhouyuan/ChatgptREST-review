# 2026-03-09 GitHub Issue Reply Watcher

## 背景

之前直接在 shell 里挂 `gh issue view ...` 的死循环，只能等命令结束，不能真正把当前 Codex 会话唤醒。  
这对“等 issue 对方回复”这个场景不好用，因为回复到了也只是后台进程返回，不会自动变成外部提醒。

## 本轮收口

新增脚本：

- `ops/watch_github_issue_replies.py`

能力：

- 记录 issue 当前评论数为 baseline
- 轮询 GitHub issue 评论数
- 发现新评论后：
  - 发送 Feishu webhook（默认读 `FEISHU_BOT_WEBHOOK_URL`），或
  - 发送本机桌面通知（`notify-send`）
  - 更新本地状态文件并退出

状态文件默认落到：

- `state/github_issue_watch/<repo_slug>/issue_<number>.json`

## 用法

先 arm baseline：

```bash
PYTHONPATH=. ./.venv/bin/python ops/watch_github_issue_replies.py 110 --arm-only
```

再进入等待：

```bash
PYTHONPATH=. ./.venv/bin/python ops/watch_github_issue_replies.py 110 --wait
```

如果想用桌面通知而不是 Feishu webhook：

```bash
PYTHONPATH=. ./.venv/bin/python ops/watch_github_issue_replies.py 110 --wait --desktop-notify
```

## 验证

```bash
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_watch_github_issue_replies.py
```

## 结论

对“等待 GitHub issue 回复”这类场景，正确形态不是让 Codex shell 自己傻等，而是：

- 持久 watcher
- 外部通知
- 当前会话只在收到新任务时继续处理

解决的是通知链路问题，不是让当前 shell 阻塞更久。
