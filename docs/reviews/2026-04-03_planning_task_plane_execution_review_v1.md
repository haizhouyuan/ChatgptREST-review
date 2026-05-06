# 2026-04-03 Planning Task Plane Execution Review v1

## 1. 本轮目标

把原先仅覆盖三类 scenario 的 `phase-1 continuity sidecar`，推进成一个更完整的 `planning task plane`，让 `planning` 主线不再只证明：

1. `meeting_sedimentation`
2. `workforce_planning`
3. `implementation_plan`

而是能够覆盖更接近真实 `planning/` 工作的多任务类型、跨端继续、branch、list/query 与 richer checkpoint writeback。

## 2. 本轮新增能力

### 2.1 任务真相层扩展

`chatgptrest/planning/meeting_task_store.py` 现在不再只是“会议沉淀 sidecar store”，而是承载更广 planning task plane 的 truth layer。

本轮新增/增强：

1. task type 从 3 类扩到 7 类：
   - `meeting_sedimentation`
   - `workforce_planning`
   - `implementation_plan`
   - `project_diagnosis`
   - `research_decision`
   - `leadership_report`
   - `planning_general`
2. richer checkpoint schema：
   - `task_title`
   - `project_or_topic_ref`
   - `current_objective`
   - `current_output_target`
   - `decision_summary`
   - `confirmed_scope`
   - `open_questions`
   - `current_artifact_refs`
   - `next_actions`
   - `memory_writeback_candidates`
3. identity history：
   - `by_identity`
   - `history_by_identity`
4. branch support：
   - `parent_task_id`
   - `branch_root_task_id`
5. public listing：
   - `list_public(...)`

### 2.2 agent_v3 接线增强

`chatgptrest/api/routes_agent_v3.py` 本轮新增：

1. `_planning_checkpoint_seed(...)`
   - 从 `task_intake.context`、`objective`、`output_shape` 提取 richer planning metadata
2. `_maybe_resolve_planning_task_layer(...)` 会把 seed 一起传进 task store
3. `_maybe_update_planning_task_layer(...)` 会把 seed 作为 checkpoint patch 写回
4. 新增 `GET /v3/agent/planning/tasks`
   - 支持按 `account_id/thread_id/user_id/session_id/task_type/status` 查询

### 2.3 acceptance pack 扩展

`ops/export_planning_phase1_continuity_acceptance_pack.py` 本轮已从“phase-1 continuity acceptance pack”提升为更接近 `planning task plane` 的 acceptance pack。

当前 pack 覆盖 7 个 scenario：

1. `meeting_sedimentation`
2. `workforce_planning`
3. `implementation_plan`
4. `project_diagnosis`
5. `research_decision`
6. `leadership_report`
7. `planning_general`

每个 scenario 当前都验证：

1. first response
2. retrieve
3. identity continue
4. explicit continue
5. list
6. writeback
7. writeback content
8. checkpoint version

### 2.4 新增 route-level planning tests

本轮新增：

- `tests/test_routes_agent_v3_planning_task_plane.py`

它证明了：

1. `project_diagnosis` 的 identity-based continue 可用
2. `branch` 可从诊断线程分出 `leadership_report`
3. `research_decision` 与 `planning_general` 已被真正接进 route layer

## 3. 本轮修过的真实问题

这一步不是单纯“扩 scenario 数量”，中间修了几个真实分类与持久化问题：

1. `management/管理层` 关键词会把人力规划误分到 `leadership_report`
   - 现已从 `leadership_report` keyword 集中移除
2. `profile=implementation_plan` 曾经会过早自证为 `implementation_plan`
   - 现改为只有 semantic text 里命中真实 implementation 关键词时才升格
3. writeback 检查之前只看“命令成功”
   - 现在 acceptance pack 会检查 persisted `latest_output` 是否真的等于写回内容
4. 之前 pack 只证明显式 `task_id` continue
   - 现在 pack 也证明同一 identity 下的 implicit continue

我的独立判断是：

1. 这些修复都属于“把 planning task plane 从 demo 口径推进到更可信口径”
2. 它们不是 cosmetic cleanup，而是会直接影响任务分类、跨端继续和验收可信度

## 4. 验证结果

### 4.1 编译与测试

已通过：

```bash
python3 -m py_compile \
  chatgptrest/api/routes_agent_v3.py \
  ops/export_planning_phase1_continuity_acceptance_pack.py \
  tests/test_routes_agent_v3_meeting_task_layer.py \
  tests/test_routes_agent_v3_planning_task_plane.py \
  tests/test_export_planning_phase1_continuity_acceptance_pack.py

./.venv/bin/pytest -q \
  tests/test_meeting_task_store.py \
  tests/test_planning_task_checkpoint_writeback.py \
  tests/test_planning_task_checkpoint_complete.py \
  tests/test_routes_agent_v3_meeting_task_layer.py \
  tests/test_routes_agent_v3_planning_task_plane.py \
  tests/test_export_planning_phase1_continuity_acceptance_pack.py \
  tests/test_agent_v3_routes.py \
  tests/test_public_agent_mcp_validation.py
```

### 4.2 真实 evidence bundle

已成功导出：

- `docs/dev_log/artifacts/planning_task_plane_acceptance_pack_20260403_v2/manifest.json`
- `docs/dev_log/artifacts/planning_task_plane_acceptance_pack_20260403_v2/report_v1.md`

关键结果：

1. `overall_pass = true`
2. `scenarios = 7`
3. `passed = 7`
4. 七个 scenario 全部通过：
   - `first_response_ok`
   - `retrieve_ok`
   - `identity_continue_ok`
   - `explicit_continue_ok`
   - `list_ok`
   - `writeback_ok`
   - `writeback_content_ok`
   - `checkpoint_version_ok`

## 5. 本轮能证明什么

这一步现在可以证明：

1. ChatgptREST 内部的 planning task plane 已不再局限于三类 continuity slice
2. 现在至少已有 7 类 planning task type 的 truth-layer support
3. identity-based continue 与 explicit continue 都已被 acceptance pack 证明
4. route layer 已支持 planning tasks list/query
5. 深度工作台 writeback 已从“命令存在”提升到“持久化内容可校验”

## 6. 本轮不能证明什么

这一步仍然不能证明：

1. `Feishu/OpenClawBot` 主链 ingress 已真实验收
2. full `task_runtime` 已接成 authoritative task plane
3. 所有 planning 高频任务都已完成 production-ready acceptance
4. Claude strict sign-off 已最终通过

所以这一步的准确口径应写成：

> 当前已完成的是 ChatgptREST 内部 `planning task plane` 的一次明显扩面与加强，不再只是三条 continuity sidecar；但外部 OpenClawBot 主链验收与 full task runtime 仍不是这一步的证明范围。

## 7. 当前结论

我现在的独立判断是：

1. 这一步已经超出“最小实现”，属于真正扩大了 planning task plane 的覆盖范围
2. 但仍应把它定义为 `phase-1 task truth / continuity plane`，不要误写成 `full task runtime`
3. 下一步最重要的是拿已提交版本做严格 Claude red-team，而不是继续先加第 8、9 类 task type
