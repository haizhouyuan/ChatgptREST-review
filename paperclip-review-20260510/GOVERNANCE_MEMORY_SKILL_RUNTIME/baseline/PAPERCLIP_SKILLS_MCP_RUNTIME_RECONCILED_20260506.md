# Paperclip Skills / MCP / Runtime 配置 —— 深度核验最终版

> **生成时间**: 2026-05-06  
> **核验方式**: 逐文件实地 `cat` + `curl` + `ps` 探查（非文档推断）  
> **前置文档**:  
> - `PAPERCLIP_SKILL_MCP_RUNTIME_VERIFIED_20260506.md`（Kimi 调查，Paperclip server/skills 层）  
> - `PAPERCLIP_SKILLS_AND_MCP_INVENTORY_20260506.md`（ClaudeKimi 调查，CLI wrapper MCP 层）  
> - `PAPERCLIP_RUNTIME_INVENTORY_20260506.md`（CLI runtime 盘点，有遗漏）

---

## 一、两份前置调查的关键差异与勘误

### 1.1 路径错误（ClaudeKimi 调查）

| 调查报告写的路径 | 实际存在路径 | 状态 |
|----------------|-------------|------|
| `~/.claude-kimi/mcp.json` | `/REDACTED_HOME/.claude-kimi/mcp.json` | ✅ 存在，但路径前缀错误 |
| `~/.claude-minimax/settings.json` | `/REDACTED_HOME/.claude-minimax/settings.json` | ✅ 存在，路径前缀错误 |
| `~/.claude-gac/mcp.json` | `/REDACTED_HOME/.claude-gac/mcp.json` | ✅ 存在，路径前缀错误 |
| `~/.home-claude-ds/.claude/mcp.json` | `/REDACTED_HOME/.home-claude-ds/.claude/mcp.json` | ✅ 存在，路径前缀错误 |
| `~/.home-claude-mi/.claude/mcp.json` | `/REDACTED_HOME/.home-claude-mi/.claude/mcp.json` | ✅ 存在，路径前缀错误 |

> **根因**: 用户有两个 HOME 层级——`~` = `/REDACTED_HOME` 是系统 HOME，但大量项目数据和配置实际存放在 `/REDACTED_HOME/`（SSD/数据盘挂载点）。wrapper 脚本在后者路径下创建隔离目录。ClaudeKimi 调查将 `~` 等同于配置目录前缀，导致路径错误。

### 1.2 MCP 数量勘误

| Wrapper | ClaudeKimi 报告 | 实地核验 | 差异说明 |
|---------|----------------|---------|---------|
| `claudekimi` | 6 | **6** | ✅ 正确 |
| `claudeds` | 8 | **5** | ❌ 多报了 3 个（可能混淆了环境变量注入与注册 server） |
| `claudemi` | 9 | **5** | ❌ 多报了 4 个（同上） |
| `claudeminmax` | 6（继承全局） | **2** | ❌ 实际有独立 mcp.json（2 servers），不会继承 `~/.claude/mcp.json` |
| `claudegac` | 2 | **2** | ✅ 正确 |

### 1.3 Skills 层重大遗漏

ClaudeKimi 调查只盘点了 `toyresearch/skills/` 下的 **2 个** HomePC 基础设施 skill，**完全遗漏了 Paperclip demo package 的 5 个 skills**。这在 `PAPERCLIP_SKILL_MCP_RUNTIME_VERIFIED_20260506.md` 中已补充。

### 1.4 Chrome-Devtools 端口

ClaudeKimi 报告"9222 vs 9224 冲突"。实地核验：
- `127.0.0.1:9222`：**正在运行**（HeadlessChrome/145，Protocol 1.3）
- `127.0.0.1:9224`：**未响应**

结论：9222 是当前唯一活跃的 CDP 端口，无冲突。9224 可能是文档中预留的 Claude 专属 lane，但当前未启动对应浏览器实例。

---

## 二、各 Runtime 配置 —— 经实地核验的最终版

### 2.1 配置加载机制

Claude Code v2.1.x 按以下优先级找配置：
1. `CLAUDE_CONFIG_DIR` 环境变量（如果设置）
2. `$HOME/.claude/`（HOME 可被 wrapper 覆盖）
3. 系统默认 `~/.claude/`

**关键**：当 wrapper 设置 `HOME=/REDACTED_HOME/.home-claude-ds` 时，Claude Code **不会**回退到 `~/.claude/`，而是在新的 HOME 下完全独立运行。

### 2.2 六条 Runtime 的完整配置

#### A. `claude`（默认命令）

| 项 | 值 |
|----|-----|
| 配置目录 | `~/.claude/` |
| Model | `MiniMax-M2.7`（由 settings.json 硬编码） |
| Endpoint | `https://api.minimaxi.com/anthropic` |
| mcp.json | **6 servers**: codex, claude, minimax, tavily, brave-search, gitnexus |
| settings.json | MiniMax mode + HCOM hooks + 硬编码 API keys |
| HCOM hooks | ✅ 全量启用（SessionStart/Stop, Pre/PostToolUse, SubagentStart/Stop, Notification） |
| Plugins | `minimax-skills@minimax-skills` |
| 风险 | **默认 `claude` 命令启动即进入 MiniMax 模式**，与 `claudeminmax` 功能重叠 |

**settings.json 关键片段**（已脱敏处理摘要）：
```json
{
  "model": "MiniMax-M2.7",
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
    "HCOM": "hcom",
    "BRAVE_API_KEY": "<硬编码>",
    "TAVILY_API_KEY": "<硬编码>"
  },
  "permissions": { "allow": ["Bash(hcom send:*)", ...] },
  "hooks": {
    "SessionStart": [{"hooks": [{"type": "command", "command": "${HCOM} sessionstart"}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "${HCOM} userpromptsubmit"}]}],
    "PreToolUse": [{"hooks": [{"type": "command", "command": "${HCOM} pre"}]}],
    "PostToolUse": [{"hooks": [{"type": "command", "command": "${HCOM} post"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "${HCOM} poll"}]}],
    "SubagentStart": [{"hooks": [{"type": "command", "command": "${HCOM} subagent-start"}]}],
    "SubagentStop": [{"hooks": [{"type": "command", "command": "${HCOM} subagent-stop"}]}],
    "Notification": [{"hooks": [{"type": "command", "command": "${HCOM} notify"}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "command": "${HCOM} sessionend"}]}]
  }
}
```

**mcp.json 关键片段**（API keys 已脱敏）：
```json
{
  "mcpServers": {
    "codex": { "command": ".../bin/codex", "args": ["mcp-server"] },
    "claude": { "command": ".../bin/claude-mcp", "args": [] },
    "minimax": { "command": ".../bin/minimax-mcp-js", "env": { "MINIMAX_API_KEY": "<硬编码>" } },
    "tavily": { "command": ".../bin/tavily-mcp", "env": { "TAVILY_API_KEY": "<硬编码>" } },
    "brave-search": { "command": ".../bin/brave-search-mcp-server", "env": { "BRAVE_API_KEY": "<硬编码>" } },
    "gitnexus": { "command": ".../bin/gitnexus", "args": ["mcp"] }
  }
}
```

#### B. `claudekimi`

| 项 | 值 |
|----|-----|
| 配置目录 | `/REDACTED_HOME/.claude-kimi/` |
| Model | **不硬编码**（由 wrapper 通过 `--model` 传入或默认） |
| Endpoint | `https://api.kimi.com/coding/`（wrapper 注入） |
| mcp.json | **6 servers**: chrome-devtools, context7, gitnexus, playwright, glm-router, chatgptrest |
| settings.json | `skipDangerousModePermissionPrompt: true`, `skipAutoPermissionPrompt: true` |
| HCOM hooks | ❌ 无 |
| Plugins | ❌ 无 |

**mcp.json 详情**：
```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": ".../chrome-devtools-mcp",
      "args": ["--browser-url=http://127.0.0.1:9222", "--logFile=/tmp/chrome-devtools-mcp.log"]
    },
    "context7": { "url": "https://mcp.context7.com/mcp" },
    "gitnexus": { "url": "http://127.0.0.1:18713/api/mcp" },
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@0.0.68", "--headless", "--isolated",
                "--timeout-navigation=120000", "--timeout-action=60000",
                "--block-service-workers", "--allowed-origins=http://127.0.0.1:8701"],
      "env": { "PLAYWRIGHT_BROWSERS_PATH": "...", "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1" }
    },
    "glm-router": {
      "command": "bash",
      "args": ["/vol1/1000/projects/codexread/scripts/run_glm_router_mcp.sh"],
      "env": { "GLM_ROUTER_CALL_LOG": "/vol1/1000/projects/codexread/logs/glm_router_calls.jsonl" }
    },
    "chatgptrest": { "url": "http://127.0.0.1:18712/mcp" }
  }
}
```

#### C. `claudeminmax`

| 项 | 值 |
|----|-----|
| 配置目录 | `/REDACTED_HOME/.claude-minimax/` |
| Model | **不硬编码**（wrapper 通过 `--model` 传入，默认 `MiniMax-M2.7-highspeed`） |
| Endpoint | `https://api.minimaxi.com/anthropic`（wrapper 注入） |
| mcp.json | **2 servers**: brave-search, tavily |
| settings.json | `env`（BRAVE_API_KEY, TAVILY_API_KEY）, `skipDangerousModePermissionPrompt: true` |
| HCOM hooks | ❌ 无（`.claude.json` 中未记录 hooks） |
| 与 `claude` 默认命令的区别 | `claude` 也指向 MiniMax，但 `claude` 有 HCOM hooks + 6 MCP；`claudeminmax` 无 hooks + 2 MCP |

#### D. `claudegac`

| 项 | 值 |
|----|-----|
| 配置目录 | `/REDACTED_HOME/.claude-gac/` |
| Model | `opus[1m]` |
| Effort | `medium` |
| mcp.json | **2 servers**: brave-search, tavily |
| settings.json | `env`（BRAVE_API_KEY, TAVILY_API_KEY）, `defaultMode: "dontAsk"`, `skipDangerousModePermissionPrompt: true` |
| HCOM hooks | ❌ 无 |
| Skills symlink | `skill-platform` → `.../.home-codex-official/.claude/skill-platform`（共享 Codex skill 市场） |

#### E. `claudeds`（DeepSeek）

| 项 | 值 |
|----|-----|
| 配置目录 | `/REDACTED_HOME/.home-claude-ds/`（通过 `HOME=` 覆盖） |
| Model | `deepseek-v4-pro`（硬编码在 `.claude.json`） |
| Endpoint | `https://api.deepseek.com/anthropic`（硬编码在 `.claude.json`） |
| mcp.json | **5 servers**: context7, gitnexus, chatgptrest, playwright, chrome-devtools |
| settings.json | **不存在** |
| HCOM hooks | ⚠️ **`.claude.json` 中记录了 HCOM permissions**（本不该有，疑似配置漂移） |
| 风险 | HCOM permissions 与 DeepSeek provider 无关，可能是从 `~/.claude/` 漂移而来 |

#### F. `claudemi`（MiMo）

| 项 | 值 |
|----|-----|
| 配置目录 | `/REDACTED_HOME/.home-claude-mi/`（通过 `HOME=` 覆盖） |
| Model | `mimo-v2.5-pro`（硬编码在 `.claude.json`） |
| Endpoint | `https://token-plan-sgp.xiaomimimo.com/anthropic`（硬编码在 `.claude.json`） |
| mcp.json | **5 servers**: context7, gitnexus, chatgptrest, playwright, chrome-devtools |
| settings.json | `defaultMode: "dontAsk"`, `theme: "auto"`, `skipDangerousModePermissionPrompt: true` |
| HCOM hooks | ⚠️ **`.claude.json` 中记录了 HCOM permissions**（同上，疑似漂移） |

### 2.3 Kimi CLI Native (`~/.kimi/`)

| 项 | 值 |
|----|-----|
| mcp.json | **6 servers**（与 `~/.claude/mcp.json` 内容完全一致） |
| 说明 | Kimi CLI 和 Claude Code 默认配置共享同一套 MCP 注册 |

### 2.4 Gemini Antigravity (`~/.gemini/antigravity/mcp_config.json`)

| 项 | 值 |
|----|-----|
| mcpServers | **8 servers**: context7, gitnexus, chatgptrest, MiniMax, tavily, brave-search, playwright-browser, StitchMCP |
| MiniMax MCP | 通过 `antigravity-minimax-coding-plan-mcp.sh` 脚本启动 |
| API Keys | **硬编码在 config 中**（StitchMCP 的 X-Goog-Api-Key） |
| playwright-browser | URL 模式 `http://localhost:39001/mcp`（非 stdio） |

---

## 三、MCP Server 注册矩阵（跨 runtime 汇总）

| Server | default<br>`~/.claude` | claudekimi<br>`.claude-kimi` | claudeminmax<br>`.claude-minimax` | claudegac<br>`.claude-gac` | claudeds<br>`.home-claude-ds` | claudemi<br>`.home-claude-mi` | Kimi CLI<br>`.kimi` | Gemini<br>antigravity |
|--------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| codex | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| claude (mcp) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| minimax | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| tavily | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| brave-search | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| gitnexus | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| chrome-devtools | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| context7 | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ |
| playwright | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ |
| glm-router | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| chatgptrest | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ |
| playwright-browser | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| StitchMCP | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Total** | **6** | **6** | **2** | **2** | **5** | **5** | **6** | **8** |

---

## 四、MCP 服务健康状态

| Server | 地址/命令 | 状态 | 验证方式 |
|--------|----------|------|---------|
| Paperclip | `127.0.0.1:3100` | ✅ Healthy | `curl /api/health` → `{"status":"ok","version":"0.3.1"}` |
| chatgptrest | `127.0.0.1:18712/mcp` | ✅ Running | `curl` → SSE protocol error（预期行为） |
| gitnexus | `127.0.0.1:18713/api/mcp` | ✅ Running | `curl` → session init required（预期行为） |
| chrome-devtools | `127.0.0.1:9222` | ✅ Running | `curl /json/version` → Chrome/145, Protocol 1.3 |
| context7 | `https://mcp.context7.com/mcp` | ✅ Reachable | HTTPS 200 |
| glm-router | `run_glm_router_mcp.sh` | ✅ Running | PID 151061, Python process 活跃 |
| tavily | `tavily-mcp` | ⚠️ 依赖 key | 未直接测试（需 API key） |
| brave-search | `brave-search-mcp-server` | ⚠️ 依赖 key | 未直接测试（需 API key） |
| codex | `codex mcp-server` | ⚠️ 依赖 auth | 未直接测试 |
| claude-mcp | `claude-mcp` | ⚠️ 依赖 auth | 未直接测试 |

---

## 五、Paperclip Demo 层（补充自 Kimi 调查）

此部分在 ClaudeKimi 调查中**完全遗漏**，在 `PAPERCLIP_SKILL_MCP_RUNTIME_VERIFIED_20260506.md` 中已详细记录，此处仅摘要：

| 组件 | 状态 |
|------|------|
| Paperclip Server | v0.3.1, PID 2249121, embedded-postgres@54329 |
| Agents | 9 个（含 process adapter） |
| Tasks | 11 个（含 LAB-SMOKE-001） |
| Skills | 5 个注册（3 本地 + 2 外部路径） |
| MCP Tools | 34 个，default-deny 策略 |
| Mutation Gating | LAB-SMOKE-001 白名单 |
| **风险** | 2 个 skills 引用外部路径 `/vol1/1000/projects/paperclip/...`，不可移植 |
| **风险** | `configs/` 与 `labebe-ai-design-studio/workspace/config/` 重复配置 |

**MCP Template** (`paperclip_labebe_demo_package/mcp/paperclip.template.json`)：
```json
{
  "mcpServers": {
    "paperclip-labebe-demo": {
      "command": "node",
      "args": [
        "/vol1/1000/projects/paperclip/cli/node_modules/tsx/dist/cli.mjs",
        "/vol1/1000/projects/paperclip/packages/mcp-server/src/stdio.ts"
      ],
      "env": {
        "PAPERCLIP_API_URL": "http://127.0.0.1:3100",
        "PAPERCLIP_API_KEY": "${PAPERCLIP_API_KEY}",
        "PAPERCLIP_COMPANY_ID": "1cb6d439-2bdf-4f63-ad9a-b5326d5546df",
        "PAPERCLIP_AGENT_ID": "${PAPERCLIP_AGENT_ID}"
      }
    }
  }
}
```

- `tsx` 已确认可用：`/vol1/1000/projects/paperclip/cli/node_modules/.bin/tsx`
- `src/stdio.ts` 源码存在，但 package.json 定义 bin 为 `dist/stdio.js`（未构建）
- `${PAPERCLIP_API_KEY}` 和 `${PAPERCLIP_AGENT_ID}` 是占位符，实际运行需替换

---

## 六、已确认问题清单（按优先级排序）

### 🔴 P0 —— 配置漂移 / 安全风险

| # | 问题 | 影响 | 证据 |
|---|------|------|------|
| 1 | `~/.claude/settings.json` 是 MiniMax 模式，含 HCOM hooks 和硬编码 API keys | `claude` 默认命令 = `claudeminmax`，功能重复；keys 泄露风险 | `cat ~/.claude/settings.json` |
| 2 | `~/.claude/mcp.json` 硬编码 MINIMAX_API_KEY, TAVILY_API_KEY, BRAVE_API_KEY | 密钥泄露风险；无法轮换 | `cat ~/.claude/mcp.json` |
| 3 | `~/.claude-gac/settings.json` 硬编码 BRAVE_API_KEY, TAVILY_API_KEY | 同上 | `cat ~/.claude-gac/settings.json` |
| 4 | `~/.claude-minimax/settings.json` 硬编码 BRAVE_API_KEY, TAVILY_API_KEY | 同上 | `cat ~/.claude-minimax/settings.json` |
| 5 | `~/.gemini/antigravity/mcp_config.json` 硬编码 StitchMCP X-Goog-Api-Key | 同上 | `cat ~/.gemini/antigravity/mcp_config.json` |
| 6 | `claudeds` 和 `claudemi` 的 `.claude.json` 中记录 HCOM permissions | DeepSeek/MiMo provider 不应有 HCOM hooks，疑似从 `~/.claude/` 漂移 | `cat .home-claude-ds/.claude.json`, `cat .home-claude-mi/.claude.json` |

### 🟡 P1 —— 功能不一致 / 维护负担

| # | 问题 | 影响 | 证据 |
|---|------|------|------|
| 7 | 各 runtime MCP 数量 2~8 不等，无统一 baseline | 不同 provider 能力不一致，agent 行为不可预测 | 矩阵表 |
| 8 | `paperclip` MCP template 使用 `src/stdio.ts`（源码）而非 `dist/stdio.js`（构建产物） | 依赖 tsx，启动慢；构建产物可能过时 | `cat mcp/paperclip.template.json`, `cat packages/mcp-server/package.json` |
| 9 | Paperclip skills 引用外部绝对路径 `/vol1/1000/projects/paperclip/...` | 不可移植，其他机器无法使用 | `cat configs/skill-registry.yaml` |
| 10 | `paperclip_labebe_demo_package/configs/` 与 `labebe-ai-design-studio/workspace/config/` 配置重复 | 修改一处需同步另一处，易发散 | 目录结构对比 |
| 11 | `~/.claude/` 和 `~/.claude-kimi/` 配置目录位于不同前缀路径（`/REDACTED_HOME/` vs `/REDACTED_HOME/`） | 备份/迁移时需同时处理两个根 | 目录结构 |

### 🟢 P2 —— 观察项

| # | 问题 | 影响 | 证据 |
|---|------|------|------|
| 12 | `glm-router` log 路径固定为 `/vol1/1000/projects/codexread/logs/glm_router_calls.jsonl` | 跨项目写入，权限/归属需确认 | `cat .claude-kimi/mcp.json` |
| 13 | chrome-devtools log 固定为 `/tmp/chrome-devtools-mcp.log` | 多实例可能冲突 | `cat .claude-kimi/mcp.json` |
| 14 | `~/.kimi/mcp.json` 与 `~/.claude/mcp.json` 内容完全一致 | Kimi CLI 和 Claude default 共享同一套 MCP，但 Kimi CLI 实际可能不需要 minimax/brave 等 | `diff ~/.kimi/mcp.json ~/.claude/mcp.json` |
| 15 | `claude` 默认命令和 `claudeminmax` 都指向 MiniMax endpoint | 功能完全重叠，保留两者无意义 | wrapper 脚本对比 |

---

## 七、快速验证命令手册

```bash
# ===== 各 runtime MCP 配置 =====
cat ~/.claude/mcp.json                                              # default (MiniMax)
cat /REDACTED_HOME/.claude-kimi/mcp.json               # Kimi
 cat /REDACTED_HOME/.claude-minimax/mcp.json           # MiniMax
 cat /REDACTED_HOME/.claude-gac/mcp.json               # GAC
 cat /REDACTED_HOME/.home-claude-ds/.claude/mcp.json   # DeepSeek
 cat /REDACTED_HOME/.home-claude-mi/.claude/mcp.json   # MiMo
 cat ~/.kimi/mcp.json                                               # Kimi CLI
 cat ~/.gemini/antigravity/mcp_config.json                          # Gemini

# ===== 各 runtime settings =====
cat ~/.claude/settings.json
cat /REDACTED_HOME/.claude-kimi/settings.json
cat /REDACTED_HOME/.claude-minimax/settings.json
cat /REDACTED_HOME/.claude-gac/settings.json
# claudeds/claudemi 无 settings.json，配置在 .claude.json 中

# ===== 服务健康检查 =====
curl -s http://127.0.0.1:3100/api/health | python3 -m json.tool    # Paperclip
curl -s http://127.0.0.1:9222/json/version | head -5               # Chrome devtools
curl -s http://127.0.0.1:18712/mcp | head -2                       # ChatgptREST
curl -s http://127.0.0.1:18713/api/mcp | head -2                   # GitNexus
ps aux | grep -E "glm_router|chatgptrest|gitnexus" | grep -v grep  # MCP processes

# ===== Paperclip demo 层 =====
cat /vol1/1000/projects/toyresearch/paperclip_labebe_demo_package/configs/skill-registry.yaml
cat /vol1/1000/projects/toyresearch/paperclip_labebe_demo_package/configs/mcp-tool-policy.yaml
cat /vol1/1000/projects/toyresearch/paperclip_labebe_demo_package/configs/agent-runtime-matrix.yaml

# ===== Skills（项目内）=====
cat /vol1/1000/projects/toyresearch/skills/homepc-video-pipeline/SKILL.md | head -20
cat /vol1/1000/projects/toyresearch/skills/homepc-workstation-bridge/SKILL.md | head -20
```

---

## 八、结论与建议

### 8.1 两份调查的可信度评估

| 文档 | 可信度 | 说明 |
|------|--------|------|
| `PAPERCLIP_SKILL_MCP_RUNTIME_VERIFIED_20260506.md`（Kimi） | **高** | Paperclip server/skills/agents/tasks 层全部经 SSH 实地验证 |
| `PAPERCLIP_SKILLS_AND_MCP_INVENTORY_20260506.md`（ClaudeKimi） | **中低** | CLI wrapper MCP 层有大量路径错误、数量误报、Skills 遗漏 |
| `PAPERCLIP_RUNTIME_INVENTORY_20260506.md`（Kimi） | **中** | CLI runtime 盘点基本正确，但遗漏 Paperclip 全栈 |

**本文件（RECONCILED）** 以实地 `cat/curl/ps` 探查结果为准，覆盖上述三份文档的所有层面。

### 8.2 立即可做的修复（无依赖）

1. **从所有 `settings.json` 和 `mcp.json` 中移除硬编码 API keys**，改为从环境变量读取（wrapper 脚本已注入，配置文件中无需重复）
2. **清理 `claudeds` 和 `claudemi` 的 `.claude.json` 中的 HCOM permissions**
3. **统一 MCP baseline**——建议所有 Claude wrapper 至少共享 `gitnexus` + `tavily` + `brave-search`
4. **决定 `claude` 默认命令的归属**——当前它等于 MiniMax 模式，建议要么改为真正的 Anthropic Claude，要么明确改名为 `claudedefault-minimax`

### 8.3 需要规划的修复

5. **Paperclip MCP template 的构建与部署**——确保 `packages/mcp-server` 有构建产物或确认 tsx 启动稳定
6. **外部 skills 路径解耦**——将 `/vol1/1000/projects/paperclip/...` 改为相对路径或符号链接
7. **配置去重**——合并 `paperclip_labebe_demo_package/configs/` 和 `labebe-ai-design-studio/workspace/config/`
