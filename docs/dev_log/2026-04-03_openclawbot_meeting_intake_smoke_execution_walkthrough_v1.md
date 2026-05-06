# 2026-04-03 OpenClawBot Meeting Intake Smoke Execution Walkthrough v1

## 1. 这轮做了什么

这轮不是继续写复盘文档，而是把 `Step 0A / B1 / B2` 真跑成可执行证据。

执行顺序是：

1. 先把 `Feishu/OpenClawBot` transport capture 固化成 smoke
2. 再把 `openmind-advisor` bridge contract 固化成 capture smoke
3. 再做 canonical main-path smoke
4. 根据失败结果逐步补代码
5. 每补一刀都重跑 smoke 和定向回归

## 2. 一开始观测到的真实断点

最初的 smoke 不是 `4/4`，而是暴露了两类硬问题：

1. `MediaPaths` 没有进入 `attachments`
2. runtime identity 没有进入 canonical main path 的 `/v3/agent/turn` body / task_intake

## 3. 第一轮修复

先改了 ChatgptREST 里的 `openmind-advisor`：

1. 允许从 `MediaPath / MediaPaths` 提取附件
2. 允许从 `context` 里恢复 `openclaw_*` identity 字段

这样把结果先从 `2/4` 拉到了 `3/4`。

## 4. 第二轮修复

然后确认剩余问题不在 ChatgptREST，而在 OpenClaw 主链：

1. `buildPluginToolContext()` 里其实已经有 identity
2. 但 plugin tool execute 的真实 custom-tools 路径没有把这些 identity 投影给插件

所以在 OpenClaw 侧做了最小适配：

1. 在 `resolvePluginTools()` 阶段，把 runtime identity 注入到 `params.context`
2. 加了一条回归测试，证明 plugin tool execute 前确实会收到这批字段

## 5. 第三轮修正

随后发现 smoke harness 自己也有装配偏差：

1. 一度绕开了 `resolvePluginTools()`
2. 一度误吃了本机旧 `~/.openclaw/openclaw.json`
3. 一度只复制了 `index.ts`，没有复制完整 plugin 目录

最后把 harness 修正为：

1. 走 `resolvePluginTools() -> toToolDefinitions()`
2. 用隔离 `HOME`
3. 用完整 plugin 目录快照

## 6. 最终结果

最终 `report_v1` 变成：

1. `feishu_transport_media_capture`: PASS
2. `dynamic_contract_capture`: PASS
3. `canonical_main_path_runtime_identity_projection`: PASS
4. `canonical_main_path_media_projection`: PASS

证据路径：

1. [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_meeting_intake_smoke_20260403/report_v1.md)
2. [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_meeting_intake_smoke_20260403/report_v1.json)

## 7. 这轮改到的代码

ChatgptREST：

1. [openmind-advisor](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
2. [openclawbot_meeting_intake_smoke.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/openclawbot_meeting_intake_smoke.py)
3. [run_openclawbot_meeting_intake_smoke.py](/vol1/1000/projects/ChatgptREST/scripts/run_openclawbot_meeting_intake_smoke.py)
4. [test_openclawbot_meeting_intake_smoke.py](/vol1/1000/projects/ChatgptREST/tests/test_openclawbot_meeting_intake_smoke.py)
5. [test_openclaw_cognitive_plugins.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py)

OpenClaw：

1. `/vol1/1000/projects/openclaw/src/plugins/tools.ts`
2. `/vol1/1000/projects/openclaw/src/plugins/tools.optional.test.ts`

## 8. 这轮跑过的验证

ChatgptREST：

1. `python3 -m py_compile chatgptrest/eval/openclawbot_meeting_intake_smoke.py scripts/run_openclawbot_meeting_intake_smoke.py tests/test_openclawbot_meeting_intake_smoke.py`
2. `./.venv/bin/pytest -q tests/test_openclawbot_meeting_intake_smoke.py tests/test_openclaw_dynamic_replay_gate.py tests/test_openclaw_cognitive_plugins.py`
3. `PYTHONPATH=. ./.venv/bin/python scripts/run_openclawbot_meeting_intake_smoke.py`

OpenClaw：

1. `corepack pnpm -C /vol1/1000/projects/openclaw exec vitest run src/plugins/tools.optional.test.ts src/agents/openclaw-tools.plugin-context.test.ts src/agents/pi-tool-definition-adapter.test.ts`

## 9. 这一轮结束后，计划怎么变

计划口径从：

> 先证明入口链到底通不通

变成：

> 入口链已经通过 Step 0，可以进入 `会议沉淀` 的 phase-1 最小生产切片
