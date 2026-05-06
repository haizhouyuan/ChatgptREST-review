# B8 Langfuse 环境变量持久化 — 运维记录

**日期**: 2026-03-01
**操作**: Langfuse 凭证自动加载（Python + systemd 双重保障）

## 原因
Langfuse 初始化 fail-open，缺凭证只打 `"Langfuse: disabled (missing credentials)"`。
使用 nohup/后台启动时不会自动继承 credentials.env，导致 trace 不上报。

## 做法

### 1. Python 自动加载（belt-and-suspenders）
`chatgptrest/observability/__init__.py` 新增 `_load_credentials_if_needed()`：
- 在模块 import 时自动从 `/vol1/maint/MAIN/secrets/credentials.env` 读取 `LANGFUSE_*` 变量
- 仅设置尚未存在的环境变量（不覆盖已有值）
- fail-open: 文件缺失或读取失败只记 debug 日志

### 2. Systemd Drop-in（13 个 chatgptrest 单元）
`~/.config/systemd/user/<unit>.service.d/10-langfuse.conf`：
```ini
[Service]
EnvironmentFile=-/vol1/maint/MAIN/secrets/credentials.env
Environment=LANGFUSE_TIMEOUT=15
Environment=LANGFUSE_SAMPLE_RATE=1.0
Environment=LANGFUSE_FLUSH_AT=20
Environment=LANGFUSE_FLUSH_INTERVAL=1
```

覆盖的单元：chatgptrest-api, chatgptrest-chrome, chatgptrest-driver, chatgptrest-guardian,
chatgptrest-maint-daemon, chatgptrest-mcp, chatgptrest-mihomo-delay, chatgptrest-monitor-12h,
chatgptrest-orch-doctor, chatgptrest-viewer-watchdog, chatgptrest-worker-repair,
chatgptrest-worker-send, chatgptrest-worker-wait

## 验证
```bash
# 1. 重载 systemd
systemctl --user daemon-reload

# 2. 启动服务（不手动 source）
PYTHONPATH=. .venv/bin/python -c "
from chatgptrest.api.app import create_app
import uvicorn
app = create_app()
uvicorn.run(app, host='0.0.0.0', port=18713, log_level='info')
"

# 3. 检查日志
grep "Langfuse:" /tmp/srv*.log
# 应输出：Langfuse: initialized (host=https://us.cloud.langfuse.com)

# 4. Langfuse Cloud UI 验证
# 登录 https://us.cloud.langfuse.com → Traces → 筛选最近 30 分钟
# 应能看到 advisor trace
```

## 回滚
```bash
# 删除 drop-in
for unit in ~/.config/systemd/user/chatgptrest-*.service.d; do
  rm -f "$unit/10-langfuse.conf"
done
systemctl --user daemon-reload

# Python 自动加载是 fail-open，删除 credentials.env 即可禁用
# 或者还原 observability/__init__.py（git checkout）
```

## 验证结果
- `Langfuse: initialized (host=https://us.cloud.langfuse.com)` ✅
- 4/4 场景测试通过 ✅
- 无需手动 source ✅
