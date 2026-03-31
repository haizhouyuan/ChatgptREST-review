---
title: work memory review queue operator walkthrough
version: v1
status: active
updated: 2026-03-30
owner: Codex
---

# Work Memory Review Queue Operator Walkthrough v1

## 1. 这轮补了什么

当前 `planning backfill importer` 原来只能：

1. `dry-run`
2. `execute ready`
3. `manual_review_required -> queue`

但 queue 只能堆积，缺少明确 operator path。  
这轮补的是最小可用闭环：

1. review queue `list`
2. `approve`
3. `reject`
4. `promote`
5. `supersede`
6. `rollback`

## 2. 代码面

- `chatgptrest/kernel/work_memory_importer.py`
  - 新增 review queue list/result model
  - 新增 queue resolve operator
  - queue item 加 `review_state / resolution_*`
  - replay 同一 manual-review item 时复用既有 queue record，不再覆盖已处理状态
- `chatgptrest/cli.py`
  - 新增 `work-memory review-list`
  - 新增 `work-memory review-resolve`
- `tests/test_work_memory_importer.py`
  - 覆盖 `promote / reject / supersede / rollback`
- `tests/test_cli_chatgptrestctl.py`
  - 覆盖 queue list / resolve CLI

## 3. 关键设计判断

- 第一版 operator 继续走 CLI，不先长公共 API
- `approve` 和 `promote` 都会把 queue item 写成 `approved` durable object
- `supersede` 只开放给 `decision_ledger`
- `rollback` 不删除记录，只把新对象打回 `rejected`，并恢复 supersede 前快照

## 4. 回归

这轮至少实跑：

```bash
cd /vol1/1000/projects/ChatgptREST
./.venv/bin/pytest -q tests/test_work_memory_importer.py tests/test_cli_chatgptrestctl.py -k 'work_memory'
./.venv/bin/pytest -q tests/test_work_memory_manager.py tests/test_context_service_work_memory.py -k 'work_memory or import'
```

结果：

- 第一组：`14 passed`
- 第二组：`19 passed`

## 5. 下一步

Phase 1 现在可以进入 live operator 验证：

1. 真实 `memory.db` dry-run
2. `ready` execute
3. `manual_review_required` queue list + resolve
4. cross-ingress retrieval verification
5. 四端联验重跑
