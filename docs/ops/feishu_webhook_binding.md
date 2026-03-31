# P1-3: 飞书 Webhook 绑定指南

## 1. 在飞书开发者后台注册 webhook

1. 登录 [飞书开发者后台](https://open.feishu.cn/app)
2. 进入你的应用 → **事件订阅**
3. 配置 **请求网址（Request URL）**：

```
https://yogas2.tail594315.ts.net/v2/advisor/webhook
```

> 如果使用 nginx 反向代理（见 `ops/nginx_openmind.conf`）：
> `http://yogas2:80/v2/advisor/webhook`

4. 获取 **Encrypt Key** 和 **Verification Token**：
   - Encrypt Key → 当前代码暂不使用（FeishuHandler 已预留）
   - Verification Token → 用于消息签名验证

5. 在 **添加事件** 中勾选：
   - `im.message.receive_v1`（接收消息）
   - `im.message.message_read_v1`（可选：已读回调）

## 2. 配置 FEISHU_WEBHOOK_SECRET

将飞书后台的 **Encrypt Key** 设置为 `FEISHU_WEBHOOK_SECRET` 环境变量。

### 方法 A：credentials.env（推荐）

编辑 `/vol1/maint/MAIN/secrets/credentials.env`，追加：

```bash
FEISHU_WEBHOOK_SECRET=你的encrypt_key值
```

Python 模块会自动加载（与 Langfuse 凭证相同机制）。

### 方法 B：systemd drop-in

```bash
# 复制模板
mkdir -p ~/.config/systemd/user/chatgptrest-api.service.d/
cp ops/systemd-drop-ins/11-feishu.conf ~/.config/systemd/user/chatgptrest-api.service.d/
# 编辑：替换 %FEISHU_WEBHOOK_SECRET_VALUE% 为实际值
vi ~/.config/systemd/user/chatgptrest-api.service.d/11-feishu.conf
systemctl --user daemon-reload
systemctl --user restart chatgptrest-api.service
```

## 3. 验证

```bash
# 检查 webhook endpoint 可达
curl -s -X POST http://127.0.0.1:18713/v2/advisor/webhook \
  -H "Content-Type: application/json" \
  -d '{"challenge":"test_challenge"}' | python3 -m json.tool

# 飞书开发者后台也会发送一个 challenge 验证请求
```

## 4. 回调 URL 类型

| 场景 | URL |
|------|-----|
| Tailscale 内网 | `https://yogas2.tail594315.ts.net/v2/advisor/webhook` |
| 公网（需 nginx+TLS） | `https://your-domain/v2/advisor/webhook` |
| 本地测试 | `http://127.0.0.1:18713/v2/advisor/webhook` |
