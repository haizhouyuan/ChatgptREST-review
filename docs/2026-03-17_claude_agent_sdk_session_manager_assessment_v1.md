# Claude Agent SDK Session Manager Assessment v1

Date: 2026-03-17

## Executive Summary

结论先说：

- **方向是对的**：如果要把现在这个过于简单的 shell runner 升级成真正可用的长期后台 agent 执行层，官方 **Claude Agent SDK** 是比纯 shell detach 脚本更合适的底座。
- **但你贴的方案不能直接照抄**：它把 SDK 说得太“神”了，很多真正需要的工程能力仍然要我们自己做。
- **更关键的是，当前这台机器上的 `claudeminmax` wrapper 不能直接当 Python SDK 的 backend**。我本地复现到了明确兼容性错误：SDK 会传 `--setting-sources`，而当前 wrapper 背后的 Claude Code CLI `1.0.110` 不认识这个参数。
- **官方 SDK 本身是能工作的**。我在临时 venv 里安装了官方 `claude-agent-sdk`，用它自己的 bundled CLI 做了最小 query proof-of-concept，实际成功返回结果。

所以正确结论不是“别用 SDK”，而是：

- **短期**：继续用已经修好的 runner 做后台执行
- **中期**：新建一个真正的 `cc-sessiond` / `cc-agentd`，底座用官方 Python Agent SDK
- **切换前提**：先把 CLI/backend 兼容性拆清楚，不能直接把当前 `claudeminmax` 路径硬塞给 SDK

## What The Official SDK Actually Provides

官方文档确认，Claude Agent SDK 现在已经提供这些能力：

- Python SDK：`pip install claude-agent-sdk`
- TypeScript SDK：也有官方包，但当前更适合做服务端 session 管理的是 Python 路线
- `query(...)`：异步流式消息接口
- `ClaudeSDKClient`：长生命周期 client，支持程序化多 session
- session 相关控制项：
  - `continue_conversation`
  - `resume`
  - `fork_session`
  - `session_id`（client.query 时可显式指定）
- 进度/输出控制：
  - `include_partial_messages`
  - `output_format`
  - `hooks`
  - `plugins`
  - `agents`
- 运行控制：
  - `cwd`
  - `cli_path`
  - `env`
  - `max_turns`
  - `max_budget_usd`
  - `permission_mode`
  - `setting_sources`

这说明它不是一个“只能一问一答”的轻薄 wrapper，确实已经具备构建 session service 的基础。

## Local Validation

### 1. Local Claude Code CLI

本机当前 `claudeminmax` 使用的 Claude Code 版本：

```text
1.0.110
```

直接终端调用可用：

```bash
cd /vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317
claudeminmax -p 'Reply with exactly this JSON: {"ok":true}' --output-format json
```

以及：

```bash
cd /vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317
claudeminmax -p 'Run /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_agent_v3_routes.py and return JSON only with keys status and tests.' --output-format json
```

都能成功。这再次证明：`claudeminmax` 本身没坏。

### 2. Official Python Agent SDK With Bundled CLI

我在临时 venv 中安装了官方 SDK：

```bash
python3 -m venv /tmp/...
pip install claude-agent-sdk
```

然后运行最小 query proof-of-concept：

```python
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
```

实际成功返回：

```json
{"ok":true}
```

这说明：

- 官方 SDK 在这台机器上是可用的
- API key / 环境没有阻止 SDK 正常工作
- “SDK 根本不能落地” 这个判断不成立

### 3. Official Python Agent SDK With `cli_path=claudeminmax`

我又做了关键对照实验：强制 SDK 走当前 `claudeminmax` wrapper：

```python
ClaudeAgentOptions(
    cwd=Path('/vol1/1000/projects/ChatgptREST'),
    cli_path='/home/yuanhaizhou/.local/bin/claudeminmax',
    max_turns=1,
)
```

结果失败，报错：

```text
error: unknown option '--setting-sources'
```

调用栈来自官方 `claude_agent_sdk`，说明 SDK 在控制 transport 时会向 CLI 传内部控制参数，而当前 wrapper 指向的本地 Claude Code CLI 版本不兼容这组参数。

这个结论很重要：

- **官方 SDK 可用**
- **当前 `claudeminmax` backend 不能直接拿来给 SDK 用**

## Why The Proposed CCSessionManager Is Not Enough

你贴的那版 `CCSessionManager` 可以当概念草图，但离可用系统还差很多：

1. **状态只在内存里**
   - 进程重启，所有 session 丢失
   - 没有 durable store，没有 orphan recovery

2. **`cancel()` 是假的**
   - 只是把 state 改成 `CANCELLED`
   - 实际后台 `asyncio.create_task(...)` 还在跑

3. **没有 job artifact discipline**
   - 没有 request / result / events / stderr / raw stream 的统一落盘约定
   - 无法对齐我们现在已有的 run evidence 模型

4. **没有多 workdir / 多客户端隔离**
   - Codex / OpenClaw / Antigravity / Claude Code 的工作目录、权限模式、工具集都不同

5. **没有真正的 queue / admission control**
   - 没有 session concurrency cap
   - 没有 per-user / per-client 限制
   - 没有 budget guard

6. **没有 structured stream persistence**
   - 只把部分 message append 到 list
   - 丢掉了大量事件语义，后续排障会非常差

7. **没有 restart-safe session registry**
   - session_id 只是字典 key
   - 没有租约、TTL、恢复、重绑逻辑

8. **没有 backend compatibility story**
   - 它默认假设 SDK 直接可跑
   - 但我们本机已经证明 `cli_path=claudeminmax` 当前不兼容

所以，这个方案的价值在于“方向”，不是“可直接实现”。

## The Real Architecture We Should Build

不是继续加 shell 脚本，而是做一个真正的 **`cc-sessiond`**：

```text
Clients
- Codex
- OpenClaw / OpenMind
- Antigravity
- manual CLI wrappers

      |
      v
cc-sessiond
- session registry
- run store
- event log
- status API
- cancel / wait / tail
- backend routing
- budget / concurrency controls

      |
      +--> sdk_official backend
      |    - official Python Agent SDK
      |    - bundled compatible Claude CLI
      |
      +--> cli_wrapper fallback backend
           - current claudeminmax runner path
           - for lanes that still depend on current wrapper/relay setup
```

### Why This Is Better

- Session state becomes durable
- Clients all talk to one service contract
- We stop conflating “run orchestration” with “shell launch”
- We can keep the current runner as fallback while migrating
- We can add SDK-only features incrementally:
  - hooks
  - plugins
  - custom agents / subagents
  - structured outputs
  - cost ceilings

## Recommended Implementation Plan

### Phase 0: Keep The Current Runner, But Only As Fallback

This is already partly done:

- stream-json progress is now wired into the shared runner
- status/events are now meaningful

Do not throw this away yet. It is still the only confirmed backend for the current `claudeminmax` path.

### Phase 1: Build `cc-sessiond` On Official Python Agent SDK

Language choice: **Python**

Reason:

- official Python surface is clear and locally verified
- `ClaudeSDKClient` and options surface are good enough
- our orchestration stack is already Python-heavy

Minimum service components:

- SQLite session registry
- run directory per session
- NDJSON raw event log
- normalized `status.json`
- normalized `result.json`
- explicit cancellation via task handle
- HTTP or local CLI interface:
  - `create`
  - `status`
  - `tail`
  - `wait`
  - `cancel`

### Phase 2: Support Two Backends

Backend A: `sdk_official`

- uses official SDK defaults / bundled CLI
- the first production-grade path for sessiond

Backend B: `cli_wrapper`

- uses current `claudeminmax` runner
- for tasks that still depend on current wrapper / relay semantics

This dual-backend phase is important. It avoids a hard cutover.

### Phase 3: Solve `claudeminmax` Compatibility Explicitly

Do not assume this is trivial.

At least one of these must happen:

1. Upgrade local Claude Code CLI to a version compatible with current Agent SDK control flags
2. Stop using `cli_path=claudeminmax` in SDK mode, and instead configure the official CLI/backend in a supported way
3. Split “provider config” from “wrapper executable” so SDK can still invoke a compatible CLI binary while inheriting the right environment

Until one of these is resolved, **`claudeminmax` cannot be the direct SDK backend**.

### Phase 4: Migrate Clients

After `cc-sessiond` is real:

- OpenClaw / OpenMind should stop calling raw runner scripts
- Codex automation should stop inventing run directories itself
- Antigravity should target the same session contract

That is the point where the ecosystem gets simpler.

## Decision

### Should we replace the current runner with Agent SDK right now?

**No.**

### Should we build the next-generation runner/session layer on top of Agent SDK?

**Yes.**

### Should we implement the pasted in-memory `CCSessionManager` as-is?

**No.**

It is too thin and ignores the exact problems that made the current runner weak in the first place.

## Source Notes

Primary sources reviewed:

- Anthropic official Agent SDK overview:
  - `https://docs.anthropic.com/en/docs/claude-code/sdk`
- Anthropic Python SDK docs:
  - `https://docs.anthropic.com/en/docs/claude-code/sdk/python`
- Anthropic session management docs:
  - `https://docs.anthropic.com/en/docs/claude-code/sdk/session-management`
- Anthropic TypeScript SDK docs:
  - `https://docs.anthropic.com/en/docs/claude-code/sdk/typescript`
- GitHub issue showing `--setting-sources` incompatibility reports similar to the local failure mode:
  - `https://github.com/anthropics/claude-code/issues/186`

Local validation performed on this host:

- direct `claudeminmax` one-shot success
- official SDK + bundled CLI success
- official SDK + `cli_path=claudeminmax` failure with `unknown option --setting-sources`
