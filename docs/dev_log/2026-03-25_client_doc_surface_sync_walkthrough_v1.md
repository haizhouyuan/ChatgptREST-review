# 2026-03-25 Client Doc Surface Sync Walkthrough v1

## 为什么要做

前面的服务端收口已经完成：

- coding agent 默认必须走 public advisor-agent MCP
- low-level ask 已加 identity / authorization / intent guard

如果客户端仓库里的 `AGENTS.md`、`docs/chatgptREST.md`、repo-local skill 仍然继续教学旧的 `chatgptrest_*_ask_submit` / `chatgptrest_job_wait` / bare `/v1/jobs`，用户仍会按旧路径重复偏航，所以必须把文档边界同步到同一语义面。

## 做了什么

1. 扫描当前客户端仓与 repo-local skills，区分“当前入口文档”与“历史 issue/归档”。
2. 只改现行入口文档，不改历史 issue 记录。
3. 把交互式 coding agent 的默认入口统一改成 public advisor-agent MCP。
4. 把 low-level `/v1/jobs` 相关示例改成 maintenance/automation-only，并补 registered identity 约束。
5. 更新 `docs/client_projects_registry.md`，把同步状态和特殊情况写清楚。

## 关键判断

- `openclaw` 主仓此前已经完成同类同步，因此本轮不重复改。
- `planning` 不只是文档，还有 repo-local skill 仍在教学旧 submit/wait 模型，所以一并同步。
- `finchat` 与 `maint/openclaw/sim-dev` 目前尚无 `HEAD`，不适合在本轮替它们做“整仓初始化提交”；因此只更新工作树并在登记簿中明确说明。

## 影响

- 对用户：当前入口文档与服务端真实 contract 不再打架。
- 对 coding agent：默认 northbound surface 更单一，减少继续误走 low-level ask 的概率。
- 对 automation：若仍需 low-level ask，会更早碰到“需要 registered identity”的明确边界，而不是文档暗示它仍是默认路径。
