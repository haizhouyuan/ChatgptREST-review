# 2026-04-03 Planning Phase-1 Continuity Acceptance Pack Walkthrough v1

## 做了什么

本轮把 phase-1 continuity sidecar 的三条窄路径压成了一份可重复导出的 acceptance pack。

新增：

1. `ops/export_planning_phase1_continuity_acceptance_pack.py`
2. `tests/test_export_planning_phase1_continuity_acceptance_pack.py`

实际导出的 evidence bundle：

- `docs/dev_log/artifacts/planning_phase1_continuity_acceptance_pack_20260403_v1/`

## 为什么做

到 `v11` 为止，phase-1 已经有：

1. `meeting_sedimentation`
2. `workforce_planning`
3. `implementation_plan`

三类 continuity slice，但这些证明还主要停留在：

1. 单测
2. 路由测试
3. 分散 review 结论

所以本轮的目标不是继续加第四类 task type，而是回答更值钱的问题：

> 当前三类 slice 到底能不能被压成一份统一、可重复、可审阅的 acceptance bundle？

## 中间遇到的问题

### 1. CLI 入口不能直接跑

导出器一开始缺少 repo-root import 处理，直接运行会报：

1. `ModuleNotFoundError: No module named 'chatgptrest.api.routes_agent_v3'`

修法：

1. 按 repo script 常规写法补了 `REPO_ROOT` 和 `sys.path.insert(0, str(REPO_ROOT))`

### 2. smoke 被 rate limit 误伤

初版导出器在第三个 scenario 上被 `/v3/agent` 默认 limiter 打成 429，导致：

1. `explicit_continue_ok = false`
2. `writeback_ok = false`

这不是 phase-1 continuity 本体坏了，而是离线 smoke 和默认 rate limit 打架。

修法：

1. 在导出器的测试环境里显式设置 `OPENMIND_RATE_LIMIT=1000`

## 最终验证

通过：

```bash
python3 -m py_compile ops/export_planning_phase1_continuity_acceptance_pack.py tests/test_export_planning_phase1_continuity_acceptance_pack.py
./.venv/bin/pytest -q tests/test_export_planning_phase1_continuity_acceptance_pack.py
./.venv/bin/python ops/export_planning_phase1_continuity_acceptance_pack.py --output-dir docs/dev_log/artifacts/planning_phase1_continuity_acceptance_pack_20260403_v1
```

真实导出结果：

1. `manifest.json`: `overall_pass=true`
2. `smoke_manifest.json`: 三个 scenario 全在
3. `report_v1.md`: 三个 scenario 全绿

## 红队

已发起：

1. `claudegac` run `ccjob_20260402T225945Z_d25e3324`

本轮落盘时，它已经在读：

1. 导出器
2. 测试
3. `meeting_task_store.py`
4. `planning_task_checkpoint_complete.py`
5. `routes_agent_v3.py`
6. evidence bundle

但还没有 final verdict，所以这轮先把状态如实记为 `pending`。

## 当前判断

这一步现在可以稳妥地说：

1. phase-1 continuity sidecar 不再只有分散的单测证据
2. 它已经有一份统一 acceptance pack
3. 这份 pack 仍然是离线、deterministic、synthetic acceptance
4. 下一步更值钱的是把 Claude 的严格批评并回，而不是继续机械扩 task type
