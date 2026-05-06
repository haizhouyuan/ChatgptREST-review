# 2026-03-20 Post-Reconciliation Next Phase Plan Walkthrough v2

## 为什么要重写

`v1` 的顺序没有错，但它还是 authority freeze 之前的视角。现在 authority、front door、session truth、telemetry 以及 API 恢复都已经做完了，再沿用 `v1` 会把已经完成的事继续写成“未来任务”。

所以这次 `v2` 的重点不是新增观点，而是：

- 把已完成项从“待办”里移出去
- 把真正还没做的 implementation gap 排序
- 把 planning / research 两个主场景抬成后续唯一主线

## 参考了哪些材料

- `authority_matrix_v2`
- `knowledge_authority_decision_v2`
- `routing_authority_decision_v2`
- `front_door_contract_v2`
- `session_truth_decision_v3`
- `telemetry_contract_fix_v1`
- 刚完成的：
  - `agent_v3_facade_telemetry_bridge_v1`
  - `chatgptrest_api_service_recovery_v1`

## v2 最大变化

### 从 Phase 0 转成 Implementation Phase

`v1` 里：

- `Authority Freeze`
- `Front Door Contract Freeze`
- `Runtime Host Recovery`

还是主任务。

`v2` 里它们已经变成已完成或已基本完成前提，后面真正该做的是：

1. `Front Door Object Freeze`
2. `Ingress Alignment`
3. `Planning Scenario Pack`
4. `Research Scenario Pack`
5. `Knowledge Runtime Rebalance`
6. `Heavy Execution Decision Gate`

### 把 heavy execution 再次后移

这次没有再让 “Work Orchestrator / heavy execution” 抢前排。

原因很明确：

- 你的真实主战场仍然是 `planning + research`
- 现在最缺的是对象统一、入口统一、场景包统一
- 不是新的 runtime 服务

## 当前可以直接开干的第一批交付物

- `front_door_object_contract_v1`
- `task_intake_spec_v1.json`
- `entry_adapter_matrix_v1`
- `ingress_alignment_matrix_v1`

这四个做出来之后，后面的 `planning / research scenario pack` 才有稳定地基。
