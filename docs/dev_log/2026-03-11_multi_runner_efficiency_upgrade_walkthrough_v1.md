---
title: Multi Runner Efficiency Upgrade Walkthrough
version: v1
updated: 2026-03-11
status: completed
artifact_summary: /vol1/1000/projects/ChatgptREST/artifacts/monitor/runner_lane_probe/20260311T020101Z/summary.json
---

# 本次做了什么

我没有继续凭印象谈 `cc runner / gemini cli / codex runner / hcom`，而是做了 3 件事：

1. 直接读了现有 skill / runner / backend 代码。
2. 跑了真实 smoke，而不是只看代码。
3. 新增了一个统一 probe，把这些 smoke 收成同一份 JSON 证据。

新增文件：

- [runner_lane_probe.py](/vol1/1000/projects/ChatgptREST/ops/runner_lane_probe.py)
- [test_runner_lane_probe.py](/vol1/1000/projects/ChatgptREST/tests/test_runner_lane_probe.py)

对应 artifact：

- [probe summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/runner_lane_probe/20260311T020101Z/summary.json)

# 实际验证了什么

## 1. Claude / MiniMax lane

命令：

```bash
claudeminmax -p 'Return exactly this JSON: {"ok":true,"mode":"runner_probe"}' --output-format json
```

结果：

- 成功
- 输出机器可读
- 本次最新 run 的 `duration_ms=11096`
- 但总 wall time 仍在 `~57s`

判断：

- 适合 detached async worker
- 不适合拿来做大量极小微任务

## 2. Codex ambient lane

命令：

```bash
codex exec --skip-git-repo-check --sandbox read-only -o out.json -
```

结果：

- 成功
- 但自动拉起 MCP
- trivial JSON smoke 仍消耗 `21776 tokens`

判断：

- 这不是 Codex 模型本身太重
- 是 ambient `~/.codex/config.toml` 把 batch lane 拖重了

## 3. Codex isolated empty home

做法：

- 临时 `HOME`
- 临时空白 `CODEX_HOME`

结果：

- 失败
- 401 Unauthorized

判断：

- “干净 lane” 方向是对的
- 但不能是空白 home
- 必须带 auth bootstrap

## 4. Codex auth-only lane

做法：

- isolated `CODEX_HOME`
- 只复制 `~/.codex/auth.json`
- 不带 ambient config / MCP

结果：

- 成功
- trivial JSON smoke 只用 `905 tokens`
- 从 ambient `21776` 下降到 `905`

判断：

- 这是真正可推广的 Codex batch baseline
- 当前还会出现 `refresh_token_reused` 噪声，说明 auth bootstrap 还需要再正规化

## 5. Gemini ambient lane

命令：

```bash
gemini -p 'Return exactly this JSON: {"ok":true,"mode":"runner_probe"}' --model gemini-2.5-pro
```

结果：

- 成功
- 但 stderr 带 `glm_router` MCP discovery 报错

判断：

- Gemini 不是不能用
- 问题是 ambient MCP 太脏

## 6. Gemini no-MCP lane

命令：

```bash
gemini -p 'Return exactly this JSON: {"ok":true,"mode":"runner_probe"}' --model gemini-2.5-pro --allowed-mcp-server-names ''
```

结果：

- 成功
- stderr 只剩 `Loaded cached credentials.`

判断：

- 这是 Gemini 的正确 cheap auxiliary lane

## 7. hcom start

命令：

```bash
bash .../hcom_start.sh --raw-out ...
```

结果：

- 失败
- raw 输出明确提示：
  - Codex `notify` hook 已占用
  - 默认 `hcom start` 不是幂等的

判断：

- `hcom` 现在不能当默认执行面
- 它应该被放回 orchestration control plane

# 为什么新增 probe

因为这类问题如果只靠散乱命令，很快就会再次失真。

这次 probe 的价值在于：

- 用同一条 prompt 对所有 lane 做 smoke
- 统一记录 `returncode / elapsed / stdout / stderr / parsed_output`
- 把“这个 lane 适合做什么”收成可比结论

# 当前最有价值的经验

1. `Codex` 最大问题不是模型，而是 ambient home 太重。
2. `Gemini` 最大问题不是 headless，而是 ambient MCP 太脏。
3. `ClaudeCode/minimax` 当前最适合做 detached worker。
4. `hcom` 不是 worker runner，而是 control plane。
5. 今后任何 runner 讨论，都应该先过 `runner_lane_probe.py`，再谈是否“好用”。

# 我建议的下一步

直接进入 3 个 wrapper：

1. `codex_batch.sh`
2. `gemini_batch.sh`
3. `hcom_preflight.sh`

如果这 3 个做完，再继续统一 job contract。
