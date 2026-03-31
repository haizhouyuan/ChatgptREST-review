# 2026-03-20 ChatgptREST API Service Recovery Walkthrough v1

## 做了什么

1. 先核对 `chatgptrest-api.service` 的状态与日志。
2. 核对 `/vol1/maint/ops/scripts/agent_activity_event.py` 的默认 telemetry mirror 候选。
3. 在 `maint` 仓里移除了过时的 `18713` 默认 fallback，并补了定向测试与文档。
4. 重新启动 `chatgptrest-api.service`。
5. 直接验证：
   - `/healthz`
   - `/v2/telemetry/ingest`
   - maint closeout mirror

## 关键结论

- `chatgptrest-api.service` 之前是 inactive，不是 crash loop。
- 之前 closeout 里看到的 `18713 404` 不是 telemetry route 消失，而是 GitNexus Express listener。
- 真正的恢复条件只有两个：
  - 不再默认打 `18713`
  - 把 `18711` 的 API 服务拉起来

## 验证结果

- `systemctl --user status chatgptrest-api.service` 显示 `active (running)`
- `ss -lntp | rg ':18711\\b'` 显示 Python 正在监听 `127.0.0.1:18711`
- `/healthz` 返回 `{"ok":true,"status":"ok"}`
- `/v2/telemetry/ingest` 返回 `200`
- maint closeout telemetry mirror 返回 `ok=true`
