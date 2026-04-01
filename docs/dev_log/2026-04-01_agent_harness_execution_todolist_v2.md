# Agent Harness 执行 Todo 清单 v2

更新时间：2026-04-01

## 当前状态

- [x] Tranche 1: Truth Model 收口
- [x] Tranche 2: Task Control Plane 做实（`/v1/tasks` + `/finalize` 主链）
- [x] Tranche 3: Evaluator Gate 高可信化（组件级）
- [x] Tranche 4: Durable Execution 做实（组件级）
- [x] Tranche 5: Delivery Plane Authoritative（task runtime 内端到端闭环）
- [x] Tranche 6: Memory Distillation Authoritative（task runtime 内端到端闭环）
- [ ] Tranche 7: 主入口集成
- [x] Tranche 8: Harness Acceptance Suite（task runtime acceptance 已补齐）
- [ ] Tranche 9: opencli POC Hardening
- [ ] Tranche 10: CLI-Anything Governed Intake

## 本轮收口结论

- [x] 第三轮 Claude Code 已引入真实 orchestration caller：`TaskFinalizationService`
- [x] `/v1/tasks/{task_id}/finalize` 已接入 runtime surface
- [x] final outcome -> published -> distilled -> completed 已有真实服务级 / API 级闭环
- [x] delivery / memory / completion 不再仅靠测试手工推进状态
- [x] 负向路径 fail-closed：无 summary 时保持在 `PROMOTED`

## 第二轮实现后新增确认（已保留）

- [x] DeliveryPublisher 已贯通 `db_path`
- [x] MemoryDistiller 已贯通 `task_db_path` / `memory_db_path`
- [x] walkthrough 不再声称 `/v3/agent/*` 主入口已完成
- [x] 新增组件级 publish/distill 正反测试

## 已解决阻断项

### Blocker 1: 没有真实调用方把 delivery/memory/completion 串起来

- [x] `publish_to_delivery()` 已有真实 runtime 调用链
- [x] `distill_outcome()` 已有真实 runtime 调用链
- [x] `complete_task()` 已有真实 runtime 调用链

解决方式：
- 新增 `chatgptrest/task_runtime/task_finalization.py`
- 通过 `TaskFinalizationService.finalize_task()` 串联：
  - `PROMOTED -> PUBLISHED`
  - `PUBLISHED -> DISTILLED`
  - `DISTILLED -> COMPLETED`
- `/v1/tasks/{task_id}/finalize` 作为 runtime surface 调用该 orchestrator

### Blocker 2: 端到端真实复现未通过

- [x] 真实 finalization 路径不再依赖手工 `update_task_status(...)` 伪造成功
- [x] 至少一条 runtime surface 能从 promoted outcome 走到 completed

验证证据：
- 服务级：`TaskFinalizationService.finalize_task()` 正向/负向验证通过
- API 级：`POST /v1/tasks/{task_id}/finalize` 返回 `200`，任务终态为 `COMPLETED`
- 负向：无 summary 的 outcome 调用 finalize 时 fail-closed，任务保持 `PROMOTED`

### Blocker 3: acceptance tests 仍主要通过手工状态推进绕过真实流程

- [x] 新测试已覆盖真实 finalize entry
- [x] 至少补了一条 API/服务级测试，覆盖真实 final outcome -> published -> distilled -> completed

说明：
- 单元级 publish/distill 测试仍会局部推进状态，用于隔离组件行为；这不再是唯一 acceptance 依据
- 端到端 acceptance 现在由真实 finalize path 覆盖

### Blocker 4: 文档口径仍需继续收紧

- [x] walkthrough 已收口为 `task runtime foundation + orchestrated finalize path`
- [x] 不再将本轮实现表述为 `/v3/agent/*` 主入口已完成

## 当前剩余边界

- [ ] 还没有接入 `/v3/agent/*` 或更高层主入口
- [ ] 还没有完成 opencli / CLI-Anything tranche
- [ ] 这轮闭环范围是 `task runtime foundation + finalize orchestration`

## 本轮 Acceptance Checklist

- [x] `publish_to_delivery()` 有真实调用方
- [x] `distill_outcome()` 有真实调用方
- [x] `complete_task()` 有真实调用方
- [x] 至少一条 runtime/API 主路径从 promoted outcome 走到 completed
- [x] 端到端测试不再只靠手工 `update_task_status()` 伪造 success
- [x] walkthrough 口径与代码现状一致
- [x] 服务级 / API 级独立验收通过

## 独立验收摘要

- 服务级正向：`PROMOTED -> COMPLETED` 成功，且 `delivery_projection_ref` / `memory_distillation_ref` 均落库
- API 级正向：`POST /v1/tasks/{task_id}/finalize` 成功返回 `COMPLETED`
- 服务级负向：无 summary 时返回失败且任务保持 `PROMOTED`
