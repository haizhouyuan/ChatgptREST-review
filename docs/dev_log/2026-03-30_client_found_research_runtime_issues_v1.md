# 2026-03-30 Client-Found Research Runtime Issues v1

## 背景

本轮问题来自一次真实的长期工作记忆架构研究过程。客户端组合包括：

- public advisor-agent MCP
- `chatgptrestctl` / low-level `/v1/jobs`
- 会话 URL 导出与 conversation reconcile
- logged-in ChatGPT Web 会话观察

目标不是做 API smoke test，而是在真实调研任务中拿到 grounded `report_grade` / `deep_research` 答案。

## 已修复

### 1. Deep Research conversation URL 导出拿不到 widget 正文

症状：

- conversation export 顶层看起来没有可用 assistant 正文
- deep research widget-only 会话无法从 conversation URL 恢复最终答案

修复：

- 已在 `3350bdf` 修复
- 关键变更：
  - `chatgpt_web_mcp/_tools_impl.py`
  - `chatgptrest/core/conversation_exports.py`
  - `tests/test_conversation_export_reconcile.py`

结果：

- 旧的 7 个 ChatGPT 研究会话可以稳定导出并恢复答案

## 已定位并做 live 修复，但仍应补产品级防漂移机制

### 2. public advisor-agent MCP client allowlist 漂移

症状：

- public `advisor_agent_turn` 返回 `403 client_not_allowed`
- MCP server 实际 client identity 为 `chatgptrest-agent-mcp`
- API allowlist 只放行了 `chatgptrest-mcp`

定位：

- live service: `~/.config/systemd/user/chatgptrest-mcp.service`
- live env: `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env`

本轮处理：

- 已在 live env 加入 `chatgptrest-agent-mcp`
- 重启 `chatgptrest-api.service`
- 修复后 public MCP 成功跑通两条 grounded rerun

为什么仍应发 issue：

- 这是 runtime config drift，不是一次性操作失误
- 当前系统缺少启动时自检，无法主动发现“service identity 与 allowlist 不一致”

## 仍待修复

### 3. `chatgptrestctl jobs submit --client-name` 只改 body，不改 `X-Client-Name` header

复现：

- body `client.name = chatgptrestctl-maint`
- 实际 header 仍是 `X-Client-Name: chatgptrestctl`
- 服务端返回：
  - `low_level_ask_client_identity_mismatch`

结论：

- `--client-name` 目前不是完整 override，只改了 body payload
- 对 maintenance / alternate client identity 场景不可靠

影响：

- 真实运维或调试时，CLI 不能稳定代表维护态客户端身份
- 误导使用者，以为自己提交的是 `chatgptrestctl-maint`

### 4. `report_grade` wait path 会把明显未完成的 partial assistant 输出收成 completed

关键案例：

- job: `2d77fc54e582427bbcb1977ea7de299f`
- conversation: `https://chatgpt.com/c/69ca05c1-d43c-83ab-ab04-db4fdb111c64`

证据：

- `events.jsonl` 里多次出现：
  - `answer_completed_from_export`
  - `completion_guard_downgraded`
  - `wait_requeued`
- 最终以：
  - `completion_guard_completed_under_min_chars`
  - `decision_reason = "stalled"`
  收成 completed
- `answer.md` 只有 `439` chars，明显是代码执行中途的 partial answer

影响：

- 长任务会被误判为完成
- 客户端拿到的是“看起来成功、实际上被截断”的答案
- 对研究 /报告场景破坏性很高

### 5. long-running research answers 的 completion contract 仍然不够清晰

本轮观察到两类完成路径：

1. `report_grade` 会话可能长时间停在 code-execution partial state
2. `deep_research` 会话可能 conversation export 仍然缺 answer，但 worker 最终能产出 `answer.md`

这说明当前 completion contract 还不够透明：

- 客户端很难仅凭 export 判断“是否真的完成”
- `result.json` / `events.jsonl` / `answer.md` 三者的权威性不够清晰

本轮拿到答案依赖的是：

- public MCP rerun
- worker wait 到 completed
- answer artifact 真实落盘

而不是一条简单直接的 completion 语义。

## 本轮新拿到的成功结果

修复 live allowlist 后，public advisor-agent MCP 成功跑通：

### grounded report rerun

- session: `agent_sess_513efc1ced8f4530`
- job: `b64110f64822488389189413e9fdb670`
- conversation: `https://chatgpt.com/c/69ca0a6f-ede0-83a3-9f86-ef57ffc7eff6`
- answer artifact:
  - `artifacts/jobs/b64110f64822488389189413e9fdb670/answer.md`

### grounded deep research rerun

- session: `agent_sess_9dc680f2537c4227`
- job: `605a8c93f4d44abcaf570c1f854d7cc3`
- conversation: `https://chatgpt.com/c/69ca0ab9-c77c-83aa-99ff-d58343324b82`
- answer artifact:
  - `artifacts/jobs/605a8c93f4d44abcaf570c1f854d7cc3/answer.md`

## 建议发出的 GitHub Issues

1. `mcp/runtime: add guardrail for public MCP client-name allowlist drift`
2. `cli: jobs submit --client-name should override X-Client-Name header`
3. `wait/report-grade: do not complete stalled jobs with truncated partial answer`
4. `jobs/runtime: clarify completion contract across result.json, events.jsonl, answer.md, and conversation export`
