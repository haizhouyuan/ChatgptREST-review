# 2026-04-11 Codex Assistant-First Ingress Proxy Walkthrough v1

## 背景

用户要求把交互姿势切成：

- 用户先把工作任务发给 Codex
- Codex 再代发到 Feishu / OpenClawBot 入口
- Codex 持续监控执行结果

目标不是继续要求用户自己试错 Feishu 入口，而是把 Codex 变成第一入口，直到下游入口跑过足够多任务且稳定。

## 本轮代码改动

### 1. provider-visible prompt 路径脱敏

改动文件：

- `chatgptrest/advisor/prompt_builder.py`
- `tests/test_prompt_builder.py`

做法：

- 为 `available_inputs` / wake-up packet 增加本地路径和 markdown link 脱敏
- 将绝对路径转换为 `name [local artifact]`

原因：

- 之前 direct agent lane 在显式本地文件路径场景下会因为 provider-visible payload 不干净而触发 attachment contract 类错误

### 2. 新增 Codex first-ingress proxy runner

改动文件：

- `ops/run_openclawbot_feishu_proxy_turn.py`
- `tests/test_run_openclawbot_feishu_proxy_turn.py`

做法：

- 默认 transport 改为 `direct_agent_v3`
- synthetic Feishu replay 保留为 canary/debug transport
- 显式本地路径自动提升为 `attachments`
- 消息中的绝对路径重写为 `[attached]`
- 增加 Feishu 开始/结束通知能力
- 增加 transcript/receipt/session 汇总输出

### 3. 新增 synthetic ingress helper

改动文件：

- `ops/openclawbot_feishu_proxy_inject.ts`

做法：

- 允许 Python runner 以 parent controller 方式启动 synthetic ingress worker
- 先落 `inject_result.json`
- 再 detached background dispatch

原因：

- 之前 synthetic replay 在 parent process 结束前拿不到稳定证据，不利于 monitor 和 fail-closed 总结

## 关键验证

### 1. focused tests

命令：

```bash
./.venv/bin/pytest -q tests/test_prompt_builder.py tests/test_run_openclawbot_feishu_proxy_turn.py
```

结果：

- `21 passed`

### 2. direct lane + 本地文件提升

证据：

- `state/agent_sessions/agent_sess_c677928f83274c5d.json`

结论：

- 证明附件提升和 provider contract 修正有效

### 3. synthetic ingress

证据：

- `artifacts/monitor/openclawbot_feishu_proxy_turn/20260411T073320Z/`
- `artifacts/monitor/openclawbot_feishu_proxy_turn/20260411T073422Z/`

结论：

- ingress receipt 和 worker spawn 已稳定
- worker 确实能把消息送入 `feishu-intake`
- 但 final Feishu reply 仍可能 `400`

### 4. direct lane + Feishu notices

证据：

- `artifacts/monitor/openclawbot_feishu_proxy_turn/20260411T073542Z/`

结论：

- Codex 可主动给用户 Feishu 发 start/final notice
- direct lane 机械链路可用
- 但业务任务本身仍可能在 advisor/web execution 层失败

## 最终操作口径

本轮后冻结的真实口径是：

1. 用户先把工作任务发给 Codex
2. Codex 选择 `direct_agent_v3` 作为默认代理模式
3. 若需要用户侧可见性，Codex 额外发 Feishu 开始/结束通知
4. synthetic Feishu ingress 仅在需要调试 live OpenClawBot path 时使用

## 未解决项

1. synthetic ingress worker 的 OpenClaw config validation 噪声
2. synthetic ingress final Feishu reply `400`
3. direct agent lane 的 advisor/web execution 任务成功率还未达到可无人值守口径

## 结论

这轮不是把 Feishu/OpenClawBot 宣称为全绿主入口，而是把：

- **Codex assistant-first ingress proxy**

正式做成一个可用能力，并把它纳入了受控运维与文档口径。
