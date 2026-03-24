# 2026-03-19 Codex Handoff Session Summary v2

## 1. 当前总状态

### 1.1 仓库与运行面

- 主目录：`/vol1/1000/projects/ChatgptREST`
- 当前分支：`master`
- 当前交接目标：继续只处理 `public agent facade / public MCP / live ChatGPT 风控 / cc-sessiond / premium ingress` 这条线

### 1.2 明确不要碰的边界

用户已明确要求不要碰以下 finbot worktree：

- `/vol1/1000/worktrees/chatgptrest-finbot-dev-20260318`
- `/vol1/1000/worktrees/chatgptrest-finbot-docs-clean-20260318`

本轮所有代码、文档、运维动作都只在主目录 `master` 上完成。

### 1.3 运行状态

当前 `chatgptrest` 相关服务已经全部停掉，用于止血：

- `chatgptrest-api.service`: `inactive dead`
- `chatgptrest-mcp.service`: `inactive dead`
- `chatgptrest-driver.service`: `inactive dead`
- `chatgptrest-worker-send-chatgpt@*`: `inactive dead`
- `chatgptrest-worker-send-gemini@*`: `inactive dead`
- `chatgptrest-worker-wait.service`: `inactive dead`
- `chatgptrest-maint-daemon.service`: `inactive dead`
- `chatgptrest-worker-repair.service`: `inactive dead`

额外确认：

- `systemctl --user list-jobs`: 空
- `18711` / `18712`: 无监听
- 当前 `127.0.0.1:18713` 的监听不是 ChatgptREST，而是 GitNexus：
  - `node ... gitnexus ... serve --host 127.0.0.1 --port 18713`

结论：

- 当前没有 ChatgptREST API / MCP / worker 在继续向外发问
- 服务尚未恢复

## 2. 这轮已经完成的系统性工作

下面是这几天沿着 `public agent facade` 这条线已经做完并提交到 `master` 的核心工作。

### 2.1 public agent facade / public MCP 收口

已完成：

- public MCP 默认只暴露 3 个 agent 工具：
  - `advisor_agent_turn`
  - `advisor_agent_cancel`
  - `advisor_agent_status`
- 默认不再让 coding agent 直接依赖 legacy 裸名工具：
  - `chatgptrest_consult`
  - `chatgptrest_ask`
  - `chatgptrest_ops_status`
  - 等等

相关提交：

- `085baf6` merge: bring public advisor agent facade into runtime branch
- `9f5b274` fix(mcp): bind public agent server to runtime port
- `43d9b8c` feat(mcp): auto-watch deferred agent sessions
- `d014f18` fix(agent): enforce advisor provenance and mcp client headers

相关文档：

- [2026-03-18_public_agent_facade_merge_restart_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-18_public_agent_facade_merge_restart_walkthrough_v1.md)
- [2026-03-18_coding_agent_mcp_surface_policy_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-18_coding_agent_mcp_surface_policy_v1.md)

### 2.2 premium ingress 基础骨架

已完成：

- `ask_contract`
- clarify gate
- `prompt_builder`
- post-review
- EvoMap writeback
- agent SSE / deferred delivery

相关提交：

- `6b4a098` feat(premium-ingress): add ask contract funnel front gate
- `1ea422d` test: add tests for ask contract, prompt builder, and post-review
- `0982598` feat(premium-ingress): wire prompt-builder, add clarify gate, add EvoMap writeback
- `be4e8f3` fix(agent): persist premium review signals to evomap

说明：

- 这些已经把 premium ingress 做到了“可用骨架”
- 但还没有把真正的 `LLM strategist` 主链完整落地，见后面的“未完成项”

### 2.3 Deep Research 导出质量修复

已完成：

- 如果已经拿到干净的 Word / Markdown 导出，就不再被脏 `conversation export` 覆盖
- 避免 `cite...` / `【...†...】` 把已有干净答案污染回去

相关提交：

- `8b604a4` fix(worker): preserve clean deep research export markdown

相关文档：

- [2026-03-18_deep_research_export_preserve_clean_markdown_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-18_deep_research_export_preserve_clean_markdown_v1.md)

说明：

- 目前修的是“保住已有干净导出”
- 还没有做到“自动进入 Deep Research 全屏 report 视图并优先抓正式导出”

### 2.4 附件误判修复

已完成：

- 中文斜杠片段如：
  - `/二手来源`
  - `/中/弱/推测`
  - `/行为/访谈/...`
  不再误判为附件路径
- facade 现在会把真正的附件缺失错误翻译成结构化 contract：
  - `attachment_confirmation_required`

相关提交：

- `17aa32b` fix(agent): avoid false attachment path hits in prompts
- `23c9ba3` feat(agent): return attachment confirmation contract

### 2.5 cc-sessiond 基础可用化

已完成：

- `cc-sessiond` API 路由接入
- backend adapter fallback
- `CcExecutor` 默认后端
- `prompt doc path only` 强约束
- SDK runtime 接线修复

代表性提交：

- `723830c` fix(cc-sessiond): auto-start queued session processor
- `0847fab` fix(cc-sessiond): recover pending sessions on restart
- `bf459e2` fix(cc-sessiond): enforce path-only task packets
- `9c60ff1` fix(cc-sessiond): require prompt doc path only

### 2.6 repair / autofix 风控收紧

已完成：

- `repair.autofix` 默认不再漂到 `codex1 gpt-5.4`
- 改成默认走 `gpt-5.3-codex-spark`

相关提交：

- `65a5485` fix(repair): default autofix model to codex spark

### 2.7 smoke / synthetic / low-value live ask 风控

这个是这轮最关键的止血面。

已完成：

- `chatgpt_web.ask` live smoke / test / probe 默认 fail-closed
- synthetic prompt 如：
  - `hello`
  - `test blocked state`
  - `test needs_followup state`
  在 public / advisor 正门被挡住
- old synthetic source job 不再被 `repair.check` / `repair.autofix` 反复碰

相关提交：

- `b5c1f13` fix(policy): fail-close live chatgpt smoke and dedupe worker autofix
- `fa0f6a1` fix(agent): block synthetic advisor prompts and repair churn

相关文档：

- [2026-03-18_live_chatgpt_smoke_risk_containment_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-18_live_chatgpt_smoke_risk_containment_v1.md)
- [2026-03-18_advisor_synthetic_prompt_containment_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-18_advisor_synthetic_prompt_containment_v1.md)

### 2.8 这轮最新修复：直打旁路 + prompt 污染

这是服务停机前最后一组核心修复。

已完成：

1. 封死 direct low-level live ask 旁路

- `POST /v1/jobs kind=chatgpt_web.ask` 现在默认不允许直打真实 ChatGPT 前端
- 会返回：
  - `403 direct_live_chatgpt_ask_blocked`
- 默认允许的例外只有：
  - `CHATGPTREST_DIRECT_LIVE_CHATGPT_CLIENT_ALLOWLIST`
  - `params.allow_direct_live_chatgpt_ask=true`
  - in-process `TestClient`

2. 去掉 public / advisor prompt 污染

- `routes_agent_v3._enrich_message()` 不再把 `附加上下文` 拼进最终 prompt
- `ControllerEngine._build_enriched_question()` 不再把：
  - `相关知识库参考`
  - `附加上下文`
  拼进最终问题正文

相关提交：

- `2a0f25a` fix(agent): block direct live asks and strip prompt pollution
- `7d11845` docs(agent): document direct live ask containment

相关文档：

- [2026-03-19_live_ask_bypass_and_prompt_pollution_containment_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_live_ask_bypass_and_prompt_pollution_containment_v1.md)

## 3. 已完成的排查结论

### 3.1 最近那些乱七八糟的 ChatGPT 线程是谁发的

结论：

- 不是 finbot
- 不是用户这轮输入的 `hello`
- 主要来源有两类：

1. 旧的 synthetic / smoke / BI / fault-handling 测试链

例如：

- `hello`
- `test blocked state`
- `test needs_followup state`

对应 client 往往是：

- `advisor_ask`
- `smoke_test_chatgpt_auto`

2. 直接低层旁路提交

我实际反查到了真实 job：

- `bad52f092b1149c9af7b1e711224cadd`
- `86af3886e9ba4073a447178c521af1de`

这些 job 的 `requested_by.headers` 明确显示：

- `user_agent: curl/7.88.1`
- `x_client_name: chatgptrestctl`
- `x_client_instance: codex-local`

也就是说：

- 某个 Codex / curl / chatgptrestctl 旁路直接打了 `/v1/jobs`
- 绕过了 public agent facade

### 3.2 为什么会看到“hello 还在发”

用户看到的几条 `hello`，并不是修复之后还在继续新发，而是旧进程误发的历史遗留。

关键点：

- 修复之后重新 probe，新的 live smoke 已经稳定返回：
  - `400 live_chatgpt_smoke_blocked`
- 之后仍看到旧 `hello` 线程，是因为：
  - 它们是旧 API 进程创建的
  - 后续又被 wait / repair / maint 路径触达

### 3.3 为什么 cancel 之后还会长时间 `in_progress`

当前取消机制不是抢占式取消。

行为：

- `queued` job：取消会很快终态
- `in_progress` job：只先写 `cancel_requested_at`
- 需要等 wait worker 下一次重新 claim 到这条 job，才终态为 `canceled`

所以：

- cancel 不是即时生效
- backlog 大的时候，看起来会“cancel 很久还在 in_progress”

这条还没修，是未完成项之一。

### 3.4 为什么 public agent 的回答会污染成 `--- 附加上下文 ---`

根因已经定位并修掉：

- `chatgptrest/api/routes_agent_v3.py::_enrich_message()`
- `chatgptrest/controller/engine.py::_build_enriched_question()`

旧行为会把：

- `--- 相关知识库参考 ---`
- `--- 附加上下文 ---`
- `depth: standard`
- 其他 stable_context

直接拼进最终问题正文。

现在已经改成：

- context 保留在结构化状态里
- 最终用户可见 prompt 只保留干净问题本体

## 4. cc-sessiond 当前真实状态

### 4.1 现状结论

`cc-sessiond` 不是“完全坏掉”，而是：

- 基础设施已能用
- 真实主任务没有稳定跑通
- 状态池被大量测试残留污染

### 4.2 当前问题

真实 strategist 主任务：

- `21f4e10e869d`：failed
- `04fd194171b4`：failed

失败原因：

- `Separator is found, but chunk is longer than limit`

还有一批无效 `running/pending` 会话：

- 指向已经不存在的 `/tmp/.../task_packet_v1.md`
- 更像孤儿会话或测试残留

### 4.3 判断

现在 `cc-sessiond` 的主要问题不是单个功能 bug，而是：

- 测试残留太多
- 真实业务会话和测试状态混在一起
- 队列与状态池还没有做运营级清理

### 4.4 已经做过的约束

为了防 prompt 太长继续把 executor 打爆，已经加上硬约束：

- `cc-sessiond` 现在只接受：
  - 一个 Markdown task-packet 文档路径
  - 文件名必须是版本化文档，如 `*_v1.md`
- 不再接受整段自由文本 prompt

## 5. 当前还没完成的工作

### 5.1 premium ingress strategist 还没落地完成

当前 premium ingress 还没有做到最终目标：

`raw ask -> LLM strategist -> AskStrategyPlan -> clarify -> prompt compile -> execution -> post-review -> EvoMap`

现在已经有的只是：

- `ask_contract`
- clarify gate
- `prompt_builder`
- post-review
- EvoMap writeback

缺的是：

- 真正的 `LLM strategist`
- 真正的 `AskStrategyPlan`
- strategized prompt compile 主链

### 5.2 public agent facade session 还不是 durable

虽然已经有：

- `session_id`
- status
- SSE
- MCP watcher

但 session 仍然没有做到真正 durable：

- API / MCP 重启后，session / watch 体验仍然不够强壮

### 5.3 MCP 产品化还不够完整

这是用户抱怨最强的一条。

当前已经有：

- public MCP 少量工具面
- 长任务自动 deferred
- watcher / 推送效果

但仍然没完全做到：

- restart 后自动恢复 transport
- stale MCP session 不靠人工重连
- coding agent 不会因为 transport 抖动又去乱试 API

### 5.4 Deep Research 全屏正式导出抓取还没做

现在只修到了：

- 有干净 Word / Markdown 导出时，不再被脏 export 覆盖

还没做：

- 自动点开 Deep Research 全屏 report 视图
- 优先抓正式导出
- DOCX -> Markdown 的稳定主流程

### 5.5 wait-phase cancel 需要改成更快收口

这一条直接影响运维体验。

现在 cancel 还不是抢占式，建议做成：

1. cancel_requested 的 wait job 优先回收
2. `in_progress` 的 wait-phase ask 不要继续长时间挂着

## 6. 下一步应该怎么做

按照当前状态，建议下一任 Codex 严格按这个顺序接手。

### 第一步：继续保持停机，先收 MCP/恢复策略

在没把 MCP 连接恢复逻辑做完整之前，不要急着恢复服务。

目标：

- 让 `chatgptrest-mcp` 真正可恢复
- 长任务默认后台化
- stale transport 自动恢复
- agent 不再因为 MCP 小故障去旁路直打 `/v1/jobs`

### 第二步：修 wait-phase cancel 收口

目标：

- `cancel_requested` 后更快终态化
- 避免旧线程长时间停留在 `in_progress`

### 第三步：清理 cc-sessiond 残留状态池

目标：

- 清孤儿 `running/pending`
- 区分测试 session 和真实业务 session
- 再重新发 strategist 主任务

### 第四步：重发 strategist 主任务并验收

目标：

- 把真正的 `LLM strategist` 主链做完
- 不再停留在 contract/prompt_builder skeleton

### 第五步：再决定是否恢复服务

恢复条件建议至少满足：

1. direct live ask 旁路已封死
2. prompt 污染已去掉
3. MCP transport 恢复逻辑可用
4. wait cancel 改善
5. 没有新的 synthetic `hello/test...` 线程继续出现

## 7. 这轮关键提交清单

和本次交接最相关的提交，按时间近到远列：

- `7d11845` docs(agent): document direct live ask containment
- `2a0f25a` fix(agent): block direct live asks and strip prompt pollution
- `d014f18` fix(agent): enforce advisor provenance and mcp client headers
- `96fe429` docs(ops): record advisor synthetic prompt containment
- `fa0f6a1` fix(agent): block synthetic advisor prompts and repair churn
- `b5c1f13` fix(policy): fail-close live chatgpt smoke and dedupe worker autofix
- `65a5485` fix(repair): default autofix model to codex spark
- `43d9b8c` feat(mcp): auto-watch deferred agent sessions
- `8b604a4` fix(worker): preserve clean deep research export markdown
- `23c9ba3` feat(agent): return attachment confirmation contract
- `167eedf` fix(mcp): recover agent turns after transport disconnect
- `17aa32b` fix(agent): avoid false attachment path hits in prompts
- `be4e8f3` fix(agent): persist premium review signals to evomap
- `0982598` feat(premium-ingress): wire prompt-builder, add clarify gate, add EvoMap writeback
- `6b4a098` feat(premium-ingress): add ask contract funnel front gate

## 8. 交接说明

这份 v2 是对以下旧文档的详细补充，而不是替代：

- [2026-03-18_codex_handoff_session_summary_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-18_codex_handoff_session_summary_v1.md)

如果下一任 Codex 需要快速上手：

1. 先读本文件
2. 再读：
   - [2026-03-19_live_ask_bypass_and_prompt_pollution_containment_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_live_ask_bypass_and_prompt_pollution_containment_v1.md)
   - [2026-03-18_advisor_synthetic_prompt_containment_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-18_advisor_synthetic_prompt_containment_v1.md)
   - [2026-03-18_live_chatgpt_smoke_risk_containment_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-18_live_chatgpt_smoke_risk_containment_v1.md)
3. 然后按“第 6 节”的顺序继续做
