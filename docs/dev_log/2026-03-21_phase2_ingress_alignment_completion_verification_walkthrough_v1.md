# 2026-03-21 Phase 2 Ingress Alignment Completion Verification Walkthrough v1

## 目标

独立核验 `Phase 2: Ingress Alignment` 的实现完成度，重点不是再重复“已经加了 `task_intake`”，而是检查：

- OpenClaw plugin 是否真的成了 canonical payload adapter
- Feishu WS 是否真的从 channel envelope 升级成 aligned ingress adapter
- `/v2/advisor/advise` 是否真的完整消费 aligned `task_intake`

## 本轮实际做的事

### 1. 先核对阶段提交与文档

确认阶段完成提交为：

- `21c80f2`

读取并核对：

- `docs/dev_log/2026-03-21_phase2_ingress_alignment_completion_v1.md`
- `docs/dev_log/2026-03-21_ingress_alignment_matrix_v1.md`
- `docs/dev_log/2026-03-21_public_vs_internal_ingress_payload_diff_v1.md`

### 2. 重新检查三处关键实现

逐个复核了：

- `openclaw_extensions/openmind-advisor/index.ts`
- `chatgptrest/advisor/feishu_ws_gateway.py`
- `chatgptrest/api/routes_advisor_v3.py`

其中最关键的问题不是“字段有没有出现”，而是：

- adapter 自己会不会把 canonical payload 提前钉错
- route 在消费 `task_intake` 时会不会有隐性丢字段

### 3. 核实 Phase 2 已经真正完成的部分

确认成立：

- OpenClaw plugin 现在显式发送 versioned `task_intake`
- Feishu WS gateway 现在显式发送 versioned `task_intake`
- `/v2/advisor/advise` 现在会把 canonical intake 写入 `context` 和 `request_metadata`
- wrong `spec_version` 现在能 fail-closed 成 `400`

这说明 `Phase 2` 的主线目标，也就是 live ingress alignment，已经落地。

### 4. 找到两个 remaining precision gaps

第一处是 OpenClaw planning residual：

- plugin 侧 `goalHint -> scenario` 的映射没有覆盖 planning
- 但 plugin 已经会显式发送 `task_intake.scenario`
- server 侧收到显式 `scenario` 后不会再替 caller 重推 planning

结果是：planning-ish 请求如果从 OpenClaw plugin 进入，当前仍可能被明确钉成 `general/text_answer`。

第二处是 `/v2/advisor/advise` attachment residual：

- route 调 builder 时把 `attachments=[]` 写死
- builder 不会读取 `raw_task_intake.attachments`

结果是：caller-supplied `task_intake.attachments` 在这条 lane 上目前仍是有损消费。

### 5. 复跑回归和语法检查

本轮重新执行并通过：

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

同时我还补做了两个最小复现：

1. 模拟 explicit `task_intake.scenario=general + goal_hint=planning`
2. 模拟 `raw_task_intake.attachments=['/tmp/demo.txt']`

两者都确认 residual 真实存在。

## 最终判断

我的最终判断不是“Phase 2 不通过”，而是：

- Phase 2 的核心目标已经通过
- 但 Phase 2 文档里“可以完全写满”的表达仍然偏强

如果下一步继续收尾，最自然的顺序会是：

1. 在 OpenClaw plugin 里把 planning 场景映射补齐，或在未识别场景时不要过早显式钉死 `scenario/output_shape`
2. 在 `/v2/advisor/advise` 这条 lane 上决定 attachment-bearing `task_intake` 是否要成为正式 contract；如果要，就把 attachment 消费补齐

## 产物

本轮新增：

- `docs/dev_log/2026-03-21_phase2_ingress_alignment_completion_verification_v1.md`
- `docs/dev_log/2026-03-21_phase2_ingress_alignment_completion_verification_walkthrough_v1.md`
