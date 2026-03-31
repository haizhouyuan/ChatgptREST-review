# 2026-03-25 Client Doc Surface Sync v1

## 目标

把当前仍在教学 legacy bare MCP tool / low-level `/v1/jobs` 的客户端入口文档收口到统一边界：

- 交互式 coding agent 默认只走 public advisor-agent MCP
- low-level `/v1/jobs kind=*web.ask` 只保留给 explicit automation / maintenance
- 若仍命中 low-level ask，必须是已登记来源身份

## 本次同步范围

- `codexread`
- `homeagent`
- `homeagent/homeagent-android-stitch-ui`
- `planning`
- `research`
- `storyplay`
- `finchat`
- `maint/openclaw/sim-dev`

## 实际收口内容

- `AGENTS.md` / `README.md` / `docs/chatgptREST*.md` 中，凡是给 Codex / Claude Code / Antigravity 的默认接入说明，统一改为：
  - MCP 端点：`http://127.0.0.1:18712/mcp`
  - 默认工具：`advisor_agent_turn`、`advisor_agent_status`、`advisor_agent_wait`、`advisor_agent_cancel`
- 移除“把 `chatgptrest_chatgpt_ask_submit` / `chatgptrest_gemini_ask_submit` / `chatgptrest_job_wait` 当 coding agent 默认接口”的教学语义。
- 对仍需保留 low-level `/v1/jobs` 的文档，改为 maintenance/automation-only，并补 provenance / registered identity 约束。
- `planning` 的 repo-local skills 也已同步：
  - `skills-src/chatgptrest-call/SKILL.md`
  - `skills-src/ppt-banana-review-loop/SKILL.md`

## 特殊情况

- `openclaw` 主仓的当前文档此前已同步到 public advisor-agent MCP first，本轮未再重复改动。
- `~/.codex-shared/skills` 已扫描，没有发现需要同步的 ChatgptREST 旧入口教学。
- `finchat` 与 `maint/openclaw/sim-dev` 当前仓库没有 `HEAD`，因此本轮只能更新工作树文件，不能在各自仓做增量 commit 固化。

## 结果口径

- ChatgptREST 侧的“客户端文档登记簿”已更新。
- 当前主用客户端的现行入口文档，已不再把 legacy bare MCP tool 或 low-level `/v1/jobs` 当 coding agent 默认入口。
