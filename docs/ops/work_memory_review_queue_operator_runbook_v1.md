---
title: work memory review queue operator runbook
version: v1
status: active
updated: 2026-03-30
owner: Codex
---

# Work Memory Review Queue Operator Runbook v1

## 1. 适用范围

本 runbook 只覆盖 `planning backfill -> work-memory import` 产生的 `manual_review_required` 队列项。

当前 operator 面只开放本地 CLI：

```bash
cd /vol1/1000/projects/ChatgptREST
./.venv/bin/python -m chatgptrest.cli work-memory review-list
./.venv/bin/python -m chatgptrest.cli work-memory review-resolve ...
```

不通过公共 API 直接改 review queue。

## 2. 队列模型

- review queue category: `work_memory_import_review`
- 存储 tier: `meta`
- 初始状态: `review_state=pending`
- 处理后状态:
  - `resolved`
  - `rolled_back`

关键字段：

- `payload`
- `import_metadata`
- `review_state`
- `resolution_action`
- `resolution_reason`
- `resolution_actor`
- `resolution_record_id`
- `resolution_superseded_record_id`

## 3. 列队命令

查看待处理条目：

```bash
./.venv/bin/python -m chatgptrest.cli work-memory review-list \
  --state pending \
  --json-out docs/dev_log/artifacts/work_memory_review_queue_20260330/list_pending_v1.json \
  --report-out docs/dev_log/artifacts/work_memory_review_queue_20260330/list_pending_v1.md
```

查看全部历史条目：

```bash
./.venv/bin/python -m chatgptrest.cli work-memory review-list --state all
```

## 4. 处理动作

### 4.1 `approve`

```bash
./.venv/bin/python -m chatgptrest.cli work-memory review-resolve <record_id> \
  --action approve \
  --reviewer planning-operator \
  --reason "证据充分，允许进入 durable object"
```

当前实现里，`approve` 会把 queue item 解析为 `approved` durable object 并写入 `episodic`。

### 4.2 `promote`

```bash
./.venv/bin/python -m chatgptrest.cli work-memory review-resolve <record_id> \
  --action promote \
  --reviewer planning-operator \
  --reason "进入 active context"
```

`promote` 与 `approve` 都会写入 active durable object，差别只保留在审计动作名，便于 operator 区分“审批通过”和“明确要求进 active context”。

### 4.3 `reject`

```bash
./.venv/bin/python -m chatgptrest.cli work-memory review-resolve <record_id> \
  --action reject \
  --reviewer planning-operator \
  --reason "来源不足，继续停留在 authority docs，不入 durable object"
```

`reject` 只更新 queue item，不写 active durable object。

### 4.4 `supersede`

仅支持 `decision_ledger`：

```bash
./.venv/bin/python -m chatgptrest.cli work-memory review-resolve <record_id> \
  --action supersede \
  --supersedes-decision-id DCL-OLD \
  --reviewer planning-operator \
  --reason "新结论替代旧结论"
```

此动作会：

- 写入新的 `decision_ledger`
- 把被替代对象标记为 `superseded`
- 在 queue item 中保留 rollback 所需的 restore snapshot

### 4.5 `rollback`

```bash
./.venv/bin/python -m chatgptrest.cli work-memory review-resolve <record_id> \
  --action rollback \
  --reviewer planning-operator \
  --reason "导入后核验发现口径错误，回滚"
```

`rollback` 会：

- 把该 queue item 之前写入的 durable object 改为 `review_status=rejected`
- 若此前动作是 `supersede`，则恢复被替代对象的原始值
- 把 queue item 状态改为 `rolled_back`

## 5. 审计与回滚原则

- 所有 queue 处理都必须带 `--reviewer` 和 `--reason`
- 不允许静默改状态
- `manual_review_required` 不允许默认直写 active
- replay 同一 queue item 不会重复插入新的 pending 记录
- 已 `resolved` 的 queue item 只允许执行 `rollback`

## 6. 推荐操作顺序

1. 先 `review-list --state pending`
2. 对每个条目明确 `approve/promote/reject/supersede`
3. 对有问题的已落库对象再执行 `rollback`
4. 再跑 retrieval verification，确认：
   - active project 在 decision ledger 前
   - rejected / pending / rolled_back 条目不进 active context
   - supersede/rollback 的 explainability 保留
