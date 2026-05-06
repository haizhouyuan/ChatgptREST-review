# 2026-03-15 OpenMind Controller Unification Walkthrough v2

## 本轮增量目标

在 v1 的统一 controller 骨架之上，本轮继续落实外部评审里我采纳的部分，但坚持复用现有仓库结构，不再平行新造第四套执行面。

这轮真正落下去的是三件事：

- 把 controller ledger 从 `request/job` 语义推进到更接近 `objective/run/step` 语义
- 把 `action` 和 `team` 两类路径接进 controller 主回路，而不是停在 route 内部
- 补 controller 自己的回读与状态对账，让 run snapshot 能反映外部 job 或 team run 的最新状态

## 具体改动

### 1. controller run 补齐 objective-first 字段

在 `chatgptrest/core/db.py` 与 `chatgptrest/controller/store.py` 上，给 `controller_runs` 增加并持久化了以下字段：

- `objective_text`
- `objective_kind`
- `success_criteria_json`
- `constraints_json`
- `delivery_target_json`
- `current_work_id`
- `blocked_reason`
- `wake_after`
- `plan_version`

这让 controller run 不再只是“某次 ask/advise 的快照”，而是能明确表达：

- 这次 run 想完成什么
- 现在卡在哪一步
- 完成判定是什么
- 下一步该做什么

同时修正了 `store.upsert_run(...)` 的更新语义，允许在 run 终态时显式清空 `current_work_id`，避免 terminal run 仍挂着旧 work item。

### 2. ask 热路径改成按 objective kind 选择 step executor

`chatgptrest/controller/engine.py` 现在会先构建 `objective_plan`，再决定执行类型：

- 普通问答路径：仍复用原有 job worker，但作为 controller-owned `execution` step 入账
- `action` 路径：转成 typed `effect_intent`
- `funnel`/显式 team 路径：转成 controller-owned `team_execution`

这样 route graph 的职责被进一步收敛为“规划和识别”，不再直接承担最终工作闭环。

### 3. action 路径不再假装已经完成

以前 `execute_action()` 的成功态更像“计划好了，但还没执行”。这轮把它接成 effect-intent step：

- 生成 `EffectIntent`
- 建立 blocking checkpoint
- run 进入 `WAITING_HUMAN`
- 产物进入 `controller_artifacts`

这样 controller 至少能明确表达“已经生成可执行意图，但执行前需要你确认”，而不是把 planning 伪装成 delivery。

### 4. team path 接进 controller 主回路

这轮没有重做 TeamControlPlane，而是直接复用现有 `cc_native.dispatch_team(...)`。

实际做法是：

- controller 先解析 topology / team spec
- 先把 `team_execution` 作为 submitted step 写入 ledger
- 再启动 team child executor
- team 执行结果通过 `_project_team_result(...)` 回写到同一个 controller run

这里还专门修了一处真实竞态：

- 如果 team 返回得非常快，旧实现会先写入结果，再被“submitted”的旧状态覆盖
- 现在改成先持久化 submitted，再启动 worker，避免快返回覆盖更近的状态

### 5. controller snapshot 增加外部状态对账

`get_run_snapshot()` 现在会先跑一轮 reconciliation：

- 如果 work item 挂的是 job_id，就回读 `job_store`
- 如果 work item 挂的是 team run，就回读 `TeamControlPlane`

这样 `/v2/advisor/run/{run_id}` 不再只是静态落盘数据，而是一个 controller-owned read model。

### 6. clean-base merge compatibility

在把这组提交移植到最新 `origin/master` 时，又补了两处基线兼容修正：

- 恢复 `chatgptrest/core/prompt_policy.py` 源文件，让 controller 与现有 job routes 继续共用同一套 prompt-policy 异常语义
- 把 effect-intent 评估从旧的 `advisor.graph.execute_action` 依赖改成 controller 内部 helper，避免 action 语义继续绑定到旧 graph 执行接口

## 新增和修复的测试

新增：

- `tests/test_controller_store.py`
  - 验证 objective-first 字段持久化
  - 验证 terminal run 会清空 `current_work_id`

扩展：

- `tests/test_advisor_v3_end_to_end.py`
  - objective-first ask 会生成 `objective_text/objective_kind/plan_version`
  - `action` route 会产出 `effect_intent` 并进入 `WAITING_HUMAN`
  - `team` route 会通过 child executor 写回 `team_run_id` 和 team artifact

## 验证结果

本轮执行并通过：

- `PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python -m py_compile chatgptrest/controller/store.py chatgptrest/controller/engine.py`
- `PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_controller_store.py tests/test_advisor_v3_end_to_end.py -k 'advise_round_trip or kb_direct_can_opt_in or action_route_returns_effect_intent or team_route_invokes_child_team_executor or objective_first_planned'`
- `PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py tests/test_controller_store.py tests/test_routes_advisor_v3_team_control.py tests/test_api_startup_smoke.py`

## 这轮没有做什么

仍然没有在这一轮里把下列能力一次性塞进去：

- standing goals
- 后台 heartbeat / wake scheduler
- 真正的 effect runtime 执行器
- controller 驱动的多模型策略层

这是刻意控制边界。当前这轮的目标是把 controller 从“统一入口骨架”推进到“objective-first 执行骨架”，先把控制语义做实，而不是继续摊大范围。

## 提交范围说明

本轮按仓库要求再次执行了 `gitnexus_detect_changes(scope="all")`，但结果仍然被主仓库其他脏改动污染，显示为整仓级 `critical`，不能直接代表当前 clean worktree 的真实提交范围。

本轮真实提交范围以当前 worktree 的 `git diff --stat` 为准，仅包含：

- `chatgptrest/controller/engine.py`
- `chatgptrest/controller/store.py`
- `tests/test_advisor_v3_end_to_end.py`
- `tests/test_controller_store.py`
- 本 walkthrough 文档
