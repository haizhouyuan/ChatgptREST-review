# 2026-03-21 Task Intake Phase2 Gap Fixes v1

## 1. 为什么要补这一轮

`Phase 2` 第一轮完成后，review 指出了两个剩余精度问题：

1. OpenClaw plugin 会把未覆盖的 `goal_hint` 预先压成 `scenario=general`
2. `task_intake.attachments` 在 `/v2/advisor/advise` 路径上仍是有损消费

这两个点都不是“文档措辞问题”，而是 canonical intake 的真实语义缺口。

## 2. 独立判断

### 2.1 `planning` 不能只在 adapter 里硬编码

如果只把 OpenClaw plugin 的 mapping 补一个 `planning`，问题会暂时消失，但下次再来新的 `goal_hint` 还是会被 adapter 提前压成 `general`。

所以正确修法是两层一起做：

- canonical builder 认 `goal_hint=planning`
- OpenClaw plugin 对未冻结 hint 不再默认写死 `scenario=general`

### 2.2 attachments 应该在 canonical builder 收口

`/v2/advisor/advise` 写死 `attachments=[]` 暴露了问题，但真正根因在
[task_intake.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_intake.py)：

- `build_task_intake_spec(...)` 只吃调用参数里的 `attachments`
- 不吃 caller-supplied `raw_task_intake.attachments`

所以正确修法也应该在 builder，而不是只给某一条 route 打补丁。

## 3. 实际修复

### 3.1 canonical builder

[task_intake.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_intake.py)

新增/修改：

- `_infer_scenario(...)` 现在显式识别：
  - `planning`
  - `implementation_planning`
- `build_task_intake_spec(...)` 不再只吃调用参数 `attachments`
- 新增 `_merge_attachment_inputs(...)`
  - 会把 top-level `attachments`
  - 和 caller-supplied `raw_task_intake.attachments`
  - 合并成 canonical `attachments`

### 3.2 OpenClaw plugin

[openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)

修改：

- `inferScenarioFromGoalHint(...)` 现在识别 `planning`
- 对未识别的 hint 返回 `null`，不再默认返回 `general`
- `buildTaskIntakePayload(...)` 只在有明确 scenario 时才写：
  - `scenario`
  - `output_shape`

这样 future hints 不会再被 adapter 提前压死。

## 4. 回归

补了 3 组关键断言：

- [tests/test_task_intake.py](/vol1/1000/projects/ChatgptREST/tests/test_task_intake.py)
  - `planning` goal hint -> `planning / planning_memo`
  - `raw_task_intake.attachments` 保留
- [tests/test_routes_advisor_v3_task_intake.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_advisor_v3_task_intake.py)
  - `/v2/advisor/advise` 路径上 attachments 保留
- [tests/test_openclaw_cognitive_plugins.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py)
  - plugin source 断言不再允许默认 `general` 压缩

## 5. 修正后的结论

这轮之后，`Phase 2` 的结论可以写得更硬一些：

- live ingress adapter 已对齐 canonical intake
- payload semantics 不再因为 OpenClaw default-general 或 advise attachment loss 而继续漏损

仍然保留的边界只有 legacy / migration 类问题，不再是 canonical payload 本身的问题。
