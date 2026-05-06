# KB + Planning High-Quality Harness 统一执行计划 Codex方案 Walkthrough V4

Date: 2026-04-08

## 这次做了什么

这版 `walkthrough v4` 记录的是执行完成后的最后一轮收口，而不是再起新计划。

本轮最后真正发生的关键动作有 4 个：

1. 吸收评审意见，把 `claudeminmax` 的 `KB 治理 / 重新入库前质检 / data-quality sidecar` 正式写进统一计划
2. 把 `visit_cooperation_prep` live gate 从“单测能过、live 还没转绿”推进到真正全绿
3. 用统一 acceptance pack 把 `promotion inventory / phase10 / planning readiness / EvoMap vector / KB probe / feedback smoke / visit live gate / sidecar artifacts` 收进同一个证据目录
4. 用 `v4 plan + todo + completion + residual` 把这条主线冻结为后续实测 mouthpiece

## 最后的 blocker 是什么

最后一个真实 blocker 不是 KB，也不是 vector，而是 live OpenClaw ask 仍可能因为 wrapper 默认塞进来的 `planning_task_type=planning_general`，把 raw ingress 的 `visit_cooperation_prep` 强信号压掉。

表现为：

1. unit / API test 已经能命中 `visit_cooperation_prep`
2. live gate 却仍落到 `planning_general / funnel / web`

## 怎么解决的

修法没有扩范围，只做了一条窄策略：

1. 如果显式 profile 只是 generic `planning_general / business_planning`
2. 同时 raw ingress normalization 已经给出了更强的 `suggested_planning_profile`
3. 且当前还是 brand-new ask、没有已存在的 planning task binding

那就优先吃 raw ingress 的更强信号。

代码在：

- [scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py)

同时补了两层回归：

- [test_scenario_packs.py](/vol1/1000/projects/ChatgptREST/tests/test_scenario_packs.py)
- [test_routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3.py)

修完后，重启了：

- `chatgptrest-api.service`

然后再重跑 live gate，最终转绿。

## 最终收口

最终证据目录以这一次 unified acceptance 为准：

- [acceptance manifest](/vol1/1000/projects/ChatgptREST/artifacts/monitor/kb_planning_high_quality_harness_acceptance/20260408T123704Z/manifest.json)

它同时证明了：

1. `phase10` 全绿
2. planning readiness 全绿
3. EvoMap vector lane 可用
4. feedback smoke 可用
5. `visit_cooperation_prep` live gate 全绿
6. `claudeminmax` sidecar 证据已入包
