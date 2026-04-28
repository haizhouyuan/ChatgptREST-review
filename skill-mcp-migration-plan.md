# Skill & MCP 配置迁移方案

> 生成时间：2026-04-27
> 背景：梳理现有 Claude/Codex 实例配置，确定哪些需要同步到 Kimi CLI 和 `.claude-kimi`，避免一股脑复制废弃配置。

---

## 一、现状梳理

### 1.1 实例活跃度矩阵

| 实例 | 配置文件路径 | 历史对话量 | 最后活跃时间 | 活跃项目数 | 活跃度判定 |
|------|-------------|-----------|-------------|-----------|-----------|
| `.claude` (主实例) | `~/.claude/` | 406 条 | 持续活跃 | 15 个 | **主力在用** |
| `.claude-kimi` | `~/.claude-kimi/` | 155 条 | 2026-04-26 | 3 个 | **新建活跃实例** |
| `.claude-gac` | `~/.claude-gac/` | 246 条 + 大量子对话 | 2026-04-24 | 47 个 | **用户声明废弃，但昨日仍有 redteam 任务** |
| `.claude-minimax` | `~/.claude-minimax/` | 大量 project 子对话 | 2026-04-17 | 9 个 | **10 天无活动，疑似已停** |
| **Kimi CLI** | `~/.kimi/` | — | — | — | **完全空白** |

> `.claude-minimax` 的 `history.jsonl` 为 0 是因为其对话分散在 project 子目录中，实际 education 项目单条对话达 431 行。

### 1.2 MCP 配置现状

#### Claude 实例 MCP

| 实例 | brave-search | tavily | 状态 |
|------|:-----------:|:------:|------|
| `.claude` (主) | 有 | 有 | 完整 |
| `.claude-minimax` | 有 | 有 | 完整 |
| `.claude-kimi` | 无 | 无 | **空白** |
| `.claude-gac` | 有 | 有 | 完整 |

#### Codex MCP（实际启用状态）

| MCP 名称 | 状态 | 绑定项目 | 通用性 | 建议迁移 |
|---------|------|---------|--------|:--------:|
| chrome-devtools | enabled | — | 需 CDP 9222 | 待定 |
| playwright | enabled | — | 浏览器自动化 | 待定 |
| tasks | enabled | codexread | 项目强绑定 | **否** |
| tmux_orchestrator | enabled | codexread | 项目强绑定 | **否** |
| video_pipeline | enabled | codexread | 项目强绑定 | **否** |
| gemini_cli | enabled | codexread | 需 gemini 二进制 | **否** |
| glm_router | enabled | codexread | 需 GLM 路由环境 | **否** |
| chatgptrest | enabled | 本地 127.0.0.1:18712 | 本地服务 | **否** |
| gitnexus | enabled | 本地 127.0.0.1:18713 | 本地服务 | **否** |
| context7 | enabled | — | 需登录（当前未登录） | **否** |
| browser-use | disabled | — | 已禁用 | **否** |

#### Kimi CLI MCP

| 配置文件 | 状态 |
|---------|------|
| `~/.kimi/mcp.json` | **不存在，0 个 server** |

### 1.3 Skills 配置现状

| Skill | 位置 | 通用性 | 建议 |
|-------|------|--------|------|
| claudecode-agent-runner | `.claude/skills/` + `.home-codex-official/.claude/skills/` | Claude 专用 | 跳过 |
| markdown-to-pdf | `.claude/skills/` | 通用 | **同步** |
| web-content-extractor | `.claude/skills/` | 通用 | **同步** |
| teamdashboard | `.claude/skills/` | 可能项目专用 | 待定 |

### 1.4 API Keys 现状

| 实例 | BRAVE_API_KEY | TAVILY_API_KEY |
|------|:-----------:|:-------------:|
| `.claude` (主) | 未知 | 未知 |
| `.claude-minimax` | 有 | 有 |
| `.claude-kimi` | 无 | 无 |
| `.claude-gac` | 有 | 有 |

---

## 二、迁移方案

### 2.1 迁移原则

1. **只迁活跃配置**：废弃实例（gac、minimax）的配置不自动迁移，除非用户确认需要
2. **通用优先**：只迁移通用 MCP 和 skills，项目强绑定的不迁
3. **Kimi 双轨**：同时配置 Kimi CLI 本身 + `.claude-kimi` 实例
4. **最小可用**：先保证基础能力（搜索 + 通用 skills），高级能力后续按需添加

### 2.2 确定迁移清单

#### 必须迁移

| 配置项 | 来源 | 目标 | 理由 |
|--------|------|------|------|
| brave-search MCP | 各 Claude 实例 | Kimi CLI + `.claude-kimi` | 基础搜索能力，所有实例标配 |
| tavily MCP | 各 Claude 实例 | Kimi CLI + `.claude-kimi` | 基础搜索能力，所有实例标配 |
| BRAVE_API_KEY | `.claude-minimax` / `.claude-gac` | `.claude-kimi` | brave-search 依赖 |
| TAVILY_API_KEY | `.claude-minimax` / `.claude-gac` | `.claude-kimi` | tavily 依赖 |
| markdown-to-pdf skill | `.claude/skills/` | `.claude-kimi/skills/` + Kimi CLI | 通用文档能力 |
| web-content-extractor skill | `.claude/skills/` | `.claude-kimi/skills/` + Kimi CLI | 通用网页抓取能力 |

#### 不迁移

| 配置项 | 理由 |
|--------|------|
| Codex 的 project 专用 MCP | 强绑定 codexread 项目，Kimi 用不上 |
| Codex 的本地服务 MCP | 依赖本地 127.0.0.1 端口，Kimi 环境未部署 |
| context7 | 当前未登录，迁移过去也无法使用 |
| claudecode-agent-runner skill | Claude Code 专用机制，Kimi 不兼容 |
| teamdashboard skill | 待确认是否为项目专用 |
| `.claude-gac` 的 47 个 redteam projects | 用户声明废弃 |
| `.claude-minimax` 的 education/eggy projects | 10 天无活动，疑似旧项目 |

#### 待定（需用户确认）

| 配置项 | 说明 |
|--------|------|
| chrome-devtools MCP | 如需浏览器调试可添加，需配合 CDP 9222 端口 |
| playwright MCP | 如需网页自动化可添加 |
| teamdashboard skill | 确认是否为通用 skill |
| `.claude-minimax` 是否彻底废弃 | 10 天无活动，但配置完整，是否留档 |
| `.claude-gac` 是否有未归档数据 | 4 月 24 日还在跑 redteam，是否需要先导出 |

### 2.3 具体迁移步骤

#### Step 1：创建 `.claude-kimi/mcp.json`

```json
{
  "mcpServers": {
    "brave-search": {
      "command": "/home/yuanhaizhou/.nvm/versions/node/v22.22.0/bin/brave-search-mcp-server"
    },
    "tavily": {
      "command": "/home/yuanhaizhou/.nvm/versions/node/v22.22.0/bin/tavily-mcp"
    }
  }
}
```

#### Step 2：配置 `.claude-kimi/settings.json`

追加 API keys（保留现有 `skipDangerousModePermissionPrompt`）：

```json
{
  "env": {
    "BRAVE_API_KEY": "BSAEwaDFaY-l5N5U0CJD8BkQ76SmvzI",
    "TAVILY_API_KEY": "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"
  },
  "skipDangerousModePermissionPrompt": true
}
```

#### Step 3：创建 `.claude-kimi/skills` 软链接或复制

建议建立软链接到主实例的 skills 目录，保持统一更新：

```bash
ln -s /home/yuanhaizhou/.claude/skills /home/yuanhaizhou/.claude-kimi/skills
```

如不希望共享，可单独复制 `markdown-to-pdf` 和 `web-content-extractor`。

#### Step 4：配置 Kimi CLI MCP

```bash
kimi mcp add brave-search --command /home/yuanhaizhou/.nvm/versions/node/v22.22.0/bin/brave-search-mcp-server
kimi mcp add tavily --command /home/yuanhaizhou/.nvm/versions/node/v22.22.0/bin/tavily-mcp
```

或手动创建 `~/.kimi/mcp.json`：

```json
{
  "mcpServers": {
    "brave-search": {
      "command": "/home/yuanhaizhou/.nvm/versions/node/v22.22.0/bin/brave-search-mcp-server"
    },
    "tavily": {
      "command": "/home/yuanhaizhou/.nvm/versions/node/v22.22.0/bin/tavily-mcp"
    }
  }
}
```

#### Step 5：验证

```bash
# 验证 Kimi CLI
kimi mcp list
kimi mcp test brave-search
kimi mcp test tavily
```

### 2.4 迁移后配置对照表

| 配置项 | `.claude` (主) | `.claude-kimi` | Kimi CLI | 对齐状态 |
|--------|:-------------:|:-------------:|:--------:|:--------:|
| brave-search MCP | 有 | 待配置 | 待配置 | 待执行 |
| tavily MCP | 有 | 待配置 | 待配置 | 待执行 |
| markdown-to-pdf skill | 有 | 待配置 | 已识别 | 待执行 |
| web-content-extractor skill | 有 | 待配置 | 已识别 | 待执行 |
| BRAVE_API_KEY | 有 | 待配置 | — | 待执行 |
| TAVILY_API_KEY | 有 | 待配置 | — | 待执行 |

---

## 三、待确认事项

| # | 问题 | 影响 |
|---|------|------|
| 1 | `.claude-minimax` 是否彻底废弃？还是暂停后可能恢复？ | 决定是否保留其配置存档 |
| 2 | `.claude-gac` 的 redteam 数据是否需要先导出归档？ | 4 月 24 日还有活动，避免丢失 |
| 3 | `teamdashboard` skill 是否需要同步？ | 决定 skills 完整度 |
| 4 | 是否需要为 Kimi CLI / `.claude-kimi` 添加 chrome-devtools 或 playwright MCP？ | 决定浏览器能力覆盖 |
| 5 | `.claude-kimi` 的 skills 是软链接到主实例还是独立复制？ | 决定后续更新策略 |

---

## 四、废弃实例处理建议

| 实例 | 建议操作 | 理由 |
|------|---------|------|
| `.claude-gac` | **先归档 redteam projects，再标记废弃** | 昨日还有活动，数据可能未归档 |
| `.claude-minimax` | **观察 2 周，如无活动则归档** | 10 天无活动但配置完整，education 项目可能还有价值 |

---

*文档由 Kimi CLI 自动生成，基于 2026-04-27 的实际配置扫描。*
