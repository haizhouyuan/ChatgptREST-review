# 模型配置与 Key 管理全景（2026-03-02）

## 1. 凭证集中管理

### 统一凭证文件
**路径**：`/vol1/maint/MAIN/secrets/credentials.env`（权限 600，不入 git）

| 分类 | 变量名 | 用途 |
|------|--------|------|
| **MiniMax** | `MINIMAX_API_KEY`、`MINIMAX_ANTHROPIC_BASE_URL`、`MINIMAX_MODEL` | Coding Plan API + Anthropic 兼容接口 |
| **DashScope/通义** | `DASHSCOPE_API_KEY`、`QWEN_API_KEY`、`QWEN_BASE_URL`、`QWEN_MODEL` | Advisor LLM 主通道（qwen3-coder-plus） |
| **百炼** | `BAILIAN_API_KEY` | StoryPlay 项目用 |
| **豆包/火山** | `DOUBAO_APP_ID/KEY/SECRET`、`DOUBAO_ACCESS_TOKEN`、`ARK_API_KEY/BASE_URL/MODEL`、`DOUBAO_VOLC_WEBSEARCH_API_KEY`、`HOMEAGENT_BRAIN_DOUBAO_OLD_*` | HomeAgent Android + Brain Server |
| **腾讯云** | `QCLOUD_SECRET_ID`、`QCLOUD_SECRET_KEY` | StoryPlay TTS |
| **Gemini** | `GEMINI_CODINGPLAN_MODEL`、`GEMINI_CODINGPLAN_BASE_URL` | 额度探测（当前 disabled） |
| **OpenAI** | `OPENAI_BASE_URL`、`OPENAI_MODEL` | 额度探测（当前 disabled） |
| **OpenRouter** | `OPENROUTER_API_KEY` | StoryApp 相关工作流使用 |
| **Langfuse** | `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_BASE_URL` | Advisor 观测 |
| **LangSmith** | `LANGSMITH_API_KEY`、`LANGSMITH_ENDPOINT` | 备用观测 |
| **Stitch** | `STITCH_API_KEY` | UI 设计 MCP |
| **飞书** | `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_WEBHOOK_SECRET` | Advisor 飞书卡片推送 |
| **Browser-Use** | `BROWSER_USE_API_KEY` | 浏览器自动化 MCP |

### Shell 中的 Key 引用
| 文件 | 变量 |
|------|------|
| `~/.bashrc` | `ANTHROPIC_API_KEY`、`CODEX_API_KEY`、`MINIMAX_API_KEY` |
| `~/.home-codex-official/.bashrc` | `ANTHROPIC_API_KEY`、`MINIMAX_API_KEY` |

### 跨项目凭证分布（由 credctl.py 扫描）
| 项目 | 文件 | 相关 Key |
|------|------|----------|
| homeagent/android | `local.properties` | DOUBAO 全家桶、VOLC_WEBSEARCH |
| homeagent/brain_server | `.env` | ARK_API_KEY/BASE_URL/MODEL |
| storyplay | `.env` | DASHSCOPE_API_KEY |
| storyplay | `config/tencent-tts.env` | QCLOUD 腾讯云 |
| storyapp-worktrees/reframe | (script params) | OPENROUTER_API_KEY |

### 管理工具
```bash
# 同步凭证到各工具 config
python3 /vol1/maint/MAIN/scripts/credctl.py sync

# 生成凭证清单（脱敏）
python3 /vol1/maint/MAIN/scripts/credctl.py inventory

# 额度探测 + fallback 选路
python3 /vol1/maint/MAIN/scripts/credctl.py quota-check --write-runtime-env
```

## 2. 模型路由架构

### Advisor（Coding Plan API）— LLMConnector

**主通道**：`QWEN_BASE_URL`（默认 `coding.dashscope.aliyuncs.com/v1`）+ `QWEN_API_KEY`

支持模型（OpenAI 兼容接口）：

| 模型 | 定位 |
|------|------|
| `MiniMax-M2.5` | 通用/Review/Planning |
| `qwen3-coder-plus` | 编码 |
| `qwen3.5-plus` | 通用 |
| `kimi-k2.5` | 编码/Debug |
| `glm-5` | 备选 |

**静态路由表**（ModelRouter 不可用时的 fallback）：

| 任务类型 | 模型链（优先 → 备选） |
|----------|----------------------|
| planning | gemini-cli → MiniMax-M2.5 → qwen3.5-plus |
| coding | gemini-cli → qwen3-coder-plus → kimi-k2.5 |
| debug | gemini-cli → kimi-k2.5 → MiniMax-M2.5 |
| review | gemini-cli → MiniMax-M2.5 → qwen3.5-plus |
| research | gemini-web → chatgpt-web → gemini-cli |
| report | gemini-web → chatgpt-web → gemini-cli |
| default | gemini-cli → MiniMax-M2.5 → qwen3.5-plus |

> 注：LLMConnector 只能调 API 模型，web/CLI 模型由 graph 层 MCP 调度。

**兜底**：所有 Coding Plan 模型失败后，自动 fallback 到 MiniMax Anthropic 直连（`MINIMAX_API_KEY` + `MINIMAX_ANTHROPIC_BASE_URL`）。

### ModelRouter（三源融合）
当 EvoMap + Langfuse 可用时，ModelRouter 做动态选路：
1. **EvoMap**：实时成功率、延迟、错误模式
2. **Langfuse**：质量评分、成本
3. **静态规则**：人工配置的优先级

### Web 提供方（ChatgptREST 作业队列）

| 提供方 | kind | 支持 presets | Chrome Profile |
|--------|------|-------------|----------------|
| ChatGPT Pro | `chatgpt_web.ask` | auto, pro_extended, thinking_heavy, thinking_extended, deep_research | `secrets/chrome-profile/` |
| Gemini | `gemini_web.ask` | pro, deep_think | `secrets/chrome-profile/`（复用） |
| Qwen | `qwen_web.ask` | auto, deep_thinking, deep_research | `secrets/qwen-chrome-profile/` |

## 3. 额度探测与 Fallback

### 配置
**文件**：`/vol1/maint/MAIN/config/quota_targets.json`

| Provider | 类型 | 启用 | 默认模型 |
|----------|------|------|----------|
| codex_membership | OAuth 文件存在检测 | ✅ | — |
| gemini_cli_membership | OAuth 文件存在检测 | ✅ | — |
| minimax_coding_plan | Anthropic API | ✅ | MiniMax-M2.5 |
| qwen35_coding_plan | OpenAI API | ✅ | qwen3-coder-plus |
| openai_coding_plan | OpenAI API | ❌ | gpt-5-mini |
| gemini_coding_plan | Gemini API | ❌ | gemini-2.5-pro |

**Fallback 顺序**：codex → gemini CLI → MiniMax → Qwen → OpenAI

### 探测结果
- **定时器**：`main-llm-quota-poll.timer`（每 6 小时）
- **最新结果**：`/vol1/maint/state/main_quota/latest.json`
- **活跃 Provider**：`/vol1/maint/state/main_quota/active_provider.json`
- **运行时环境**：`/vol1/maint/MAIN/secrets/runtime.env`
- **历史快照**：`/vol1/maint/state/main_quota/snapshots/`（数量随轮询持续增长）

当前活跃：**codex_membership**（健康，reason: `first_healthy_in_order`）

## 4. systemd 凭证注入

ChatgptREST systemd 服务通过 drop-in 注入 Langfuse 凭证：
- `ops/systemd-drop-ins/10-langfuse.conf` → 自动从 `credentials.env` 读取 `LANGFUSE_*`
- Python `observability/__init__.py` 在 import 时自动加载

## 5. 待改进项

| # | 项目 | 说明 |
|---|------|------|
| 1 | OpenAI/Gemini API 未启用 | `openai_coding_plan` 和 `gemini_coding_plan` 在 quota_targets 里 disabled |
| 2 | quota snapshots 无限增长 | 快照数量持续增长，需要加 rotation/保留策略 |
| 3 | .bashrc 明文 key | ANTHROPIC_API_KEY/CODEX_API_KEY 仍直接写在 .bashrc 中 |
