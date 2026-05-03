# Agent 代理流量避坑指南 — ChatgptREST / Google Drive / 本地服务场景

> 本文档记录在实际执行 Labebe BOSS-3D-003 Stage 5 交付过程中遇到的代理/网络相关陷阱，供后续 agent 参考。
>
> 作者: Kimi Code CLI (session)
> 日期: 2026-05-03
> 场景: ChatgptREST MCP 调用、Google Drive rclone 同步、本地服务通信

---

## 1. 环境背景

### 1.1 网络拓扑

```
Yoga Server (Debian 12)
├── 本地代理客户端: mihomo/clash @ 127.0.0.1:7890 (HTTP/SOCKS5)
├── ChatgptREST MCP 服务: 127.0.0.1:18712 (HTTP SSE)
├── ChatgptREST API 服务: 127.0.0.1:18711 (HTTP REST)
├── 本地 Vite dev server: 127.0.0.1:5177
└── 外部: Google Drive API (被 GFW 阻断)
```

### 1.2 全局代理环境变量

```bash
$ env | grep -i proxy
ALL_PROXY=http://127.0.0.1:7890
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

这些变量在 `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env` 和 shell profile 中被持久化设置。**这意味着任何子进程默认都会走代理。**

---

## 2. 陷阱分类

### 陷阱 1: 本地服务走代理 → 流量浪费 + 潜在失败

**问题**: `HTTP_PROXY`/`HTTPS_PROXY` 对所有 HTTP(S) 请求生效，包括访问 `127.0.0.1:18712` 的本地 MCP 服务。

**实际影响**:
- ChatgptREST wrapper 脚本通过 HTTP 访问 `127.0.0.1:18712/mcp`
- 请求被路由到 `127.0.0.1:7890` 代理
- 代理再回环到 `127.0.0.1:18712`
- 结果: 本地请求走了两跳，增加了延迟，消耗了代理连接数

**为什么有时候能工作**:
- mihomo/clash 通常有 `bypass` 规则，会识别 `127.0.0.1`/`localhost`/`::1` 并直连
- 但如果代理配置中缺少这些规则，本地 MCP 请求会直接失败（`connection refused` 或超时）

**最佳实践**:
```bash
# 在调用本地服务前，临时取消代理环境变量
# 方法 A: 显式 unset（推荐）
(
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY
  curl http://127.0.0.1:18712/mcp
)

# 方法 B: 使用 NO_PROXY（如果工具支持）
export NO_PROXY="127.0.0.1,localhost,::1,*.local"

# 方法 C: 在脚本开头显式绕过（rclone_proxy.sh 的反面教材）
```

---

### 陷阱 2: rclone 需要代理，但代理变量作用域错误

**问题**: rclone 访问 Google Drive API 必须走代理（GFW 阻断），但代理变量如果在不合适的 scope 中设置，会导致其他工具也受影响。

**错误示范**（全局 export）:
```bash
# ~/.bashrc 或 ~/.profile 中
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
# 这会导致所有子进程都走代理，包括本地服务调用
```

**正确做法**（scoped export）:
```bash
# gdrive_remote_check.sh 中的实现
run_rclone_with_proxy() {
  # 只在 rclone 命令的作用域内设置代理
  HTTP_PROXY="http://127.0.0.1:7890" \
  HTTPS_PROXY="http://127.0.0.1:7890" \
  rclone "$@"
}
```

**或者使用 wrapper 脚本**:
```bash
# rclone_proxy.sh — 只对 rclone 生效
#!/usr/bin/env bash
export HTTP_PROXY="${HTTP_PROXY:-http://127.0.0.1:7890}"
export HTTPS_PROXY="${HTTPS_PROXY:-http://127.0.0.1:7890}"
exec rclone "$@"
```

**关键原则**: 代理是"按需启用"，不是"全局默认"。

---

### 陷阱 3: ChatgptREST wrapper 脚本与代理的冲突

**问题**: `chatgptrest_call.py` 脚本使用 Python `urllib` 或 `http.client` 访问本地 MCP 服务端点 `127.0.0.1:18712`。如果环境中存在 `HTTP_PROXY`，Python 的 `urllib.request` 默认会读取并使用代理。

**实际观察**:
- 脚本提交成功，说明代理没有阻断本地连接
- 但 Job 状态查询时，如果代理出现瞬时故障，可能导致 401/timeout

**建议做法**:
```bash
# 在调用 chatgptrest_call.py 前，对本地服务调用取消代理
# 但保留对 ChatGPT web 访问的代理（因为 ChatGPT 也可能被 GFW 影响）

# 实际上，ChatgptREST 的 CDP 浏览器访问也需要代理
# 所以不能完全取消代理

# 更精确的做法：区分服务地址
export NO_PROXY="127.0.0.1,localhost,::1,192.168.0.0/16,10.0.0.0/8"
```

---

### 陷阱 4: Playwright 浏览器下载走代理超时

**问题**: `npx playwright install` 需要从微软 CDN 下载 Chromium。在代理环境下，下载可能：
- 速度极慢
- 频繁超时
- 部分 CDN 节点被代理策略拒绝

**实际经历**:
- 在 Yoga 上，`npx playwright install chromium` 多次超时
- 最终手动下载了 chromium-1217 (170MB) 并创建 symlink 解决

**避坑建议**:
```bash
# 方法 A: 临时取消代理后重试
(unset HTTP_PROXY HTTPS_PROXY; npx playwright install)

# 方法 B: 使用国内镜像
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright \
  npx playwright install

# 方法 C: 手动下载（fallback）
# 1. 从 https://playwright.azureedge.net/builds/chromium/1217/chromium-linux.zip 下载
# 2. 解压到 ~/.cache/ms-playwright/chromium-1217/
# 3. 创建必要的 symlink（headless-shell → chrome）
```

---

### 陷阱 5: chatgptrest.env 中的代理变量影响所有 ChatgptREST 子进程

**问题**: `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env` 中设置了 `ALL_PROXY`、`HTTP_PROXY`、`HTTPS_PROXY`。ChatgptREST 的 wrapper 脚本会加载这个文件。

**影响范围**:
- ChatgptREST 的 CDP 浏览器（访问 chatgpt.com）→ 需要代理 ✅
- ChatgptREST 的 MCP 初始化（访问 127.0.0.1:18712）→ 不需要代理 ❌
- ChatgptREST 的 API 调用（访问 127.0.0.1:18711）→ 不需要代理 ❌
- rclone sync → 需要代理 ✅

**建议**: ChatgptREST 的 env 文件应该增加 `NO_PROXY`:
```bash
# ~/.config/chatgptrest/chatgptrest.env
ALL_PROXY=http://127.0.0.1:7890
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
NO_PROXY=127.0.0.1,localhost,::1,192.168.0.0/16,10.0.0.0/8
```

---

## 3. 实际执行中的代理策略

### 3.1 Google Drive rclone 同步

```bash
# 正确做法：代理只作用于 rclone 命令
export HTTP_PROXY="http://127.0.0.1:7890"
export HTTPS_PROXY="http://127.0.0.1:7890"
rclone copy ./docs gdrive:target/path --progress

# 更正确做法：使用 wrapper，不影响当前 shell 的代理设置
bash ~/.codex-shared/skills/gdrive-remote-check/scripts/rclone_proxy.sh \
  copy ./docs gdrive:target/path
```

### 3.2 ChatgptREST Pro 审核提交

```bash
# 当前做法（有优化空间）
export PYTHONPATH=/vol1/1000/projects/ChatgptREST
export CHATGPTREST_ROOT=/vol1/1000/projects/ChatgptREST

# 问题：HTTP_PROXY/HTTPS_PROXY 仍然指向代理
# 本地 MCP 请求会多走一跳

# 优化做法
(
  export PYTHONPATH=/vol1/1000/projects/ChatgptREST
  export CHATGPTREST_ROOT=/vol1/1000/projects/ChatgptREST
  export NO_PROXY="127.0.0.1,localhost,::1"
  python3 chatgptrest_call.py ...
)
```

### 3.3 Playwright 录制 walkthrough

```bash
# Playwright 的浏览器（headless Chromium）访问本地 dev server 127.0.0.1:5177
# 如果全局代理设置存在，浏览器内部请求也会走代理

# 优化做法：在启动 Playwright 前，对本地地址设置 NO_PROXY
export NO_PROXY="127.0.0.1,localhost"
node scripts/record-walkthrough.mjs
```

---

## 4. 给其他 Agent 的 checklist

在执行涉及代理的操作前，先问自己：

| 问题 | 需要代理？ | 建议做法 |
|------|-----------|---------|
| 访问 Google Drive / YouTube / OpenAI API | ✅ 是 | 显式导出代理，或使用 wrapper |
| 访问本地 127.0.0.1 / localhost | ❌ 否 | `unset HTTP_PROXY HTTPS_PROXY` 或设置 `NO_PROXY` |
| 访问局域网 192.168.x.x | ❌ 否 | 加入 `NO_PROXY` |
| ChatgptREST MCP 初始化 (127.0.0.1:18712) | ❌ 否 | 设置 `NO_PROXY` |
| ChatgptREST CDP 浏览器 (chatgpt.com) | ✅ 是 | 保持代理 |
| Playwright 下载 Chromium | ⚠️ 可能不需要 | 先试无代理，超时再用镜像 |
| rclone sync to Google Drive | ✅ 是 | 使用 scoped proxy wrapper |
| npm install (海外 registry) | ⚠️ 视情况 | 可配置 registry 镜像，不依赖代理 |

---

## 5. 推荐的 `.env` 或 `chatgptrest.env` 配置模板

```bash
# === 代理基础 ===
ALL_PROXY=http://127.0.0.1:7890
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890

# === 关键：本地和局域网不走代理 ===
NO_PROXY=127.0.0.1,localhost,::1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12

# === ChatgptREST 特有 ===
CHATGPTREST_API_TOKEN=...
CHATGPTREST_OPS_TOKEN=...
```

---

## 6. 实际踩坑记录

### 事件 1: rclone 代理未设置导致 Drive sync 失败
- **时间**: 2026-05-02
- **现象**: `rclone ls gdrive:` 返回 `Failed to create file system: couldn't find root...` 或超时
- **根因**: rclone 没有读取到代理环境变量，Google Drive API 请求被 GFW 阻断
- **修复**: 在 `gdrive_remote_check.sh` 和 `sync-drive-package.ps1` 中显式导出代理

### 事件 2: ChatgptREST worktree Python 模块冲突
- **时间**: 2026-05-03
- **现象**: `ImportError: cannot import name 'mcp_http_initialize_handshake'`
- **根因**: ChatgptREST 使用了 git worktrees，Python `sys.path` 解析到了 `.worktrees/runtime-feature-memory/` 中的旧版本代码
- **修复**: 设置 `PYTHONPATH=/vol1/1000/projects/ChatgptREST` 强制使用主 checkout
- **与代理的关系**: 无直接关系，但在排查代理问题时一并发现

### 事件 3: Playwright chromium-1217 headless shell 缺失
- **时间**: 2026-05-02/03
- **现象**: `browserType.launch: Executable doesn't exist at .../chromium_headless_shell-1217/...`
- **根因**: `npx playwright install` 因网络问题超时，chromium-1217 未完整下载
- **修复**: 手动下载 chromium-1217，创建 `chrome-headless-shell` symlink
- **与代理的关系**: 代理导致 CDN 下载超时；如果代理配置不当或 CDN 节点不稳定，install 会失败

---

## 7. 一句话总结

> **代理是手术刀，不是默认开关。**
>
> 对外走代理（Google Drive、ChatGPT web），对内不走代理（localhost、MCP、局域网）。
> 用 `NO_PROXY` 做白名单，比用 `unset` 做黑名单位置更可靠。
