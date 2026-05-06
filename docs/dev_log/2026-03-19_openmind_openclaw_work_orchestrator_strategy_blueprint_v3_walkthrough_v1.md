# 2026-03-19 OpenMind OpenClaw Work Orchestrator Strategy Blueprint v3 Walkthrough v1

## 1. Goal

产出一版比 `v2` 更具体、可实施、且基于代码现实的蓝图，并发布到钉钉供评审。

## 2. Why v2 Was Not Enough

`v2` 的主要问题有 3 个：

1. 低估了 `OpenClaw` 已有的 runtime 能力，把它压成了入口壳。
2. 没有充分承认“当前运行中的 OpenMind 主要实现其实在 ChatgptREST 里”。
3. 把 `Work Orchestrator` 说得太像一个即将新建的服务，容易重演 `cc-sessiond` 式中间层膨胀。

## 3. What Was Read

本轮重点阅读并对齐了以下实现面：

### OpenClaw

- `/vol1/1000/projects/openclaw/docs/concepts/architecture.md`
- `/vol1/1000/projects/openclaw/docs/concepts/session.md`
- `/vol1/1000/projects/openclaw/docs/tools/subagents.md`
- `/vol1/1000/projects/openclaw/src/agents/tools/sessions-spawn-tool.ts`
- `/vol1/1000/projects/openclaw/src/agents/subagent-registry.ts`
- `/vol1/1000/projects/openclaw/src/infra/heartbeat-runner.ts`
- `/vol1/1000/projects/openclaw/src/cron/service.ts`
- `/vol1/1000/projects/openclaw/src/gateway/openresponses-http.ts`
- `/vol1/1000/projects/openclaw/src/gateway/tools-invoke-http.ts`

### ChatgptREST / current OpenMind runtime

- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/funnel_graph.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py`
- `/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts`
- `/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/README.md`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/integrations/openclaw_adapter.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/team_control_plane.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py`

### Planning / research domain evidence

- `/vol1/1000/projects/planning/00_入口/总入口.md`
- `/vol1/1000/projects/planning/00_入口/当前版本总览.md`
- `/vol1/1000/projects/planning/00_入口/每次交互后的判断与核验简表.md`
- `/vol1/1000/projects/planning/00_入口/唯一口径底座.md`
- `/vol1/1000/projects/planning/docs/规划_Pro复审闭环工作流.md`
- `/vol1/1000/projects/planning/00_入口/研究主题索引.md`

### OpenMind standalone repo reality check

- `/vol1/1000/projects/openmind/README.md`
- `/vol1/1000/projects/openmind/openmind/`

## 4. Main Conclusions

### 4.1 OpenClaw should be promoted, not flattened

`OpenClaw` 已经具备：

- session source of truth
- gateway runtime
- subagent
- heartbeat/cron/webhook
- operator/control UI

所以它应该承担“持续在线、持续执行、持续盯运行态”的底座职责。

### 4.2 ChatgptREST currently hosts the practical OpenMind runtime

虽然系统身份叫 `OpenMind`，但当前真正跑起来的认知和 controller 主链主要在 `ChatgptREST advisor + controller`。

蓝图必须承认这个现实，否则会继续做“概念在一个仓库、运行在另一个仓库”的错位设计。

### 4.3 Work Orchestrator should not start as a new daemon

本轮最关键的架构收敛是：

- `Work Orchestrator` 先作为共享对象模型与策略层落地
- 不在 Phase 1 新建重服务
- 先统一 `Task Intake Spec / RunLink / WatchPolicy / ScenarioPack`

### 4.4 Requirement analysis stays, but bounded

保留 `Intake / Clarify / Scope`，但只对 `planning/research` 做强前门，不把它膨胀成独立大系统。

## 5. Deliverables

### Repo document

- `/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md`

### DingTalk publish

- manifest:
  - `/vol1/1000/projects/planning/docs/dingtalk_space_publish_20260319_101143.json`
- node link:
  - `https://alidocs.dingtalk.com/i/nodes/R4GpnMqJzGbpLbKEuqKa7yYR8Ke0xjE3`

## 6. Recommended Next Engineering Step

不要先做新服务。

先从下面 5 件里开始：

1. 在 `chatgptrest/advisor/task_spec.py` 里补 `TaskIntakeSpec`
2. 在 `chatgptrest/advisor/standard_entry.py` 里让前门真正输出结构化任务对象
3. 在 `chatgptrest/api/routes_agent_v3.py` 里接收并回传结构化 `task_spec`
4. 明确 `OpenClaw plugin -> /v3/agent/turn` 是唯一主 ingress
5. 先落 `PlanningPack` 与 `ResearchPack`
