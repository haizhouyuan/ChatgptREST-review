# Paperclip Runtime 全量盘点

> 生成时间: 2026-05-06
> 范围: 本机 (`/vol1/1000/projects/toyresearch`) 实际可执行的 AI agent CLI

---

## 一、Runtime 分类总览

| 类别 | 数量 | 说明 |
|------|------|------|
| **Claude Code 包装器** | 5 | 通过 Anthropic 兼容协议接入不同 provider |
| **OpenAI Codex** | 3 | 官方 Codex CLI 及配置隔离实例 |
| **原生 CLI** | 3 | Gemini、Kimi 官方命令行工具 |
| **本地推理** | 0 | Ollama 未安装 |
| **废弃/停用** | 1 | `openclaw` 已 disabled |

---

## 二、Claude Code 包装器（核心）

底层均为 Claude Code v2.1.129，通过 `ANTHROPIC_BASE_URL` + `ANTHROPIC_API_KEY` 切换不同 provider。

### 2.1 claudekimi

| 属性 | 值 |
|------|-----|
| 路径 | `~/.local/bin/claudekimi` |
| 底层 | `~/local/node/bin/claude` |
| 端点 | `https://api.kimi.com/coding/` |
| 模型 | `mimo-v2.5-pro` |
| API Key | `KIMI_CODINGPLAN_API_KEY` |
| 配置隔离 | `~/.claude-kimi/` |
| 代理 | 无特殊代理设置 |
| 健康状态 | 端点可连通 (HTTP 200) |
| 用途 | **默认主力 runtime**，高质量推理、财务分析、证据合成 |

**文件清单:**
- `~/.claude-kimi/.claude.json` (36KB, 活跃使用)
- `~/.claude-kimi/history.jsonl` (命令历史)
- `~/.claude-kimi/file-history/` (文件操作记录)

### 2.2 claudeminmax

| 属性 | 值 |
|------|-----|
| 路径 | `~/.local/bin/claudeminmax` |
| 底层 | `~/local/node/bin/claude` |
| 端点 | `https://api.minimaxi.com/anthropic` |
| 模型 | `MiniMax-M2.7-highspeed` |
| API Key | `MINIMAX_API_KEY` |
| 配置隔离 | `~/.claude-minimax/` |
| 健康状态 | 端点可连通 (HTTP 404 为正常，因路径需 POST) |
| 用途 | 低成本摘要、文档起草、文案变体 |
| 并发策略 | 默认 `CLAUDEMINMAX_MAX_CONCURRENCY=1`，可显式升到 `2`，超过 `2` 会被 wrapper clamp |
| 429 策略 | runtime allocator 对 HTTP 429 读取并尊重 `Retry-After`，没有 header 时才回退默认 cooldown |

**注意:** `~/.local/bin/claudeminmax` 是指向 `~/.home-codex-official/.local/bin/claudeminmax` 的软链接。

### 2.3 claudeds (DeepSeek)

| 属性 | 值 |
|------|-----|
| 路径 | `~/.local/bin/claudeds` |
| 底层 | Node v22 的 `claude` |
| 端点 | `https://api.deepseek.com/anthropic` |
| 模型 | `deepseek-v4-pro` |
| API Key | `DEEPSEEK_API_KEY` |
| 配置隔离 | `~/.home-claude-ds/` |
| 代理 | 强制 `127.0.0.1:7890` |
| 健康状态 | 端点可连通 |
| 用途 | 备用推理 runtime |

**文件清单:**
- `~/.home-claude-ds/.claude.json` (1.3KB，新配置)
- `~/.home-claude-ds/.claude/` (配置子目录)

### 2.4 claudegac

| 属性 | 值 |
|------|-----|
| 路径 | `~/.local/bin/claudegac` |
| 底层 | `~/local/node/bin/claude` |
| 端点 | 外部配置 (`gac.env`) |
| 模型 | `opus` (默认) |
| 配置隔离 | `~/.claude-gac/` |
| 代理 | 无 |
| 凭证文件 | `~/.claude-gac/gac.env` (210 bytes) |
| 用途 | GAC 外部 provider，财务机器人 finbot 常用 |

### 2.5 claudemi (MiMo)

| 属性 | 值 |
|------|-----|
| 路径 | `~/.local/bin/claudemi` |
| 底层 | Node v22 的 `claude` |
| 端点 | `https://token-plan-sgp.xiaomimimo.com/anthropic` |
| 模型 | `mimo-v2.5-pro` |
| API Key | `MIMO_API_KEY` |
| 配置隔离 | `~/.home-claude-mi/` |
| 代理 | 强制 `127.0.0.1:7890` |
| 用途 | 小米 MiMo Token Plan 接入 |

**注意:** `claudemi` 与 `claudekimi` 都使用 `mimo-v2.5-pro` 模型，但端点不同（MiMo 自有端点 vs Kimi Coding Plan）。

---

## 三、OpenAI Codex

### 3.1 codex / codex-official

| 属性 | 值 |
|------|-----|
| 路径 | `~/.local/bin/codex` → `codex-official` |
| 底层 | Node v22 `codex` CLI |
| 模型 | `gpt-5.5` |
| 配置隔离 | `~/.home-codex1/` + `~/.codex1/` |
| 代理 | 强制 `127.0.0.1:7890` |
| 参数 | `--dangerously-bypass-approvals-and-sandbox`, reasoning effort `xhigh` |
| 版本 | `codex-cli 0.128.0` |
| 凭证 | `auth.json` (OpenAI 刷新令牌) |
| 用途 | 自动化编码任务、多 agent 协作 (multica) |

**文件清单:**
- `~/.codex1/auth.json` (OpenAI 认证)
- `~/.codex1/agents/` → 软链接到 `~/.codex-shared/agents`
- `~/.codex1/config.toml` → 软链接到 `~/.codex-shared/config.toml`

### 3.2 codex1

`codex-official` 的透明包装器，无额外配置。

### 3.3 codex2

| 属性 | 值 |
|------|-----|
| 路径 | `~/.local/bin/codex2` |
| 配置隔离 | `~/.codex2/` |
| 底层 | `~/.home-codex-official/.local/bin/codex2` |
| 代理 | 强制 `127.0.0.1:7890` |

---

## 四、原生 CLI

### 4.1 gemini

| 属性 | 值 |
|------|-----|
| 路径 | `~/.nvm/versions/node/v22.22.0/bin/gemini` |
| 版本 | `0.39.1` |
| 配置 | `~/.gemini/` (含 GEMINI.md, antigravity, chrome-devtools-mcp-wrapper) |
| 用途 | Google Gemini CLI，支持文件、shell、MCP |
| runtime_profiles 映射 | `gemini_local` |

### 4.2 kimi / kimi-cli

| 属性 | 值 |
|------|-----|
| 路径 | `~/.local/share/uv/tools/kimi-cli/bin/kimi` |
| 版本 | `1.40.0` |
| 配置 | `~/.kimi/config.toml`, `~/.kimi/kimi.json`, `~/.kimi/credentials/` |
| 用途 | Kimi 原生 CLI |

### 4.3 kimicode

| 属性 | 值 |
|------|-----|
| 路径 | `~/.local/bin/kimicode` |
| 说明 | 调用 `kimi` 但 **unset 所有代理变量** |
| 用途 | 绕过 localhost 代理直接访问 api.kimi.com，解决代理超时问题 |

---

## 五、本地推理

### 5.1 ollama

| 属性 | 值 |
|------|-----|
| 状态 | **未安装** (`ollama: not found`) |
| runtime_profiles 注册 | `ollama_gpu0` (`http://localhost:11434/v1`, `qwen2.5:32b`) |
| 说明 | profile 中定义但本机无 ollama 服务，HomePC 上可能运行 |

---

## 六、环境变量汇总

当前 shell 中已加载的 AI provider 相关变量：

```
ANTHROPIC_API_KEY
ANTHROPIC_BASE_URL
DEEPSEEK_API_KEY
GEMINI_CLI_HOME
GEMINI_CODINGPLAN_API_KEY
GEMINI_CODINGPLAN_BASE_URL
GEMINI_CODINGPLAN_MODEL
KIMI_CODINGPLAN_API_KEY
MIMO_BASE_URL_ANTHROPIC
MIMO_BASE_URL_OPENAI
MINIMAX_ANTHROPIC_BASE_URL
MINIMAX_API_HOST
MINIMAX_API_KEY
MINIMAX_MODEL
MULTICA_CODEX_PATH
MULTICA_KIMI_MODEL
MULTICA_KIMI_PATH
```

---

## 七、凭证文件分布

| 文件 | 大小 | 说明 |
|------|------|------|
| `/vol1/maint/MAIN/secrets/credentials.env` | 3.3KB | 集中凭证（DeepSeek、MiniMax、Tavily、Brave、BrowserUse 等） |
| `~/.claude-gac/gac.env` | 210B | GAC 专用凭证（ANTHROPIC_BASE_URL + ANTHROPIC_API_KEY） |
| `~/.codex1/auth.json` | 4.4KB | OpenAI 刷新令牌 |
| `~/.kimi/credentials/` | - | Kimi CLI 凭证目录 |

---

## 八、Orchestrator 默认 Runtime 映射

| Orchestrator | 默认 Runtime | 降级策略 |
|--------------|-------------|----------|
| `paperclip_labebe` | `claudekimi` | 可降级至 minimax |
| `paperclip_planning` | `claudekimi` | 硬锁定，不降級 |
| `paperclip_memory` | `claudekimi` | 硬锁定，不降級 |
| `paperclip_finbot` | `claudegac` (opus) / `claudeds` | 财务分析专用 |

---

## 九、已知问题与风险

| # | 问题 | 影响 | 建议 |
|---|------|------|------|
| 1 | `claudemi` 和 `claudekimi` 使用相同模型名 `mimo-v2.5-pro`，但端点不同，易混淆 | 调度层可能误路由 | 统一命名：`claudekimi`→`kimi-mimo`, `claudemi`→`xiaomi-mimo` |
| 2 | `ollama_gpu0` 在 profile 中 `enabled: true`，但本机无 ollama 服务 | health probe 必然失败，触发 cooldown | 改为 `enabled: false` 或检测 HomePC 可达性 |
| 3 | 凭证分散在 3 处：`credentials.env`、`gac.env`、`auth.json` | 轮换密钥时易遗漏 | 统一使用 `/vol1/maint/MAIN/secrets/` 或外部 secret manager |
| 4 | `claudeds`、`claudemi` 强制代理 `127.0.0.1:7890`，但该端口代理状态不明 | 可能连接失败 | 增加代理健康检查 fallback |
| 5 | 5 个 Claude wrapper 各有一个 `~/.claude-*` 配置目录 | 备份/迁移成本高 | 评估是否可以合并部分配置 |
| 6 | `codex2` 指向 `~/.home-codex-official/.local/bin/codex2`，该路径实际为 `claudeminmax` 的隔离目录 | 可能互相污染 | 确认 `codex2` 是否仍在使用 |

---

## 十、快速验证命令

```bash
# Claude Code wrappers
claudekimi --version    # 2.1.129
claudeminmax --version  # 2.1.129
claudeds --version      # 2.1.129
claudegac --version     # 2.1.129
claudemi --version      # 2.1.129

# Codex
codex --version         # codex-cli 0.128.0

# Native CLI
gemini --version        # 0.39.1
kimi --version          # 1.40.0

# Ollama (expected: not found)
ollama --version        # not found

# Endpoint smoke (no auth)
curl -sI https://api.kimi.com/coding/
curl -sI https://api.minimaxi.com/v1
curl -sI https://api.deepseek.com/anthropic
```

---

## 附录：完整命令路径索引

```
~/.local/bin/claudekimi          → bash wrapper (Kimi Coding Plan)
~/.local/bin/claudeminmax        → symlink → ~/.home-codex-official/.local/bin/claudeminmax
~/.local/bin/claudeds            → bash wrapper (DeepSeek)
~/.local/bin/claudegac           → bash wrapper (GAC)
~/.local/bin/claudemi            → bash wrapper (MiMo)
~/.local/bin/codex               → symlink → codex-official
~/.local/bin/codex-official      → bash wrapper (OpenAI Codex, gpt-5.5)
~/.local/bin/codex1              → bash wrapper → codex-official
~/.local/bin/codex2              → bash wrapper (Codex instance 2)
~/.local/bin/gemini              → symlink → ~/.nvm/versions/node/v22.22.0/bin/gemini
~/.local/bin/kimi                → symlink → ~/.local/share/uv/tools/kimi-cli/bin/kimi
~/.local/bin/kimi-cli            → symlink → ~/.local/share/uv/tools/kimi-cli/bin/kimi-cli
~/.local/bin/kimicode            → bash wrapper (kimi without proxy)
~/local/node/bin/claude          → real Claude Code binary (v2.1.129)
~/.nvm/versions/node/v22.22.0/bin/codex   → real Codex CLI (v0.128.0)
~/.nvm/versions/node/v22.22.0/bin/gemini  → real Gemini CLI (v0.39.1)
```
