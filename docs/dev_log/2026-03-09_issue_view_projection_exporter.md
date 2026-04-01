# 2026-03-09 Issue View Projection Exporter

## 做了什么

新增了一个独立的 issue 视图导出器：

- 脚本：
  - `ops/export_issue_views.py`
- 测试：
  - `tests/test_export_issue_views.py`
- systemd：
  - `ops/systemd/chatgptrest-issue-views-export.service`
  - `ops/systemd/chatgptrest-issue-views-export.timer`

导出产物：

- `artifacts/monitor/open_issue_list/latest.json`
- `artifacts/monitor/open_issue_list/latest.md`
- `artifacts/monitor/open_issue_list/history_tail.json`
- `artifacts/monitor/open_issue_list/history_tail.md`

## 为什么先做这个

当前关于 issue 的两个痛点是：

1. `open issue list` 缺稳定投影，得人工翻 ledger/API
2. `历史演进记录` 的最近变化分散在 `client_issue_events`，不方便直接看

这次先补一个完全读侧的 projection：

- 不改 ledger authoritative state
- 不改 guardian auto-mitigate 逻辑
- 不抢 graph 设计的中间层边界

它只负责把现有 authoritative 数据导出成更容易消费的当前视图。

## 当前设计边界

- authoritative state 仍然在：
  - `client_issues`
  - `client_issue_events`
- exporter 只做：
  - active issue snapshot
  - recently mitigated/closed snapshot
  - recent issue evolution snapshot

这和 `#96` 线程里约定的边界一致：

- ledger authoritative
- projection rebuildable
- graph / retrieval 在此之后再做

## 验证

已跑：

```bash
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_export_issue_views.py
PYTHONPATH=. ./.venv/bin/python ops/export_issue_views.py \
  --db-path state/jobdb.sqlite3 \
  --json-out /tmp/open_issue_list_latest.json \
  --md-out /tmp/open_issue_list_latest.md \
  --history-json-out /tmp/open_issue_list_history.json \
  --history-md-out /tmp/open_issue_list_history.md
```

## 后续建议

下一步不要马上把 exporter 绑进 graph backend。  
更合理的顺序是：

1. 先把 lifecycle 规则补强
   - `live verified => mitigated`
   - `3 次 qualifying client success + 无复发 => closed`
2. 再让 exporter 读这些结构化字段
3. 再把 exporter 输出接入 graph / retrieval projection
