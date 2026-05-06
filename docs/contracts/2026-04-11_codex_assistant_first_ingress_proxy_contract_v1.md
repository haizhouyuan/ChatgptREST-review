# 2026-04-11 Codex Assistant-First Ingress Proxy Contract v1

## 目标

冻结一条可操作的工作入口：

- 用户先把工作任务发给 Codex
- Codex 作为第一入口进行投递、监控、回报
- Feishu / OpenClawBot 暂时作为下游执行与观测面，而不是用户的默认主入口

这份 contract 不宣称 `OpenClawBot` 已经完全 production-green。它冻结的是一条 **assistant-first proxy** 运维能力。

## 范围

当前覆盖：

- ChatgptREST public advisor-agent / `/v3/agent/turn` 直连投递
- Codex 代发 Feishu 开始/结束通知
- 受控 synthetic Feishu ingress replay（仅 canary/debug）
- 本地显式文件路径自动提升为 attachments
- provider-visible prompt 中的本地路径脱敏

当前不覆盖：

- 把 Feishu/OpenClawBot 直接作为零风险 primary ingress
- synthetic Feishu replay 的正式生产使用
- 任意文件系统代理或 unrestricted shell execution

## 入口模式

### 1. 默认模式：`direct_agent_v3`

默认 transport 是：

- `direct_agent_v3`

该模式：

- 直接调用 ChatgptREST `/v3/agent/turn`
- 可选向同一 Feishu open_id 发送开始/完成通知
- 允许把消息中的显式本地文件路径提升成 `attachments`
- 是当前 assistant-first ingress 的正式默认模式

### 2. 调试模式：`synthetic_feishu_ingress`

仅用于：

- live path canary
- 调试 `feishu-intake`
- 验证 transcript / receipt / reply dispatch

该模式不作为默认生产路径。若出现 replay worker config validation 噪声或 final reply `400`，按 fail-closed 处理，不对用户宣称链路已绿。

## 输入 contract

Codex 代理投递时，消息输入遵循：

1. 用户消息原文作为主 message
2. 消息中显式存在且真实可读的本地文件路径：
   - 自动提升为 `attachments`
   - 在 provider-visible message 中重写为 `name [attached]`
3. wake-up packet / available_inputs 中出现的本地路径：
   - 必须脱敏为 `name [local artifact]`
   - 不得把 `/vol1/...`、`/tmp/...` 等绝对路径直接暴露给 provider

## 输出 artifact contract

每次代理投递至少产出：

- `summary.json`
- `report.md`

视 transport 不同，可附加：

- `direct_turn.json`
- `direct_turn_error.txt`
- `final_session.json`
- `transcript.json`
- `receipts.json`
- `feishu_notice_start.json`
- `feishu_notice_final.json`
- `inject_result.json`
- `inject.worker.stdout.log`
- `inject.worker.stderr.log`

默认 artifact 根目录：

- `artifacts/monitor/openclawbot_feishu_proxy_turn/<timestamp>/`

## 当前 readiness 口径

### 可依赖的部分

- Codex 可主动向用户 Feishu 发送开始/结束通知
- `direct_agent_v3` 模式可稳定建立 ChatgptREST session 并返回 terminal session snapshot
- 显式本地路径提升为 attachments 已修复 `AttachmentContractMissing` 类问题
- provider-visible prompt 本地路径泄漏已被收敛

### 未宣称已绿的部分

- synthetic Feishu ingress replay
- `feishu-intake` live path 的最终 reply dispatch 稳定性
- 任意工作 ask 在 advisor/web lane 中都稳定成功

## 使用口径

正式口径：

- 用户把工作任务先发给 Codex
- Codex 选择合适 transport 并执行
- Codex 回报监控结果与产物

不推荐口径：

- 直接把 Feishu/OpenClawBot 当作默认 primary ingress 大量投递复杂任务

## Fail-closed 规则

以下情况不宣称成功：

1. direct turn 无 terminal session
2. synthetic ingress 只有 transcript evidence、但 final reply 发送失败
3. provider-visible payload 仍暴露本地绝对路径
4. 只发送了 Feishu 开始/结束通知，但真正任务 session 失败或无 answer

## 证据

本 contract 主要基于以下证据冻结：

- `artifacts/monitor/openclawbot_feishu_proxy_turn/20260411T073320Z/`
- `artifacts/monitor/openclawbot_feishu_proxy_turn/20260411T073422Z/`
- `artifacts/monitor/openclawbot_feishu_proxy_turn/20260411T073542Z/`
- `state/agent_sessions/agent_sess_c677928f83274c5d.json`
