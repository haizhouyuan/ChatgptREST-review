# Agent Harness 执行蓝图 v1

更新时间：2026-04-01

## 1. 当前代码真实完成度

### 1.1 Task Control Plane（任务控制平面）

| 组件 | 真实完成度 | 评估 |
|------|-----------|------|
| `task_store.py` | foundation | 数据库 schema 已完整（tasks/task_state/task_chunks/task_evaluations/task_promotion_decisions/task_final_outcomes/task_watchdog），但部分字段仍是占位 |
| `task_state_machine.py` | foundation | 状态转换逻辑存在，optimistic locking 有，但与 API surfaces 集成不完整 |
| `task_initializer.py` | partial | frozen context 生成是 scaffold，`_generate_context_snapshot` 返回空 dict（第 143-157 行）|
| `api_routes.py` | partial | REST endpoints 存在（`/v1/tasks`），但与主入口（`/v3/agent/*`）未真衔接 |

**冻结结论**：Task Control Plane 只能算 foundation，不算 best-practice。

### 1.2 Evaluator Gate（评估升级门）

| 组件 | 真实完成度 | 评估 |
|------|-----------|------|
| `promotion_service.py` | skeleton | grader 全部是 placeholder（第 246-277 行）：`_run_code_grader` 返回 `grade="pass", confidence=0.9`；`_run_outcome_grader` 同理；`_run_rubric_grader` 同理 |
| auto-promote 逻辑 | scaffold | `auto_promote_if_passing` 存在（第 217-244 行），但基于 placeholder grader + confidence >= 0.8 阈值 |
| artifact refs | stub | `_collect_artifact_refs` 返回空 list（第 315-318 行）|

**冻结结论**：Evaluator Gate 是 skeleton，不是 skeptical gate。

### 1.3 Delivery Plane（发布平面）

| 组件 | 真实完成度 | 评估 |
|------|-----------|------|
| `delivery_integration.py` | scaffold | 明确注释："does not yet publish an authoritative completion_contract / canonical_answer pair"（第 3-5 行）|
| `publish_to_delivery` | partial | 只创建 `delivery_projection`，不调用 `completion_contract.build_completion_contract` |
| `completion_contract.py` | exists | 真实存在且实现完整，但 delivery_integration 未调用 |

**冻结结论**：Delivery 是 scaffold，不是 authoritative integration。

### 1.4 Memory Distillation（记忆蒸馏）

| 组件 | 真实完成度 | 评估 |
|------|-----------|------|
| `memory_distillation.py` | scaffold | 明确注释："does not yet write through the real work-memory manager"（第 3-5 行）|
| `distill_outcome` | partial | 构建 distillation payload 但不调用 `work_memory_manager.write_from_capture` |
| `work_memory_manager.py` | exists | 真实实现完整（655 行），但 task runtime 未集成 |

**冻结结论**：Memory 是 scaffold，不是 real distillation pipeline。

### 1.5 Durable Execution（持久执行）

| 组件 | 真实完成度 | 评估 |
|------|-----------|------|
| `task_watchdog` | partial | 表已建（第 408-422 行），但 watchdog 服务未部署 |
| idempotency | partial | `inject_signal` 有 signal_id 生成（第 222-244 行），但去重逻辑未闭环 |
| checkpoint/resume | partial | `checkpoint/suspend/resume` 方法存在但未与 worker 集成 |

**冻结结论**：Durable Execution 未做实，watchdog 未部署。

### 1.6 opencli / CLI-Anything

| 组件 | 真实完成度 | 评估 |
|------|-----------|------|
| opencli | validation POC | 执行 substrate 已可工作，但 policy metadata 未强制执行 |
| CLI-Anything | quarantine-shell | manifest normalization 已实现，但无 governed intake 状态机 |

**冻结结论**：两者都远未达到高标准 controlled substrate。

## 2. 与目标架构的 Gap Map

```
目标架构：
  Task Control Plane (DB-backed) → Durable Execution → Evaluator Gate → Delivery (completion_contract) → Memory (work_memory_manager)

当前实现：
  Task Control Plane (foundation) ─┬→ Delivery (scaffold, 不调用 completion_contract)
                                   ├→ Memory (scaffold, 不调用 work_memory_manager)
                                   ├→ Evaluator Gate (placeholder graders)
                                   └→ Durable Execution (watchdog 未部署)
```

Gap 总结：

| Gap | 当前 | 目标 | 优先级 |
|-----|------|------|--------|
| Delivery → completion_contract | scaffold projection | real publication | P0 |
| Memory → work_memory_manager | scaffold payload | real pipeline | P0 |
| Evaluator → real graders | placeholder stubs | code/unit/rubric graders | P0 |
| Durable → watchdog deployed | table only | active service | P1 |
| Task → /v3/agent integration | isolated /v1/tasks | unified entry | P1 |
| opencli → policy enforce | decorative | enforced | P2 |
| CLI-Anything → governed intake | quarantine-shell | state machine | P2 |

## 3. Tranche 实施顺序

### Tranche 1: Truth Model 收口（PR #N）

**目标**：统一 Task/Attempt/Chunk/State/Evaluation/Promotion/Outcome 的 authoritative schema，消除"文件状态 vs 数据库状态"歧义。

**修改文件**：
- `chatgptrest/task_runtime/task_store.py` — 重定义 PUBLISHED/DISTILLED 语义
- `chatgptrest/task_runtime/task_state_machine.py` — 移除所有 scaffold-only 占用强状态名的逻辑

**验收**：
- 所有 state transition 可被数据库重放
- 删除文件系统后，状态仍可从 DB 恢复
- 不存在"scaffold publication 也叫 published"的路径

**回滚**：Git revert + 重新初始化 DB schema

### Tranche 2: Task Control Plane 做实（PR #N+1）

**目标**：让 TaskRecord/TaskAttempt/ChunkContract/TaskState 成为真正可驱动任务推进的控制平面。

**修改文件**：
- `chatgptrest/task_runtime/task_initializer.py` — 实现真实的 `_generate_context_snapshot`
- `chatgptrest/task_runtime/api_routes.py` — 与 `/v3/agent/*` 串接
- `chatgptrest/task_runtime/chunk_contracts.py` — 成为唯一执行单元输入

**验收**：
- `/v1/tasks` 可真实驱动任务流转
- 任务可初始化、冻结、计划、分块、推进
- 所有写操作经过 state machine

**回滚**：回退 API routes + 禁用 task initializer

### Tranche 3: Evaluator Gate 高可信化（PR #N+2）

**目标**：把 evaluator 从 placeholder surface 提升成真实 skeptical gate。

**修改文件**：
- `chatgptrest/task_runtime/promotion_service.py` — 实现真实 grader suite
  - `_run_code_grader` — 实际运行代码/单元测试
  - `_run_outcome_grader` — 检查 artifact contract 合规性
  - `_run_rubric_grader` — LLM rubric 评估
- `chatgptrest/task_runtime/task_store.py` — 添加 grader 结果表

**验收**：
- promotion 不能绕过 evaluation record
- 无有效 evaluation 不可进入 promoted
- evaluator 失败时 fail-closed

**回滚**：回退 grader 实现为 stub + 禁用 auto-promote

### Tranche 4: Durable Execution 做实（PR #N+3）

**目标**：让任务具备真正的 suspend/resume/recovery/timeout/idempotency。

**修改文件**：
- `chatgptrest/task_runtime/task_watchdog.py` — 部署 watchdog 服务
- `chatgptrest/task_runtime/task_state_machine.py` — 实现 signal 去重
- `chatgptrest/worker/` — 集成 checkpoint/resume

**验收**：
- 中途 kill 进程后可安全恢复
- 重复信号不会导致重复推进
- 卡死任务被 watchdog 拉回

**回滚**：停止 watchdog 服务 + 回退 state machine

### Tranche 5: Delivery Plane Authoritative（PR #N+4）

**目标**：FinalOutcome → completion_contract/canonical_answer 成为真实 authoritative downstream publication。

**修改文件**：
- `chatgptrest/task_runtime/delivery_integration.py` — 调用 `completion_contract.build_completion_contract`
- `chatgptrest/core/completion_contract.py` — 确认集成点
- `chatgptrest/task_runtime/task_store.py` — 添加 completion_contract 字段

**验收**：
- 只有 authoritative publication 成功，任务才进入 PUBLISHED
- 外部 consumer 读取同一 authoritative answer

**回滚**：回退 delivery_integration 为 scaffold projection

### Tranche 6: Memory Distillation Authoritative（PR #N+5）

**目标**：FinalOutcome → work_memory_manager 成为真实 distillation pipeline。

**修改文件**：
- `chatgptrest/task_runtime/memory_distillation.py` — 调用 `work_memory_manager.write_from_capture`
- `chatgptrest/kernel/work_memory_manager.py` — 确认集成点
- `chatgptrest/task_runtime/task_store.py` — 添加 memory_distillation_ref

**验收**：
- 只有真实 memory projection 成功，任务才进入 DISTILLED
- work-memory 中只出现来自 promoted/finalized outcome 的 durable knowledge

**回滚**：回退 memory_distillation 为 scaffold payload

### Tranche 7: 主入口集成（PR #N+6）

**目标**：把 Task Harness 真接到主入口。

**修改文件**：
- `chatgptrest/api/routes_agent_v3.py` — 集成 task runtime 入口
- `chatgptrest/advisor/task_intake.py` — 对接 frozen context

**验收**：
- 至少一条真实主入口 lane 由 Task Harness 驱动
- closeout/evidence/replay 路径完整

### Tranche 8: Harness Acceptance Suite（PR #N+7）

**目标**：把 harness 自己变成持续回归资产。

**修改**：
- system-level eval suite
- kill-and-recover smoke tests
- permission/bypass/forgery negative tests

### Tranche 9: opencli POC Hardening（PR #N+8）

**目标**：把 validation POC 提升为真正受控 substrate。

### Tranche 10: CLI-Anything Governed Intake（PR #N+9）

**目标**：把 quarantine-shell 升级为 governed intake。

## 4. Fail-Closed 设计点

| 位置 | 规则 |
|------|------|
| Evaluator Gate | 无有效 evaluation 不可 promote |
| Delivery | publication 失败不可占 PUBLISHED |
| Memory | distillation 失败不可占 DISTILLED |
| Task State | 无 valid transition 不可改状态 |
| opencli | 未满足 policy context 拒绝执行 |
| CLI-Anything | 未经 review 不可进入 runtime |

## 5. 禁止再过度宣称的口径

后续所有文档、PR、walkthrough 禁止再写：

1. "Task Harness 已完整闭环"
2. "Delivery / Memory 已 authoritative integrated"
3. "Evaluator gate 已达到 skeptical evaluator 标准"
4. "opencli 已是高标准 controlled substrate"
5. "CLI-Anything 已形成 governed intake path"

## 6. 实施原则

1. **数据库 / 状态机是 durable task truth**
2. 文件系统只承担 artifacts/handoff/audit anchor
3. Generator 不能自证完成
4. Promotion 必须受 evaluator/operator gate 约束
5. 没有 authoritative downstream side effect，不允许占用强状态名
6. 支线 substrate 不得先于主线 runtime 抢优先级