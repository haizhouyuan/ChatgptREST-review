---
title: Multi Runner Tooling Report For Maint
version: v1
updated: 2026-03-11
status: completed
artifact_summary: /vol1/1000/projects/ChatgptREST/artifacts/monitor/runner_lane_probe/20260311T020101Z/summary.json
---

# 目的

把 `cc runner / Gemini CLI / Codex runner / hcom teams` 当前在这台机器上的真实可用性、失败模式、可行升级方向收成一份给 `maint` 仓库继续深入分析的输入报告。

这不是抽象架构讨论，而是基于真实 CLI smoke、真实本机配置、真实 failure artifact 的执行层评估。

# 结论先行

当前不应该把这几套工具继续混着用，更不应该让 ambient 配置直接定义默认执行面。正确方向是把它们拆成 4 条职责明确的 lane：

- `ClaudeCode / claudeminmax`：长异步 detached worker
- `Gemini no-MCP lane`：便宜的 second read / judge lane
- `Codex auth-only lane`：结构化、本地 repo-aware 的 batch lane
- `hcom`：control plane，不是默认 worker lane

一句话说：

- `Codex` 不是不能 batch，而是 ambient home 太重
- `Gemini` 不是不能 headless，而是 ambient MCP 太脏
- `hcom` 不是 worker runner，而是 orchestration control plane

# 证据范围

## 代码与文档

- [runner_lane_probe.py](/vol1/1000/projects/ChatgptREST/ops/runner_lane_probe.py)
- [test_runner_lane_probe.py](/vol1/1000/projects/ChatgptREST/tests/test_runner_lane_probe.py)
- [upgrade plan](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_multi_runner_efficiency_upgrade_plan_v1.md)
- [upgrade walkthrough](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_multi_runner_efficiency_upgrade_walkthrough_v1.md)
- [existing agent workflow note](/vol1/1000/projects/ChatgptREST/docs/ops/agent_execution_workflow_20260309.md)
- [existing cc teams lessons](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_claude_code_agent_teams_lessons_and_best_practices_v1.md)
- [existing stale status observation](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_claude_code_agent_runner_stale_status_observation_v1.md)

## 运行证据

- [probe summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/runner_lane_probe/20260311T020101Z/summary.json)
- [codex ambient stderr](/vol1/1000/projects/ChatgptREST/artifacts/monitor/runner_lane_probe/20260311T020101Z/codex_ambient.stderr.log)
- [codex auth-only stderr](/vol1/1000/projects/ChatgptREST/artifacts/monitor/runner_lane_probe/20260311T020101Z/codex_auth_only.stderr.log)
- [gemini ambient stderr](/vol1/1000/projects/ChatgptREST/artifacts/monitor/runner_lane_probe/20260311T020101Z/gemini_ambient.stderr.log)
- [gemini no-mcp stderr](/vol1/1000/projects/ChatgptREST/artifacts/monitor/runner_lane_probe/20260311T020101Z/gemini_no_mcp.stderr.log)
- [hcom raw](/vol1/1000/projects/ChatgptREST/artifacts/monitor/runner_lane_probe/20260311T020101Z/hcom_start.raw.txt)

# 真实实验结果

同一条极小 JSON smoke：

```text
Return exactly this JSON: {"ok":true,"mode":"runner_probe"}
```

结果如下：

| lane | 结果 | 关键观察 |
|---|---|---|
| `codex_ambient` | 成功 | `~20s`，`21776 tokens`，会自动拉起 MCP，全链路太重 |
| `codex_isolated` | 失败 | 空白 `CODEX_HOME` 丢失认证，直接 `401` |
| `codex_auth_only` | 成功 | `~10.6s`，`905 tokens`，不拉 MCP；这是当前最好的 Codex batch 基线 |
| `gemini_ambient` | 成功 | `~52s`，但 stderr 带 `glm_router` MCP discovery 噪声 |
| `gemini_no_mcp` | 成功 | `~39.7s`，输出干净；适合 cheap secondary-review |
| `claudeminmax` | 成功 | 结构化 JSON 稳定；当前最像合格 detached worker |
| `hcom_start` | 失败 | 默认 start 不幂等；因 Codex `notify` hook 已占用而失败 |

# 独立判断

## 1. Codex runner 的主问题不是模型，而是 ambient home 污染

当前 ambient `~/.codex/config.toml` 会带入：

- `notify = ["hcom"]`
- 多个 MCP server
- 全量本机惯用配置

所以 trivial task 也会：

- 拉起 MCP
- 打印大量 stderr 噪声
- 放大 token 消耗

本次最重要发现是：

**只带 `auth.json` 的 isolated `CODEX_HOME` 能跑通，而且成本从 `21776` tokens 下降到 `905` tokens。**

这说明：

- `Codex` 适合作 batch lane
- 但必须有专门 wrapper
- 不能继续直接拿 ambient home 做 detached runner

### 当前 Codex 还存在的残口

`auth-only` lane 虽然成功，但 stderr 里有：

- `refresh_token_reused`

这说明直接拷 `auth.json` 虽然能跑，但还不是正式、稳定、可推广的 auth bootstrap 方案。

`maint` 侧后续应重点研究：

- 官方支持的最小 auth bootstrap 方式
- 是否存在只读 session/export/login cache 方式，避免 refresh token reuse
- 如何生成 minimal `CODEX_HOME` 而不丢认证

## 2. Gemini CLI 的主问题不是可用性，而是 ambient MCP 太脏

ambient `gemini` lane 本次成功了，但 stderr 带：

- `glm_router` discovery 错误
- MCP discovery 噪声

而加上：

```bash
--allowed-mcp-server-names ''
```

后，输出显著干净，stderr 只剩：

- `Loaded cached credentials.`

这说明：

- `Gemini CLI` 最适合做 cheap second read
- 但必须有专门的 no-MCP 或最小 allowlist wrapper

`maint` 侧后续应重点研究：

- `GEMINI_CLI_HOME` / `settings.json` / allowlist 的最佳隔离方式
- 是否应默认禁用所有 MCP，再按 lane 白名单启用
- 结构化输出 contract 是否应统一成固定 JSON envelope

## 3. ClaudeCode / MiniMax 目前最接近合格 detached worker

这轮实测里，`claudeminmax` 是当前最像合格 async runner 的 lane：

- 有稳定结构化输出
- 没有 ambient MCP 污染
- detached 语义自然

但它仍有两个问题：

- wall time 不短，不适合大量微任务
- 现有 `cc runner` 仍存在 stale status 问题

也就是说：

- `Claude lane` 当前应该继续当 detached long-task worker
- 不应该继续拿来做所有辅助任务

`maint` 侧后续应重点研究：

- stale-run 判断：不能只信 `status.json`
- 应同时看 `pid liveness + heartbeat freshness + stdout growth + result file presence`
- 是否要把当前 skill runner 产品化成 repo-level runner

## 4. hcom 不该当默认 worker 执行面

这次最清楚的行为证据是：

- `hcom start` 默认失败
- 根因不是 hcom 抽风
- 而是它要安装 Codex hooks，但本机已有 `notify` hook 占用

raw 证据明确写了：

- `Codex only supports one notify command`

所以当前判断很明确：

- `hcom` 更适合作 orchestration control plane
- 不适合作默认 detached worker runner

`maint` 侧后续应重点研究：

- `hcom_preflight` 是否应成为强制入口
- 如何检测 `notify` hook 冲突
- 如何让 `hcom start` 幂等，或在冲突时优雅退化
- `--from` 外部发送者是否应该成为默认推荐模式

# 推荐 maint 侧继续做的工作

## A. 建 3 个正式 wrapper

### 1. `codex_batch`

目标：

- 自动创建 minimal `CODEX_HOME`
- 只同步必需认证材料
- 默认禁用 ambient MCP
- 默认 schema-friendly

验收：

- trivial JSON smoke token 显著低于 ambient
- 不出现 ambient MCP startup
- 不依赖人工清理宿主配置

### 2. `gemini_batch`

目标：

- 默认 `--allowed-mcp-server-names ''`
- 或明确最小 allowlist
- 固定 headless JSON 输出契约

验收：

- trivial JSON smoke 可稳定机器解析
- ambient MCP 噪声不再出现

### 3. `hcom_preflight`

目标：

- 检查 hook 冲突
- 检查 `HCOM_DIR`
- 检查身份状态
- 检查 listen/send 能否闭环

验收：

- start 失败时给出结构化原因
- 不再靠人工猜测是不是 hook / 身份 / 路径问题

## B. 统一 runner contract

当前最不一致的是：

- `cc runner` 已经有 `start/status/tail/cancel/result`
- `codex/gemini` 主要还是直接 CLI

建议 `maint` 侧继续做成统一 job contract：

- `start`
- `status`
- `tail`
- `cancel`
- `result.json`
- `events.jsonl`

这样后面 controller 才能平等管理：

- Claude worker
- Codex batch lane
- Gemini batch lane

## C. 建统一 benchmark / probe

本次 [runner_lane_probe.py](/vol1/1000/projects/ChatgptREST/ops/runner_lane_probe.py) 只是第一版。

`maint` 侧应把它升级成更正式的 benchmark：

- trivial JSON smoke
- medium structured review smoke
- long detached task smoke
- failure-path smoke
- token/latency/noise/parseability/stability 四维对比

# 我建议 maint repo 的 issue 目标

建议 issue 不要泛写成“优化多 runner”，而要明确成：

## 目标

把 `Codex / Gemini / Claude / hcom` 从 ambient CLI 工具，收成 **可批处理、可预检、可比较、可编排** 的执行层。

## 第一阶段交付

1. `codex_batch` 设计与验证
2. `gemini_batch` 设计与验证
3. `hcom_preflight` 设计与验证
4. 统一 `runner probe` benchmark

## 第二阶段交付

1. 统一 `start/status/tail/cancel/result` contract
2. status board
3. stale-run / dead-run watchdog

# 这份报告希望 maint 那边重点回答的问题

1. `Codex` 的最小可推广 auth bootstrap 应该怎么做，才能避免 `refresh_token_reused`？
2. `Gemini CLI` 最佳的 clean batch profile 是不是 `GEMINI_CLI_HOME + empty allowlist`，还是 workspace-level settings 更好？
3. `cc runner` 应该继续沿 skill runner 产品化，还是迁移到 maint repo 的统一 runner 框架？
4. `hcom` 的正确边界到底是 worker lane 还是 control plane？在这台机器上怎样才能做到真正幂等的 preflight？
5. 统一 runner contract 应该先落在 `maint`，还是继续散落在各 repo skill/script 里？

# 我对 maint 侧下一轮最有价值的建议

如果只能优先做一件事：

**先做 `codex_batch + gemini_batch + hcom_preflight`。**

原因：

- 这三件事能最快把 ambient 配置噪声切掉
- 是真实提效，而不是概念升级
- 后续再统一 contract 才不会建立在脏基线上

