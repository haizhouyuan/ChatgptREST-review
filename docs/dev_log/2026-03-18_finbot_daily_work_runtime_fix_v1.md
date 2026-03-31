---
title: "2026-03-18 finbot daily_work runtime fix v1"
source: "[[CODEX]]"
author:
  - "[[CODEX]]"
published:
  created: 2026-03-18
description: "修复 daily_work 市场发现分支缺失 helper 导致的 NameError，恢复 finbotfree 定时 lane。"
tags:
  - "finbot"
  - "finbotfree"
  - "runtime-fix"
---

# finbot daily_work runtime fix v1

## 故障现象

`chatgptrest-finbotfree-daily-work.service` 在 2026-03-18 08:09 CST 手动触发时失败，journal 报错：

```text
NameError: name '_is_any_market_open' is not defined
```

触发位置：

- `chatgptrest/finbot.py:daily_work()`

## 根因

`daily_work()` 已经接入了 market discovery 多策略轮换逻辑，但依赖的 3 个 helper 缺失：

- `_is_any_market_open`
- `_pick_discovery_strategy`
- `_STRATEGY_COMPLEMENTS`

因此一旦进入 `include_market_discovery` 分支，函数会在运行时直接抛 `NameError`。

## 修复

补齐了最小运行时 helper：

1. `_DISCOVERY_STRATEGY_ROTATION`
2. `_STRATEGY_COMPLEMENTS`
3. `_pick_discovery_strategy()`
4. `_is_any_market_open()`

其中 `_is_any_market_open()` 采用保守窗口：

- 工作日
- 亚洲时段：09:00-16:00
- 美股时段：21:30-04:00

## 防回归

新增测试：

- `tests/test_finbot.py::test_finbot_daily_work_skips_market_discovery_when_closed`

覆盖“市场关闭时返回 `market_closed`，而不是抛异常”的路径。
