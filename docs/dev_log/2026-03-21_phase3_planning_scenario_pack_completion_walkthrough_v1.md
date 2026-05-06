# Walkthrough: Phase 3 Planning Scenario Pack v1

## 为什么这样做

Phase 1/2 已经把 canonical intake 和 ingress 对齐了，但 `planning` 仍然只是：

- 一个 `scenario` 值
- 一个 `task_template`
- 一些散落在 strategist / funnel 里的通用逻辑

这不足以支撑：

- 会议总结
- 业务规划
- 人力规划
- 面试记录/调查纪要

所以这轮没有去重写总 routing，而是单独加 `ScenarioPack` 作为 planning 的共享 policy layer。

## 实现顺序

1. 新增 `scenario_packs.py`
2. 在 `routes_agent_v3.py`、`routes_advisor_v3.py` 接入 pack 解析和应用
3. 让 `ask_strategist.py` 吃 pack，固定 clarify/evidence/review/output contract
4. 让 `prompt_builder.py` 吃 pack，支持 planning profile 的 template override
5. 让 `ControllerEngine` 吃 pack，固定 planning route / execution_preference
6. 让 `advisor graph` 和 `funnel_graph` 吃 pack
7. 补定向回归与相邻 ingress 回归

## 中间修正

开发中出现过两个边界问题，已经收口：

1. `business planning` 关键词一度把显式 `goal_hint=report` 也拉进 planning pack  
   现已修正：非 planning scenario 不会被 pack 覆盖。

2. `ControllerEngine.advise` 现在会把 `task_intake` 顶层透传给 advisor graph  
   原有 e2e 测试没有更新预期，已修成新的正确 contract。

## 最终结果

最终 `planning` 已经不是通用 heuristic 的附带产物，而是：

- 有 profile
- 有 acceptance
- 有 route
- 有 prompt contract
- 有 watch policy

的稳定场景包。
