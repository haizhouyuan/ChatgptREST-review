# 2026-03-21 Phase 2 Ingress Alignment Completion Verification v1

## 结论

`Phase 2: Ingress Alignment` 的主目标基本成立，但“可以完全写满”的程度还差一点。

更准确的判断是：

- OpenClaw plugin、Feishu WS、`/v2/advisor/advise` 这三处 live ingress alignment 主线已经真正接上 canonical `Task Intake Spec v2`
- 这轮通过的部分主要是 route / source / trace / identity / explicit `task_intake` 的显式化
- 但 payload 语义层还有两处残余精度问题，所以我不建议把 Phase 2 直接写成“完全 freeze、可无保留签字”

## Findings

### 1. OpenClaw plugin 对 planning 语义仍会显式降成 `general`

这轮最值得注意的 residual 是：OpenClaw plugin 现在会主动构造 `task_intake.scenario` 和 `output_shape`，但它自己的 `goalHint -> scenario` 映射仍然不覆盖 planning。

直接证据：

- `openclaw_extensions/openmind-advisor/index.ts:265`
- `openclaw_extensions/openmind-advisor/index.ts:300`
- `chatgptrest/advisor/task_intake.py:157`

当前实现里：

- `inferScenarioFromGoalHint(...)` 只覆盖 `research/report/code_review/image/repair`
- `buildTaskIntakePayload(...)` 会把这个结果直接写进 explicit `task_intake`
- server 侧 `build_task_intake_spec(...)` 对 caller-supplied `task_intake.scenario` 采取“有值即信任”的路径，不会再重新从 `goal_hint` 推 planning

我本地最小复现确认：

- 当 caller 已显式送入 `scenario=general` 且 `goal_hint=planning`
- 最终 canonical intake 仍然是 `scenario=general`、`output_shape=text_answer`

这不是 `research/report/code_review/image/repair` 的现成回归，但它说明 OpenClaw adapter 还没有把 planning 语义真正纳入 aligned payload。结合插件 README 里仍把 “structured planning” 列为推荐使用场景，这一点不能忽略。

### 2. `/v2/advisor/advise` 对 caller-supplied `task_intake.attachments` 仍是有损消费

阶段文档把 `/v2/advisor/advise` 描述成“真正消费 canonical intake”，这个说法在大部分字段上成立，但对 attachment-bearing intake 还不完全成立。

直接证据：

- `chatgptrest/api/routes_advisor_v3.py:509`
- `chatgptrest/api/routes_advisor_v3.py:523`
- `chatgptrest/advisor/task_intake.py:132`
- `chatgptrest/advisor/task_intake.py:201`

当前代码里：

- `/v2/advisor/advise` 调 `build_task_intake_spec(...)` 时把 `attachments=[]` 写死
- `build_task_intake_spec(...)` 的 `attachments` 字段来自调用参数，不来自 `raw_task_intake.attachments`

我本地最小复现确认：

- caller 提供 `task_intake.attachments=['/tmp/demo.txt']`
- builder 结果里 `attachments=[]`
- 只有 `available_inputs.files` 被保留下来

这不是当前 Feishu WS happy path 的阻断问题，因为 Feishu 当前本来没有附件上传语义。但从 contract 角度看，`/v2/advisor/advise` 目前还不能算“无损消费完整 canonical intake”。

## 已核实成立的部分

以下结论我已重新核实，成立：

- OpenClaw plugin 确实不再走 thin bridge，而是显式发送 `source/trace_id/attachments/task_intake`
- Feishu WS gateway 现在会显式发送 `source=feishu`、`trace_id=feishu-ws:*`、versioned `task_intake`
- `/v2/advisor/advise` 现在会消费 caller-supplied `task_intake`、把 canonical intake 写入 `context`、把 summary 写入 `request_metadata`
- `/v2/advisor/advise` 和 `/v2/advisor/ask` 对错误 `task_intake.spec_version` 都会 fail-closed 返回 `400`
- 这轮定向回归与 `py_compile` 我都复跑通过

## 评审判断

如果把 `Phase 2` 的验收定义为：

- live ingress adapter 已经显式接上 canonical intake
- OpenClaw / Feishu / advise lane 不再只靠 server 猜散字段

这轮可以通过。

如果把 `Phase 2` 的验收定义为：

- aligned ingress payload 语义已经对 planning / attachments 这类边界场景也完全收口

这轮还不能把口径写满。

所以我给这轮最准确的签字结论是：

- **live ingress alignment：通过**
- **payload semantics freeze：还有两处 residual**

## 本轮复跑核验

我重新执行并通过了：

```bash
./.venv/bin/pytest -q \
  tests/test_feishu_ws_gateway.py \
  tests/test_business_flow_advise.py \
  tests/test_routes_advisor_v3_task_intake.py \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_advisor_v3_end_to_end.py \
  -k 'advise or feishu or openclaw'

python3 -m py_compile \
  chatgptrest/advisor/feishu_ws_gateway.py \
  chatgptrest/api/routes_advisor_v3.py \
  tests/test_feishu_ws_gateway.py \
  tests/test_business_flow_advise.py \
  tests/test_routes_advisor_v3_task_intake.py \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_advisor_v3_end_to_end.py
```

另外，本地最小复现也确认了两处 residual：

- explicit `scenario=general` 会让 planning-ish OpenClaw request 保持 `general/text_answer`
- `raw_task_intake.attachments` 在 `/v2/advisor/advise` 这一条 builder path 里仍会被丢掉
