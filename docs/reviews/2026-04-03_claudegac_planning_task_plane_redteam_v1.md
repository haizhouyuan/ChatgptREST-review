# 2026-04-03 ClaudeGAC Planning Task Plane Redteam v1

## 1. 审核对象

- code baseline: `5e0a4e80`
- review run: `ccjob_20260402T235439Z_cde4a47c`
- result file:
  - `/vol1/1000/home-yuanhaizhou/.claude-gac/skills/claudecode-agent-runner/runs/ccjob_20260402T235439Z_cde4a47c/result/claude_result.json`

## 2. 红队结论

结论是 `approve-with-tightening`。

它确认的事实：

1. 7 类 `planning task type` 的 create / retrieve / identity continue / explicit continue / list / writeback 基本链路都成立。
2. `branch`、`parent_task_id`、`branch_root_task_id` 写入成立。
3. `checkpoint seed` 确实被接进 create/update。
4. task file 落盘使用了 tmp + replace。
5. `_lock` 仍覆盖了 resolve/update 事务。

## 3. 红队主要问题

### 3.1 High

1. `list_public()` 在无 identity 参数时会把磁盘上所有 task 都列出来。
2. `implementation_plan` 的判断在 `profile == implementation_plan` 且语义词不命中时会掉回 `planning_general`。
3. 去掉 plain `管理层` 关键词后，可能缩窄 `leadership_report` 识别。

### 3.2 Medium

1. `GET /planning/tasks` 没有限制 list 上限。
2. `_planning_checkpoint_seed()` 对 context list 字段直接 `list(...)`，脏输入可能把 endpoint 打挂。
3. 负向 acceptance test 主要证明“没副作用”，不是模拟真实 writeback failure mode。
4. `_should_continue()` 只要材料有一个重叠就会 continue。

## 4. 我的独立判断

### 4.1 接受并立即修

1. `list_public()` 空 identity 全量列出：这是实打实的泄漏面，必须 fail-closed。
2. `GET /planning/tasks` 应做 `limit` 收敛。
3. `_planning_checkpoint_seed()` 应只接受安全文本序列，不该让脏 shape 直接打挂 route。

### 4.2 部分接受并改写

1. `implementation_plan` 的兼容问题成立，但不能按“profile-only 一票通过”修。
2. 代码现实里，generic `planning` ask 的 scenario pack 默认就可能是 `implementation_plan`。
3. 如果按 `profile-only => implementation_plan` 修，会把普通 `project_diagnosis / planning_general` 吃掉。
4. 更合理的修法是：
   - 保留显式 `goal_hint=implementation_planning` 兼容
   - 保留真实实施语义关键词命中
   - 不让 generic planning 的默认 pack profile 直接改写 task type

### 4.3 不按原话接受

1. “恢复 plain `管理层` 关键词”我不直接采纳。
2. 之前去掉它是为了避免 `workforce_planning + audience=管理层` 被误判为 `leadership_report`。
3. 更稳的做法不是把关键词回滚，而是补测试锁住：
   - `workforce_planning + 管理层 audience` 仍归 `workforce_planning`
   - “管理层汇报摘要”因为 `汇报` 命中而归 `leadership_report`

## 5. 后续动作

下一轮修复应聚焦：

1. `list_public` fail-closed + limit clamp
2. `checkpoint seed` 脏输入保护
3. `implementation_plan` 兼容逻辑改写
4. 补覆盖上述行为的单测
