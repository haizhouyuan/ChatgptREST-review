# 2026-04-03 Planning Task Contract Metadata And Exporter Identity Fix Execution Review v1

## 本批目标

这批继续推进 `W2`，但口径明确收紧为两件事：

1. 把七类 planning task 的 `handoff / resume` 规则做成 runtime-visible contract metadata
2. 修掉 `planning phase1 continuity acceptance exporter` 的 identity 假阴性

这批**不是**宣称已经做成执行性的 task contract engine。

## 实际改动

1. `chatgptrest/planning/meeting_task_store.py`
   - 新增 `_TASK_CONTRACT_VERSION`
   - 新增 `_task_contract(task_type)`
   - 在 `new / continue / branch / checkpoint update` 路径上持久化 `task_contract`
   - `public payload` 现在会投影 `task_contract`
2. `scripts/planning_task_checkpoint_get.py`
   - compact handoff 现在带 `task_contract`
3. `scripts/planning_task_checkpoint_list.py`
   - compact list 现在带 `checkpoint_version / task_contract_version / current_output_target`
4. `ops/export_planning_phase1_continuity_acceptance_pack.py`
   - `lookup` 与 `after_writeback` 现在显式带 `account_id / thread_id`
   - 对齐当前 `/v3/agent/planning/task/{task_id}` 的 identity gate 契约
5. 测试补强
   - `tests/test_meeting_task_store.py`
   - `tests/test_planning_task_checkpoint_query.py`
   - `tests/test_routes_agent_v3_planning_task_plane.py`
   - 回归重跑 exporter / acceptance / route / store / CLI 相关套件

## 实现后的效果

现在七类 planning task 至少有了统一、可读、可投影的 contract 元数据：

1. `checkpoint_version`
2. `default_output_target`
3. `initial_next_step`
4. `allowed_actions`
5. `continue / branch / writeback` 的规则提示
6. 深度工作台常用 query / writeback 入口提示

同时，phase-1 continuity acceptance exporter 不再因为缺 identity query params 而把真实通过案例误判成失败。

## 验证结果

已通过：

1. `python3 -m py_compile chatgptrest/planning/meeting_task_store.py scripts/planning_task_checkpoint_get.py scripts/planning_task_checkpoint_list.py tests/test_meeting_task_store.py tests/test_planning_task_checkpoint_query.py tests/test_routes_agent_v3_planning_task_plane.py`
2. `./.venv/bin/pytest -q tests/test_meeting_task_store.py tests/test_planning_task_checkpoint_query.py tests/test_routes_agent_v3_planning_task_plane.py tests/test_routes_agent_v3_meeting_task_layer.py`
3. `./.venv/bin/pytest -q tests/test_export_planning_phase1_continuity_acceptance_pack.py tests/test_openclawbot_planning_task_plane_acceptance.py tests/test_meeting_task_store.py tests/test_planning_task_checkpoint_query.py tests/test_routes_agent_v3_planning_task_plane.py tests/test_routes_agent_v3_meeting_task_layer.py`

## 这批完成后代表什么

1. `W2` 从“能查到 checkpoint”继续推进到“查到时能看到统一 contract 元数据”
2. 七类 planning task 的 store 层 contract 已经被全量测试钉住
3. route / CLI 已经能看到 contract，但仍属于 runtime-visible metadata，不是执行性约束
4. exporter 的 identity 假阴性已经修掉，acceptance bundle 再次回到绿色

## 这批没有宣称的部分

1. 还没有把 `task_contract` 做成真正驱动行为的 engine
2. 还没有把 route / CLI 三层都做到七类 task 全量契约断言
3. 还没有进入 `W3 OpenClawBot material intake`
