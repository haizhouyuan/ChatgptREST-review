# 2026-04-03 OpenClawBot Meeting Intake Smoke Execution Review v1

## 1. 结论

`Step 0A / B1 / B2` 现在已经被实际代码与可执行 smoke 证据补成 `4/4`。

这意味着：

1. `Feishu -> OpenClawBot` 能接住会议材料并落盘媒体
2. `openmind-advisor` bridge 本体能正确组出 `/v3/agent/turn` contract
3. canonical `OpenClawBot -> customTools` 主链现在也能把：
   - runtime identity
   - `MediaPaths`
   正确投影到 `openmind-advisor`
4. 第一阶段 `会议沉淀` 入口链已经从“可疑假设”升级成“已执行验证”

## 2. 这次真正修掉了什么

### 2.1 ChatgptREST 侧

`openmind-advisor` 不再只认极窄的 `context.files / context.attachments`。

现在它还能从 `context` 里恢复：

1. `MediaPath / MediaPaths`
2. `openclaw_session_key / openclaw_account_id / openclaw_thread_id / openclaw_agent_id`
3. `session_key / account_id / thread_id / agent_id`

因此即使 OpenClaw 主链不给 execute 第三个参数可靠 runtime ctx，bridge 也能从 `params.context` 里恢复 identity 与附件。

关键文件：

1. [openmind-advisor](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)

### 2.2 OpenClaw 侧

`resolvePluginTools()` 现在会在 plugin tool execute 前，把 runtime identity 注入到 `params.context`。

注入字段是：

1. `openclaw_session_key`
2. `openclaw_account_id`
3. `openclaw_thread_id`
4. `openclaw_agent_id`
5. 以及对应的 `session_key / account_id / thread_id / agent_id`

这一步的价值是：

1. 不需要把 `publicagentmcp` 继续做大
2. 不需要在 OpenClaw 适配器里做大范围重构
3. plugin tools 可以在真实主链里恢复到稳定 runtime identity

关键文件：

1. `/vol1/1000/projects/openclaw/src/plugins/tools.ts`
2. `/vol1/1000/projects/openclaw/src/plugins/tools.optional.test.ts`

## 3. Step 0 证据

实际 smoke 报告：

1. [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_meeting_intake_smoke_20260403/report_v1.md)
2. [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_meeting_intake_smoke_20260403/report_v1.json)

当前冻结结果：

1. `feishu_transport_media_capture`: PASS
2. `dynamic_contract_capture`: PASS
3. `canonical_main_path_runtime_identity_projection`: PASS
4. `canonical_main_path_media_projection`: PASS

## 4. 为什么这次的 PASS 可信

这轮不是只修产品代码，也修了 smoke harness 本身，避免再次拿“伪主链”当结论。

最终 smoke 的主链验证具备这几个条件：

1. 走 `OpenClaw resolvePluginTools()`
2. 再走 `toToolDefinitions()`
3. 使用隔离 `HOME`，避免本机 `~/.openclaw/openclaw.json` 污染
4. 使用完整 plugin 目录快照，而不是只拷一份 `index.ts`

也就是说，这次的 `B2 PASS` 不是手工注入的桥接假象，而是接近真实 canonical path 的结果。

## 5. 当前最准确的总判断

现在应该把口径改成：

> `Feishu/OpenClawBot -> openmind-advisor -> /v3/agent/turn` 这条会议沉淀入口链已经通过 transport / bridge / canonical-main-path 三层 gate，可以进入 phase-1 第一条生产切片实施。

## 6. Next

`Step 0` 已经完成，下一步不再继续讨论“入口链到底通不通”，而是直接进入：

1. `会议沉淀` phase-1 最小生产切片实施规格
2. `task_id + checkpoint sidecar` 的最小落地
3. 再由 `claudegac` 做严格代码红队审核
