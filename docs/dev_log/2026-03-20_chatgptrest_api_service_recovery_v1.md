# 2026-03-20 ChatgptREST API Service Recovery v1

## 背景

在前面的 telemetry authority / contract 收口后，运行面仍有两个残留：

- `chatgptrest-api.service` 处于 `inactive (dead)`
- maint closeout / agent activity mirror 仍然报：
  - `18711 connection refused`
  - `18713 /v2/telemetry/ingest -> 404`

本次目标是把运行面恢复到 canonical telemetry seam 可用的状态。

## 实际发现

1. `chatgptrest-api.service` 不是 crash / start-limit-hit，而是自 `2026-03-19 03:57 CST` 起一直处于 inactive。
2. `127.0.0.1:18713` 当前实际由 GitNexus Express 服务占用，不再是 telemetry host。
3. `agent_activity_event.py` 默认 mirror 候选还包含 `18713`，会把真实问题伪装成“双端口异常”。

## 本次收口

### 1. maint 侧默认 fallback 修正

`/vol1/maint/ops/scripts/agent_activity_event.py` 的默认 telemetry mirror 候选已收敛为：

- `http://127.0.0.1:18711/v2/telemetry/ingest`

不再默认回退到 `18713`。

### 2. API service 恢复

执行：

```bash
systemctl --user start chatgptrest-api.service
```

恢复后状态：

- `chatgptrest-api.service = active (running)`
- `127.0.0.1:18711` 已监听

### 3. live 验证

健康检查：

```bash
curl -fsS http://127.0.0.1:18711/healthz
```

返回：

```json
{"ok":true,"status":"ok"}
```

telemetry ingest 探针：

- `POST http://127.0.0.1:18711/v2/telemetry/ingest`
- 返回 `200`
- body:

```json
{"ok":true,"trace_id":"trace-telemetry-recovery-1","recorded":1,"signal_types":["agent.task.closeout"]}
```

### 4. closeout 镜像验证

对 `/vol1/maint` 执行 closeout 后，telemetry mirror 结果已变成：

- `url = http://127.0.0.1:18711/v2/telemetry/ingest`
- `ok = true`
- `status = 200`
- `attempts = 1`

## 当前状态

本轮之后，telemetry 运行面已经从：

- `18711 refused`
- `18713 404`

收口到：

- `18711 = canonical telemetry seam, healthy`
- `18713 = GitNexus, 不再参与默认 telemetry mirror`

## 未做

本次没有处理：

- `chatgptrest-api.service` 为什么在 `2026-03-19 03:57` 被停掉的流程来源
- advisor / facade 更大范围的运行面自愈策略

这两项属于后续运维治理，不影响当前 telemetry 主链恢复。
