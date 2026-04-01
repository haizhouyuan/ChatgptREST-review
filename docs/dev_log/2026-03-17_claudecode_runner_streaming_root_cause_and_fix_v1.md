# ClaudeCode Runner Streaming Root Cause And Fix v1

Date: 2026-03-17

## Summary

`claudeminmax` 在交互终端里可用，但 `claudecode-agent-runner` 之前经常看起来像“卡死”。这次排查确认：

- 不是 `claudeminmax` 不可用
- 不是 MiniMax 鉴权失效
- 不是 runner detach 再次失效
- 核心问题是 runner 的执行模式和可观测性设计不对

## Root Cause

Runner 之前调用 Claude Code 的方式是：

```bash
claudeminmax -p "<prompt>" --output-format json
```

这个模式只有在任务完全结束后才输出单个 JSON blob。长任务期间：

- `status.json` 一直只写 `claude command running`
- `stdout.log` 在完成前基本没有可读进度
- `events.jsonl` 只有 `cmd_started`

而实际的 Claude Code 行为是：

- 进程已经在跑
- MiniMax 模型可能在 40 到 50 秒后才出现第一条可见 session/init 事件
- 如果提示词更大、更复杂，这个“首包空窗期”更长

所以之前那些 CCrunner 任务更像是“缺乏流式进度导致被误判为挂住”，而不是 runner 真的没工作。

## Fix

修复落在共享 skill 脚本，不在本仓库源码树内：

- `/vol1/1000/home-yuanhaizhou/.codex-shared/skills/claudecode-agent-runner/scripts/claude_job_start.sh`
- `/vol1/1000/home-yuanhaizhou/.codex-shared/skills/claudecode-agent-runner/scripts/claude_job_worker.sh`

调整点：

1. Worker 改成流式模式启动 Claude Code：

```bash
claudeminmax --verbose -p "<prompt>" --output-format stream-json
```

2. Worker 轮询 `stdout.log` 的最新 stream event，并把状态折叠成面向人的 message，例如：

- `waiting for first Claude stream event`
- `session initialized`
- `running tool: Bash`
- `tool returned output`

3. `events.jsonl` 现在会记录阶段性 `progress` 事件，而不是只有开始和结束。

4. `claude_result.json` 不再复制整份 stdout，而是从 stream-json 日志里提取最终 `type=result` 事件。

5. `status.json` 和 `events.jsonl` 的 JSON 写入改成 `jq` 生成，避免 message 中出现引号时把文件写坏。

## Verification

### Direct Claude CLI

直接一把执行验证成功：

```bash
cd /vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317
timeout 90s claudeminmax -p 'Reply with exactly this JSON: {"ok":true}' --output-format json
```

和：

```bash
cd /vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317
timeout 90s claudeminmax -p 'Run /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_agent_v3_routes.py and return JSON only with keys status and tests.' --output-format json
```

说明 CLI 本身没有问题。

### Runner After Fix

验证 run:

- `ccjob_20260317T064543Z_b23a17ae`
- `ccjob_20260317T064926Z_a5331ded`

实际观测到的进度链路：

- `waiting for first Claude stream event`
- `session initialized`
- `running tool: Bash`
- `tool returned output`
- `claude command completed`

对应测试命令：

```bash
/vol1/1000/home-yuanhaizhou/.codex-shared/skills/claudecode-agent-runner/scripts/claude_job_start.sh \
  --workdir /vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317 \
  --prompt-file /tmp/.../prompt.txt

/vol1/1000/home-yuanhaizhou/.codex-shared/skills/claudecode-agent-runner/scripts/claude_job_status.sh \
  --run-id ccjob_20260317T064926Z_a5331ded

/vol1/1000/home-yuanhaizhou/.codex-shared/skills/claudecode-agent-runner/scripts/claude_job_wait.sh \
  --run-id ccjob_20260317T064926Z_a5331ded --timeout-seconds 180
```

## Operational Conclusion

这次问题不应该再描述成“CCrunner 坏了”。

更准确的说法是：

- detach 问题此前已经修掉
- 这次剩下的是“非交互 print 模式缺少中间可见性”
- 在 MiniMax 路径上，首个流事件可能要几十秒后才出现
- 如果要稳定地把 Claude Code 当后台 agent 跑，必须使用 stream-json 并把关键事件回写到 status/events

## Follow-up

- 如果后续还要继续增强 runner，优先方向是把 `status` 再补一个最近 stream event 摘要字段，而不是回退到一次性 JSON 模式。
- 如果要做更强的观测，可以把 `session_id` 和最终 `result.result` 单独提取成顶层字段，减少二次解析成本。
