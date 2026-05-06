---
title: Multi Runner Efficiency Upgrade Plan
version: v1
updated: 2026-03-11
status: completed
artifact_summary: /vol1/1000/projects/ChatgptREST/artifacts/monitor/runner_lane_probe/20260311T020101Z/summary.json
---

# 目标

把 `cc runner`、`Gemini CLI`、`Codex runner`、`hcom teams` 从“偶尔能用的工具集合”收成“有明确分工、可批处理、可诊断、能真正省时间”的执行层。

这份计划只讨论 **执行效率与可用性**，不讨论模型质量优劣。

# 独立结论

当前最该做的不是继续把所有工具都接到默认主路径，而是先把它们拆成 **不同职责的 lane**：

- `claudeminmax / cc runner`：长任务、异步 detached worker
- `gemini no-mcp lane`：便宜的 second read / judge / reframing
- `codex auth-only lane`：结构化、本地、repo-aware 的批处理 Codex lane
- `hcom`：控制面，不是默认执行面

反过来说，当前默认 ambient 配置不适合直接当 batch baseline：

- ambient `codex` 太重
- ambient `gemini` 太脏
- `hcom start` 在这台机器上默认不幂等

# 实测基线

证据来自：

- [summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/runner_lane_probe/20260311T020101Z/summary.json)
- [runner_lane_probe.py](/vol1/1000/projects/ChatgptREST/ops/runner_lane_probe.py)

同一条极小 JSON smoke 的结果：

| lane | 结果 | 观测 |
|---|---|---|
| `codex_ambient` | 成功 | `~20s`，`21776 tokens`，默认拉起全部 MCP，太重 |
| `codex_isolated` | 失败 | 空白 `CODEX_HOME` 失去认证，`401` |
| `codex_auth_only` | 成功 | `~10.6s`，`905 tokens`，无 MCP；这是当前最有价值的 Codex batch lane |
| `gemini_ambient` | 成功 | `~52s`，但伴随 `glm_router` MCP discovery 噪声 |
| `gemini_no_mcp` | 成功 | `~39.7s`，输出干净，适合作 cheap second read |
| `claudeminmax` | 成功 | 结构化 JSON 稳定；当前最像合格 detached worker |
| `hcom_start` | 失败 | `~0.1s` 直接失败；Codex `notify` hook 已占用，默认 start 不幂等 |

# 为什么会这样

## 1. Ambient config 污染了 batch lane

`codex` 当前 ambient home 会自动带上：

- `notify = ["hcom"]`
- 多个 MCP server
- 全量本机惯用配置

所以一个极小任务也会：

- 拉起 MCP
- 增加启动噪声
- 放大 token 消耗

`gemini` 也类似，ambient lane 会自动吃本机 MCP 配置；本次实测里 `glm_router` discovery 报错，但命令仍成功。

## 2. 现在没有统一 runner contract

`cc runner` 已经接近 job runner：

- `start`
- `status`
- `tail`
- `cancel`
- `result`

但 `codex` 和 `gemini` 还主要停留在“直接 CLI 调用”层，没有同等级的作业契约。

## 3. `hcom` 现在更像 orchestration control plane

`hcom` 不适合作为“默认执行 lane”：

- 它依赖 hooks / identity / HCOM_DIR 一致性
- 本机上还和 Codex `notify` hook 有冲突
- 它更适合协调已经可靠的 lane，而不是替代它们

# 推荐目标状态

## Lane A: Claude Detached Worker

用途：

- 长时间 async review
- 大输出诊断
- 独立 patch proposal
- overnight worker

要求：

- 保持 `start/status/tail/cancel/result` 契约
- 修 stale-run 检测
- controller 永远保留 final acceptance

## Lane B: Gemini Cheap Secondary Read

用途：

- 快速 second opinion
- 外发可读性复核
- 便宜的 breadth-first decomposition
- 结构审校 / judge / reframe

要求：

- 默认用 `--allowed-mcp-server-names ''`
- 或者最小 allowlist
- 不走 ambient MCP full set

## Lane C: Codex Structured Batch

用途：

- 需要 Codex 风格 repo-aware reasoning 的批处理
- schema-constrained output
- 本地工程判断 / 决策 JSON / fix-plan synthesis

要求：

- 不用 ambient `~/.codex`
- 不用空白 home
- 用 `auth-only + minimal config` 的 isolated `CODEX_HOME`

## Lane D: hcom Control Plane

用途：

- 真正需要多 lane 协作时的调度
- 任务投递 / listen / transcript / debate / ensemble

要求：

- 先过 preflight
- 默认外部发送者用 `--from`
- 不再把“默认 `hcom start` 能跑”当假设

# 具体升级步骤

## P0：立刻可执行的操作调整

这些今天就该执行，不需要等大改：

1. 默认停止把 ambient `codex` 当微任务 lane。
2. `Codex` 批任务改走 `auth-only CODEX_HOME`。
3. `Gemini` 批任务默认加 `--allowed-mcp-server-names ''`。
4. `hcom` 默认改为 control-plane only；没有 preflight 通过前，不用它起团队主链。
5. 长 detached 任务优先走 `claudeminmax` / `cc runner`。

## P1：把 wrapper 做出来

应该新增 4 个稳定 wrapper：

1. `ops/codex_batch.sh`
   - 创建 isolated `CODEX_HOME`
   - 只同步认证材料
   - 写最小 config
   - 默认 `--sandbox read-only`
   - 默认 profile=`spark` 或 `reviewer`

2. `ops/gemini_batch.sh`
   - 默认 `--allowed-mcp-server-names ''`
   - 支持最小 allowlist
   - 固定 `--output-format json`
   - 固定 `--approval-mode plan`

3. `ops/hcom_preflight.sh`
   - 检查 `notify` hook 冲突
   - 检查 `HCOM_DIR`
   - 检查身份状态
   - 检查 hooks 是否已安装

4. `ops/runner_lane_probe.py`
   - 已新增
   - 作为今后每轮调整的统一 smoke 基线

## P2：统一 runner contract

把 `codex/gemini/claude` 都收成同一类 job：

- `start`
- `status`
- `tail`
- `cancel`
- `result.json`
- `events.jsonl`

优先顺序：

1. 先让 `codex` 和 `gemini` 拥有与 `cc runner` 一致的 artifacts layout
2. 再做统一 status board
3. 再做统一 acceptance gate

## P3：把 hcom 放回正确位置

`hcom` 不应该替代 runner。

它应该只负责：

- lane 间消息
- handoff
- debate/ensemble
- transcript/query

也就是：

- runner 负责执行
- hcom 负责编排

# 质量门槛

只有满足这些条件，某条 lane 才算“好用”：

1. trivial JSON smoke 稳定成功
2. 输出可机器消费
3. 有明确的 stderr / raw artifact
4. 有不依赖人工猜测的 preflight
5. 在这台机器上默认不会和别的 hook / MCP / ambient config 冲突

# 当前最佳实践

今天在这台机器上的最优分工是：

- 长异步任务：`claudeminmax` / `cc runner`
- 快速二审：`gemini --allowed-mcp-server-names ''`
- 结构化 Codex 批处理：isolated `CODEX_HOME` + auth-only lane
- 多开协作：`hcom` 仅在 preflight 通过后启用

# 我对后续实现的判断

如果只做一件事，优先做：

**`codex_batch.sh + gemini_batch.sh + hcom_preflight.sh`**

原因：

- 它们能直接把当前最浪费时间的 ambient 配置问题切掉
- 不需要先改大架构
- 能立刻提高真实使用效率

如果做第二件事，再做：

**统一 runner contract**

因为真正能让工具“越来越好用”的不是单个 wrapper，而是：

- 同一套 artifacts
- 同一套状态语义
- 同一套 probe / acceptance 标准

