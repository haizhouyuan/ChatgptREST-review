# 2026-03-22 Phase 6 Heavy Execution Decision Gate Review Walkthrough v1

## 我做了什么

1. 确认 `HEAD` 在 `84b78db`，worktree 干净
2. 对照 Phase 6 文档重新核对了这些真实资产：
   - `chatgptrest/kernel/cc_native.py`
   - `chatgptrest/kernel/team_control_plane.py`
   - `chatgptrest/controller/engine.py`
   - `chatgptrest/api/routes_advisor_v3.py`
   - `config/codex_subagents.yaml`
   - `config/team_topologies.yaml`
3. 回读了蓝图基线：
   - [2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md)
   - [2026-03-20_post_reconciliation_next_phase_plan_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_post_reconciliation_next_phase_plan_v2.md)
4. 复跑了与这轮最相关的测试
5. 做了 controller `execution_kind` 的定向复现

## 关键核验结果

### 蓝图方向一致

Phase 6 的 `NO-GO` 主裁决与 blueprint v3 是一致的：

- 不扶正新 daemon
- 先把 `planning / research` 场景主线做稳
- `Work Orchestrator` 仍应停留在逻辑层 / 策略层判定，而不是新中心

### 现有 team 资产确实是真资产

- `dispatch_team(...)` 不是空壳
- `TeamControlPlane` 不是空壳
- `/cc-team-*` control surface 也是真的

### 发现的问题

Phase 6 文档把当前 heavy execution 收成了“显式 opt-in path”，但 controller 还保留一条隐式 fallback：

- 如果没有 `scenario_pack.execution_preference`
- 且 route 是 `funnel` 或 `build_feature`
- 并且 `cc_native` 已注入

那么 `_resolve_execution_kind(...)` 仍会直接返回 `team`

所以当前更准确的行为边界是：

- canonical planning/research 主线不默认走 team
- 但 generic build/funnel 仍可能隐式进入 team lane

## 复跑记录

```bash
./.venv/bin/pytest -q \
  tests/test_controller_engine_planning_pack.py \
  tests/test_routes_advisor_v3_team_control.py
```

结果：

- 全通过

## 定向复现

```bash
./.venv/bin/python - <<'PY'
from chatgptrest.controller.engine import ControllerEngine
engine = ControllerEngine({'cc_native': object()})
print(engine._resolve_execution_kind(route_plan={'route':'build_feature','executor_lane':''}, stable_context={}))
print(engine._resolve_execution_kind(route_plan={'route':'funnel','executor_lane':''}, stable_context={}))
print(engine._resolve_execution_kind(route_plan={'route':'funnel','executor_lane':''}, stable_context={'scenario_pack':{'execution_preference':'job'}}))
PY
```

结果：

- `build_feature_no_optin -> team`
- `funnel_no_optin -> team`
- `funnel_pack_job -> job`

## 落盘原因

这轮不是代码修复，而是阶段性核验与评审。需要把“主裁决与蓝图一致，但当前 runtime 还没有完全收成纯显式 opt-in team lane”单独落档，避免后续误判系统现状。
