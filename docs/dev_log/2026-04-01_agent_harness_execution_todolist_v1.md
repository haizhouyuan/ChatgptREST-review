# Agent Harness 执行 Todo 清单 v1

更新时间：2026-04-01

## 1. Tranche Checklist

### Tranche 1: Truth Model 收口

- [ ] 重定义 PUBLISHED/DISTILLED 语义（task_store.py）
- [ ] 移除 scaffold-only 占用强状态名的逻辑（task_state_machine.py）
- [ ] 验收：状态可数据库重放，文件系统删除后状态可恢复

**依赖**：无

**Done-definition**：
- 所有 state transition 可被数据库重放
- 删除文件系统后状态可从 DB 恢复

**Blocker/风险**：
- 需要确认当前哪些地方占用 PUBLISHED/DISTILLED 但未完成 publication

### Tranche 2: Task Control Plane 做实

- [ ] 实现真实 `_generate_context_snapshot`（task_initializer.py）
- [ ] 串接 `/v1/tasks` 与 `/v3/agent/*`（api_routes.py）
- [ ] 让 ChunkContract 成为唯一执行单元输入（chunk_contracts.py）

**依赖**：Tranche 1

**Done-definition**：
- `/v1/tasks` 可真实驱动任务流转
- 任务可初始化、冻结、计划、分块、推进

**Blocker/风险**：
- task_initializer 的 `_generate_context_snapshot` 当前返回空 dict

### Tranche 3: Evaluator Gate 高可信化

- [ ] 实现 `_run_code_grader` 真实代码/单元测试
- [ ] 实现 `_run_outcome_grader` 检查 artifact contract 合规性
- [ ] 实现 `_run_rubric_grader` LLM rubric 评估
- [ ] 禁用 auto-promote_if_passing 基于 placeholder grader
- [ ] 添加 grader 结果表（task_store.py）

**依赖**：Tranche 2

**Done-definition**：
- promotion 不能绕过 evaluation record
- 无有效 evaluation 不可进入 promoted

**Blocker/风险**：
- 真实 grader 需要测试执行环境和 artifact 扫描能力

### Tranche 4: Durable Execution 做实

- [ ] 部署 task_watchdog 服务
- [ ] 实现 signal 去重逻辑
- [ ] 集成 checkpoint/resume 到 worker

**依赖**：Tranche 2

**Done-definition**：
- 中途 kill 进程后可安全恢复
- 重复信号不会导致重复推进
- 卡死任务被 watchdog 拉回

**Blocker/风险**：
- watchdog 服务需要在后台持续运行

### Tranche 5: Delivery Plane Authoritative

- [ ] 调用 `completion_contract.build_completion_contract`（delivery_integration.py）
- [ ] 添加 completion_contract 字段（task_store.py）
- [ ] 确保 publication 失败时不可占 PUBLISHED

**依赖**：Tranche 3（evaluator gate 通过）

**Done-definition**：
- 只有 authoritative publication 成功，任务才进入 PUBLISHED
- 外部 consumer 读取同一 authoritative answer

**Blocker/风险**：
- 需要确认 completion_contract.py 的集成点

### Tranche 6: Memory Distillation Authoritative

- [ ] 调用 `work_memory_manager.write_from_capture`（memory_distillation.py）
- [ ] 添加 memory_distillation_ref 字段（task_store.py）
- [ ] 确保 distillation 失败时不可占 DISTILLED

**依赖**：Tranche 5

**Done-definition**：
- 只有真实 memory projection 成功，任务才进入 DISTILLED
- work-memory 中只出现来自 promoted/finalized outcome 的 durable knowledge

**Blocker/风险**：
- 需要确认 work_memory_manager 的调用契约

### Tranche 7: 主入口集成

- [ ] 集成 task runtime 入口到 `/v3/agent/*`（routes_agent_v3.py）
- [ ] 对接 frozen context 到 task_intake（advisor/task_intake.py）
- [ ] 补齐 closeout/evidence/replay 路径

**依赖**：Tranche 6

**Done-definition**：
- 至少一条真实主入口 lane 由 Task Harness 驱动
- closeout/evidence/replay 路径完整

### Tranche 8: Harness Acceptance Suite

- [ ] 实现 system-level eval suite
- [ ] 实现 kill-and-recover smoke tests
- [ ] 实现 permission/bypass/forgery negative tests

**依赖**：Tranche 7

**Done-definition**：
- 每个关键 failure mode 都有系统级回归

### Tranche 9: opencli POC Hardening

- [ ] 强制执行 policy metadata（risk_level/auth_mode/browser_mode）
- [ ] pinned binary path
- [ ] isolated execution env
- [ ] receipt-first audit envelope

**依赖**：Tranche 8

**Done-definition**：
- 任何未满足 policy context 的执行都会被拒绝

### Tranche 10: CLI-Anything Governed Intake

- [ ] 实现 candidate state machine
- [ ] review evidence ingestion
- [ ] operator decision path
- [ ] market gate linkage

**依赖**：Tranche 9

**Done-definition**：
- candidate 默认不可信
- 未经 review/approval 不能进入 runtime

## 2. 依赖顺序图

```
Tranche 1 (Truth Model)
    ↓
Tranche 2 (Task Control Plane)
    ↓
Tranche 3 (Evaluator Gate) → Tranche 4 (Durable Execution)
    ↓
Tranche 5 (Delivery) → Tranche 6 (Memory)
    ↓
Tranche 7 (Main Entry Integration)
    ↓
Tranche 8 (Acceptance Suite)
    ↓
Tranche 9 (opencli Hardening) → Tranche 10 (CLI-Anything)
```

## 3. 交付前 Acceptance Checklist

- [ ] 所有 state transition 可被数据库重放
- [ ] 删除文件系统后状态仍可从 DB 恢复
- [ ] `/v1/tasks` 可真实驱动任务流转
- [ ] promotion 不能绕过 evaluation record
- [ ] evaluator 失败时 fail-closed
- [ ] 中途 kill 进程后可安全恢复
- [ ] 重复信号不会导致重复推进
- [ ] 卡死任务被 watchdog 拉回
- [ ] 只有 authoritative publication 成功才能占 PUBLISHED
- [ ] 只有真实 memory projection 成功才能占 DISTILLED
- [ ] 至少一条真实主入口 lane 闭环
- [ ] 每个关键 failure mode 有系统级回归

## 4. 高标准红线

只要触碰以下任一项，就视为**不通过**：

1. placeholder grader 仍参与真实 promotion
2. scaffold publication 占用 PUBLISHED
3. scaffold memory projection 占用 DISTILLED
4. 文件系统承担 durable task truth
5. opencli 使用 ambient PATH/repo-root artifact dir/decorative policy
6. CLI-Anything 生成物未经 review 进入 runtime authority