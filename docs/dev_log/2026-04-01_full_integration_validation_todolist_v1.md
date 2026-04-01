# 2026-04-01 全量集成测试 Todo v1

更新时间：2026-04-01
分支：`ccrunner/full-integration-validation-20260401`

## 执行目标

- [x] 跑完主线联合回归集合
- [x] 跑完 API / 服务级 finalization 正负路径验证
- [x] 跑完 bootstrap / obligations / closeout / opencli smoke
- [x] 若失败则完成修复并补回归 (无代码失败；修正了 closeout smoke 命令契约)
- [x] 重跑整套验收集合直到全部通过
- [x] 形成 walkthrough / 结果总结
- [x] 清理临时残留，保证 worktree 可审

## 当前基线

- [x] 最新 `origin/master` 已包含 harness orchestration merge：`f2283ae4`
- [x] 本轮在隔离 worktree 上执行，不污染主工作树
- [x] 验收计划文档已落盘

## 验收门槛

- [x] 21 文件联合回归通过
- [x] `/v1/tasks/{task_id}/finalize` API 路由存在 (chatgptrest/task_runtime/api_routes.py:294)
- [x] service 正向 / 负向 fail-closed 通过
- [x] `chatgptrest_bootstrap.py` smoke 通过
- [x] `chatgptrestctl repo doc-obligations` smoke 通过
- [x] `opencli doctor --no-live` smoke 通过
- [x] `opencli smoke` smoke 通过
- [x] `chatgptrest_closeout.py` smoke 通过

## 修复后必须补的留痕

- [x] walkthrough 更新
- [x] 无代码修改 (所有测试直接通过)
- [x] 测试修复说明 (无测试修复；仅修正文档中的 closeout smoke 命令)
