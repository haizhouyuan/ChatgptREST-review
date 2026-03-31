# 2026-03-11 Feishu WS Watchdog Activity Fix v1

## 背景

`chatgptrest-feishu-ws.service` 在长时间无人发消息时，会每分钟出现一次：

- `WebSocket stale for ... (>300s), forcing disconnect...`
- 随后 SDK 立即重连

这会把一个空闲但健康的 Feishu 长连接误判成死连接，造成无意义的断线重连。

## 根因

`FeishuWSGateway` 只在 `_on_message()` 收到业务消息时调用 `_touch_heartbeat()`。

但 Feishu SDK 的长连接在空闲期仍会有：

- 初始 `connect`
- ping / pong control frame

这些流量可以证明连接存活，却没有被 gateway 计入 heartbeat。结果就是：

- 连接长期空闲
- `self._last_event_ts` 长时间不更新
- watchdog 把健康连接误杀

## 修复

在 `chatgptrest/advisor/feishu_ws_gateway.py` 中新增 `_ActivityAwareWSClient`：

- 继承 `lark.ws.Client`
- 在 `_connect()` 成功后触发 activity callback
- 在 `_handle_control_frame()` 时触发 activity callback
- 在 `_handle_data_frame()` 时触发 activity callback

然后让 `FeishuWSGateway` 统一通过 `_build_ws_client()` 创建该 client，并把 callback 绑定到 `_touch_heartbeat()`。

这样 heartbeat 不再只依赖“收到用户消息”，而是依赖真实 WebSocket 活动。

## 验证

执行：

```bash
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_feishu_ws_gateway.py
python3 -m py_compile chatgptrest/advisor/feishu_ws_gateway.py tests/test_feishu_ws_gateway.py
systemctl --user restart chatgptrest-feishu-ws.service
```

结果：

- 回归测试通过
- 语法检查通过
- 服务重启后重新连上 Feishu
- 新连接在空闲观察窗口内未再出现原先那种“立即 stale + 自行重连”的循环

## 额外说明

我同时复核了 `openclaw-gateway.service` 的 `refresh_token_reused` 日志。

当前看到的报错都停留在 `2026-03-11 21:10:31 CST` 之前；在这之后的最新日志里没有继续出现同类报错。换句话说，这更像是我先前读到了历史报错，而不是它在当前时刻仍然持续复发。
