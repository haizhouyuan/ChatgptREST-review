# 2026-03-22 Phase 6 Heavy Execution Decision Gate Review v1

## 结论

`Phase 6` 的主裁决与蓝图是对齐的：

- `Work Orchestrator` 现在不该被扶正成新中心
- 当前更合理的定位仍是逻辑层 / 策略层，而不是新 daemon
- `planning` / `research` 两条主场景应继续优先于通用 heavy-execution 平台

这一点和 [2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md#L12)、[2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md#L313) 和 [2026-03-20_post_reconciliation_next_phase_plan_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_post_reconciliation_next_phase_plan_v2.md#L65) 的路线是一致的。

但这轮文档仍有 1 个实质性精度问题：

## Findings

### 1. “当前只保留显式 opt-in lane” 的表述过强，代码里仍存在隐式 route-based `team_execution`

Phase 6 文档在 [2026-03-22_heavy_execution_decision_gate_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-22_heavy_execution_decision_gate_v1.md#L16) 和 [2026-03-22_heavy_execution_decision_gate_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-22_heavy_execution_decision_gate_v1.md#L320) 把当前允许保留的 heavy execution 范围收成了：

- `gated experimental lane`
- `explicit opt-in path`

但 controller 运行面并不完全是“只有显式 opt-in 才会进 team”。

证据链：

- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L827) 的 `_resolve_execution_kind(...)` 先尊重 `scenario_pack.execution_preference`
- 这也是为什么 [test_controller_engine_planning_pack.py](/vol1/1000/projects/ChatgptREST/tests/test_controller_engine_planning_pack.py#L6) 能证明 canonical planning pack 在 `route=funnel` 时仍会落 `job`
- 但在没有 `scenario_pack` 的情况下，[engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L840) 仍会因为：
  - `route in {"funnel", "build_feature"}`
  - 或 `executor_lane == "team"`
  - 或 `stable_context.team/topology_id`
  直接返回 `team`

我本地直接复现：

- `route=build_feature, stable_context={}` -> `team`
- `route=funnel, stable_context={}` -> `team`
- `route=funnel, stable_context={"scenario_pack":{"execution_preference":"job"}}` -> `job`

这意味着当前更准确的说法应当是：

- canonical `planning / research` scenario pack 仍没有把 heavy execution 设为默认执行偏好
- 但 controller 仍保留一条隐式 route-based `team_execution` fallback
- 所以 heavy execution 不是“纯显式 opt-in”，而是“canonical 场景主线已避开，但 generic build/funnel 路由仍可进入”

评审判断：

- 这是中优先级精度问题
- 不推翻 `NO-GO` 主裁决
- 但会影响后续对当前系统行为边界的理解，尤其是“现在是否已经把 heavy execution 完全压回实验层”

建议修法：

- 如果要维持当前文档口径，就需要把 route-based `funnel/build_feature -> team` 也显式 gated 掉，只保留 `team/topology_id/executor_lane=team`
- 如果不改代码，就应把文档收窄成：
  - “canonical scenario 主线不默认走 heavy execution”
  - “generic build/funnel 仍保留隐式 team fallback”

## 通过项

以下主张我重新核过，结论成立：

- [cc_native.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py#L417) 的 `dispatch_team(...)` 是真实 team primitive，不是空壳
- [team_control_plane.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/team_control_plane.py#L125) 的 `TeamControlPlane` 是真实 durable ledger
- `/v2/advisor/cc-dispatch-team`、`/v2/advisor/cc-team-topologies`、`/v2/advisor/cc-team-runs`、`/v2/advisor/cc-team-checkpoints*` 在 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1251) 到 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1425) 确实存在并可用
- `codex_subagents.yaml` 当前角色 runtime 确实仍是单一 `codex_subagent`，见 [codex_subagents.yaml](/vol1/1000/projects/ChatgptREST/config/codex_subagents.yaml)
- canonical planning / research scenario pack 当前都固定 `execution_preference="job"`，见 [scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py#L382) 、[scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py#L427)、[scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py#L472)、[scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py#L520)

## 复核命令

我本轮实际复跑/复现了这些：

```bash
./.venv/bin/pytest -q \
  tests/test_controller_engine_planning_pack.py \
  tests/test_routes_advisor_v3_team_control.py
```

以及一条定向复现：

```bash
./.venv/bin/python - <<'PY'
from chatgptrest.controller.engine import ControllerEngine
engine = ControllerEngine({'cc_native': object()})
print(engine._resolve_execution_kind(route_plan={'route':'build_feature','executor_lane':''}, stable_context={}))
print(engine._resolve_execution_kind(route_plan={'route':'funnel','executor_lane':''}, stable_context={}))
print(engine._resolve_execution_kind(route_plan={'route':'funnel','executor_lane':''}, stable_context={'scenario_pack':{'execution_preference':'job'}}))
PY
```

结果分别是：

- `team`
- `team`
- `job`

## 总评

这轮可以签成：

- `Phase 6 NO-GO decision is blueprint-consistent`
- `existing team assets are real experimental assets`

还不能签成：

- `heavy execution is now only an explicit opt-in lane`

因为当前 controller 仍保留 generic `funnel/build_feature` 的隐式 team fallback。
