# 2026-04-11 Codex Assistant-First Ingress Proxy Readiness Review v1

## 结论

通过，但结论必须说准：

- **assistant-first ingress proxy capability 已建立**
- **Feishu/OpenClawBot 仍不是完全 production-green 的默认主入口**

也就是说，当前可以正式采用：

- 用户先把工作任务发给 Codex
- Codex 代理投递到 direct agent lane，并可同步 Feishu 通知

但不能说：

- 用户已经可以无差别把所有复杂工作任务直接交给 Feishu/OpenClawBot

## 已验证通过

### 1. 本地路径提升为附件的直连模式已修复

证据：

- `state/agent_sessions/agent_sess_c677928f83274c5d.json`

判断：

- 显式本地路径进入 direct lane 时，已能提升为 `attachments`
- provider 不再因为本地绝对路径 contract 缺失而直接报 `AttachmentContractMissing`

### 2. provider-visible prompt 本地路径泄漏已修复

证据：

- `tests/test_prompt_builder.py`
- `tests/test_run_openclawbot_feishu_proxy_turn.py`

判断：

- `available_inputs` / wake-up packet 中的本地 markdown link 与路径，已脱敏为 `name [local artifact]`
- 这是对 provider contract 的真实修复，不是文案层回避

### 3. Codex 可直接向用户 Feishu 发开始/结束通知

证据：

- `artifacts/monitor/openclawbot_feishu_proxy_turn/20260411T073542Z/feishu_notice_start.json`
- `artifacts/monitor/openclawbot_feishu_proxy_turn/20260411T073542Z/feishu_notice_final.json`

判断：

- 出站消息能力真实可用
- 后续可以把“我代投递、我代监控”作为正式操作姿势

## 未完全通过

### 1. synthetic Feishu ingress 仍然只能算 canary/debug

证据：

- `artifacts/monitor/openclawbot_feishu_proxy_turn/20260411T073320Z/inject.worker.stderr.log`
- `artifacts/monitor/openclawbot_feishu_proxy_turn/20260411T073422Z/inject.worker.stderr.log`

发现：

- worker 能成功把消息送进 `feishu-intake`
- transcript 中能看到生成 reply
- 但 final Feishu reply dispatch 仍可能出现 `HTTP 400`
- 同时伴随 OpenClaw config validation 噪声

判断：

- synthetic mode 已有真实信息增量
- 但还不够稳定，不应对外宣称为正式 primary ingress

### 2. direct agent lane 的“机械链路”比“任务质量”更稳定

证据：

- `artifacts/monitor/openclawbot_feishu_proxy_turn/20260411T073542Z/summary.json`

发现：

- direct lane 本身能建 session、能回写 final session、能发送 Feishu notices
- 但简单 planning smoke 仍可能在 advisor/web 执行层失败

判断：

- 这条链路适合作为 operator-controlled ingress
- 不适合被表述为“完全不需要人盯的自动第一入口”

## readiness 结论

### 适合现在就用的模式

- 用户先把工作消息发给 Codex
- Codex 代投递到 `direct_agent_v3`
- Codex 在必要时向同一 Feishu 用户发送开始/结束通知
- Codex 继续盯 transcript / session / receipt，并把问题收口给用户

### 不适合现在就用的模式

- 用户自行把复杂任务大量直接发给 Feishu/OpenClawBot
- 默认走 synthetic replay
- 把 direct lane 的任何 terminal session 都视作质量通过

## 结论一句话

当前真正可用的是：

- **Codex 作为第一入口的受控代理能力**

当前还不能直接声称：

- **Feishu/OpenClawBot 已经足够稳定，可以完全替代 Codex 成为第一入口**
