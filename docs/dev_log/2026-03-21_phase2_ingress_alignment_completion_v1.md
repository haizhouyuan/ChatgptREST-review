# 2026-03-21 Phase 2 Ingress Alignment Completion v1

## 1. 阶段结论

`Phase 2: Ingress Alignment` 这轮可以签字。

原因不是“所有 legacy 都没了”，而是 live ingress 里最关键的两条 adapter 已经被真正拉回 front-door contract：

- OpenClaw plugin -> `/v3/agent/turn`
- Feishu WS -> `/v2/advisor/advise`

两条入口现在都能显式发出 versioned `Task Intake Spec v2`，而不再完全依赖 server 侧从散字段推断。

## 2. 本轮完成了什么

### 2.1 OpenClaw plugin 不再是 thin bridge

[openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)

新增：

- `extractContextFiles(...)`
- `inferScenarioFromGoalHint(...)`
- `inferOutputShapeFromScenario(...)`
- `buildTaskIntakePayload(...)`

现在发给 `/v3/agent/turn` 的 body 会显式带：

- `source=openclaw`
- `trace_id`
- `attachments`
- `task_intake`

### 2.2 Feishu WS 不再只发 channel envelope

[feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py)

新增：

- `_build_advisor_api_payload(...)`

现在 Feishu WS 发给 `/v2/advisor/advise` 的 body 会显式带：

- `source=feishu`
- `trace_id=feishu-ws:{message_id}`
- `task_intake`

### 2.3 `/v2/advisor/advise` 真正接住 canonical intake

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)

`advise` 现在会：

- 统一消费 `task_intake`
- 把 canonical intake 注入 `context`
- 把 summary 注入 `request_metadata`
- 错误 spec version fail-closed

## 3. 这轮没有做什么

这轮没有把下面这些假装完成：

- 没迁 Feishu WS 到 `/v3/agent/turn`
- 没清掉 `/v1/advisor/advise`
- 没禁止所有 top-level scattered fields
- 没让所有 MCP/CLI mixed callers 都显式发 `task_intake`

所以 `Phase 2` 的签字含义是：

- **live ingress alignment complete**
- **legacy caller retirement not yet complete**

## 4. 回归结果

定向回归通过：

```bash
./.venv/bin/pytest -q tests/test_feishu_ws_gateway.py tests/test_business_flow_advise.py tests/test_routes_advisor_v3_task_intake.py tests/test_openclaw_cognitive_plugins.py tests/test_advisor_v3_end_to_end.py -k 'advise or feishu or openclaw'
python3 -m py_compile chatgptrest/advisor/feishu_ws_gateway.py chatgptrest/api/routes_advisor_v3.py tests/test_feishu_ws_gateway.py tests/test_business_flow_advise.py tests/test_routes_advisor_v3_task_intake.py tests/test_openclaw_cognitive_plugins.py tests/test_advisor_v3_end_to_end.py
```

## 5. 下一阶段入口

Phase 2 完成后，下一步不再是继续画 ingress 图，而是进入：

- `Phase 3: Planning Scenario Pack`

因为 front-door object 和 live ingress adapter 现在已经足够稳定，可以开始把 `planning` 做成真正的稳定场景包。
