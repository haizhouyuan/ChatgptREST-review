# Fresh Codex Client Quickstart

目标：让一个刚启动、没有维护背景信息的 Codex 客户端，能在最少上下文里正确使用 ChatgptREST。

如果你当前扮演的是这个仓库的 controller，而不是“只发起一次调用的 fresh client”，先读：

- `docs/ops/agent_execution_workflow_20260309.md`

这个 quickstart 只负责“怎么正确调用 ChatgptREST”，不负责“怎么编排 controller / subagents / runner / Gemini lanes”。

## 只看这 4 个入口

按这个顺序读，够了：

1. `AGENTS.md`
2. `docs/runbook.md`
3. `docs/client_projects_registry.md`
4. `skills-src/chatgptrest-call/SKILL.md`

如果只是要真的发起一次请求，不要继续漫游文档。

## 硬规则

- 不要直接改 `projects/ChatgptREST` 代码来“顺便修一下”。
- 不要自创 curl header 和裸 REST 写请求。
- `provider` 和 `preset` 必须显式给出，不能自己偷偷换。
- follow-up 优先传 `parent_job_id`，不要自己把旧 `conversation_url` 当成唯一真相源。
- Gemini Deep Think / Deep Research follow-up 不要手动再发一次“开始研究 / OK”；服务端会在识别到研究方案页时自动推进一次。
- 用人类问题做验收，不要发 `OK` / `ping` / `测试一下` 这种无价值请求。
- 长输出写到文件，不要指望聊天窗口承载全部结果。

## 首选调用路径

优先用 wrapper：

```bash
/usr/bin/python3 /vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --provider gemini \
  --preset pro \
  --idempotency-key fresh-codex-demo-001 \
  --question "请用两三句话解释深度研究和普通搜索的区别，并举一个适合用深度研究的家庭教育问题例子。" \
  --out-answer /tmp/fresh-codex-answer.md \
  --out-conversation /tmp/fresh-codex-conversation.json
```

可选直连 CLI：

```bash
cd /vol1/1000/projects/ChatgptREST
./.venv/bin/python -m chatgptrest.cli jobs run \
  --provider gemini \
  --preset pro \
  --idempotency-key fresh-codex-demo-001 \
  --question "请用两三句话解释深度研究和普通搜索的区别，并举一个适合用深度研究的家庭教育问题例子。" \
  --out-answer /tmp/fresh-codex-answer.md \
  --out-conversation /tmp/fresh-codex-conversation.json
```

## 如果 loopback HTTP 被 sandbox 拦了

这是 transport 约束，不是让你改成裸 curl 的理由。

允许的 fallback 只有：

- 仓库已经登记过的 ChatgptREST MCP 路径

并且必须记录：

- 为什么 wrapper / CLI 不能直连 `127.0.0.1:18711`
- fallback 走了哪条 MCP 路径
- 哪个文档还不够清楚

当前运行基线补充：

- 在这台机器的当前 ChatgptREST MCP stateless runtime 下，background wait 可能不可用。
- 这时允许用 MCP 做 submit / poll，但不要假设一定能拿到持久后台 watcher。
- 如果 wait 被前台窗口截断，记录这一点即可，不要因此改成自造 curl 或改 provider/preset。

## 成功判定

至少要拿到这些：

- 真实 `job_id`
- 最终 `status`
- `answer` 文件
- 如果请求了 `conversation`，则知道它可能晚于 `completed` 单独就绪

## Gemini Follow-up 约定

- follow-up 首选 `parent_job_id`；只有在没有 parent job 可用时才显式传 `conversation_url`。
- 对 Gemini 来说，同一逻辑会话的 thread URL 可能在服务端执行时发生 rebinding。客户端不要缓存旧 thread URL 去强行覆盖。
- 如果服务端返回 `in_progress/phase=wait`，说明 follow-up 已经进入正确线程；这时继续等同一个 `job_id`，不要新开一轮。
- 如果遇到 `needs_followup`，先看 `result.json` / `events.jsonl` 是否是研究方案页；在当前基线里，服务端会自动推进一次研究方案页，但客户端仍然要沿原 `job_id` 观察，不要自己手动补一句“开始研究”。

## 失败时要记录什么

- 读了哪些文档
- 实际跑了哪些命令
- 第一次走错是怎么走错的
- 是否因为 provider/preset/headers/transport 理解偏差失败
- 你认为最应该补在哪个入口文档里

## 冷启动验收脚本

如果你是维护者，要验这条链是不是对“新客户端”真的可用，跑：

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/codex_cold_client_smoke.py \
  --provider gemini \
  --preset pro \
  --profile cold-client-executor \
  --question "请用两句话解释为什么写自动化测试可以降低回归风险。"
```

产物会落到：

- `artifacts/cold_client_smoke/<timestamp>/`
