# 2026-04-01 Execution Surface Authority and Retirement Matrix v1

## 1. Scope

这份 matrix 不是做“大清仓删旧层”，而是为 **planning 第一阶段目标** 冻结一版可执行的 surface 分层：

1. 哪些是当前应该被当成主线
2. 哪些应该保留，但不能再被当成默认入口
3. 哪些只是内部/维护/兼容层
4. 哪些后面可以进入 retirement backlog

这里的“retirement”一律按 **surface posture** 理解，不等于马上删代码。

## 2. Freeze Rule

本版使用 6 个分类：

- `P1 Canonical`
  - 第一阶段 planning 目标的主线 surface
- `K Secondary Keep`
  - 保留且真实有用，但不升格为第一主线
- `I Internal`
  - 内部编排或执行 substrate，不作为用户默认入口
- `M Maintenance-only`
  - 只给维护/ops/debug/受控例外
- `C Compatibility-only`
  - 兼容旧调用名/旧集成，不再扩张
- `R Retirement backlog`
  - 进入后续收口/退役候选，但现在不做破坏性动作

## 3. Executive Freeze

对于 planning 第一阶段，我建议现在就冻结以下口径：

1. `Codex / Claude Code / Antigravity` 是主工作台。
2. `tmuxagent(8702)` 是这些 workbench 的远程入口 + 控制面。
3. `Feishu / OpenClawBot` 只先做 capture / dispatch / 轻交互入口，不承诺替代主工作台。
4. ChatgptREST 对 coding agent 的 canonical northbound 仍是 public MCP `18712/mcp`。
5. `chatgpt_web.ask / gemini_web.ask / consult` 不是用户主入口，而是内部 provider/job substrate 与专项能力 lane。
6. `/v2/advisor/*`、broad/admin MCP、legacy wrapper/jobs CLI 暂不删，但都不再当第一主线叙事。

## 4. Matrix A — 用户工作侧

| Surface | 当前作用 | Freeze 等级 | 第一阶段 posture | 退休/收口结论 | 依据 |
| --- | --- | --- | --- | --- | --- |
| `Codex` | planning 长任务主工作台 | `P1 Canonical` | 主入口、主执行面 | 保留并继续主投 | 用户当前实际高频工作主线；repo policy 也把它列为 coding-agent 默认客户端 |
| `Claude Code` | 与 Codex 并列的 native workbench | `P1 Canonical` | 主入口、主执行面 | 保留并继续主投 | 用户当前真实在用；与 Codex 一样属于高保真 workbench |
| `Antigravity` | IDE 感更强的 native workbench | `P1 Canonical` | 主入口、主执行面 | 保留并继续主投 | 用户当前真实在用；文件拖拽与 IDE 交互价值明确 |
| `tmuxagent(8702)` | 远程操控 tmux pane 中的 Codex / CC | `P1 Canonical` | 远程入口 + 控制面 | 保留并继续主投 | 代码与 live 进程都表明它是 tmux pane dashboard，不是新执行层 |
| `Feishu / OpenClawBot` | 发任务、扔材料、轻交互 | `K Secondary Keep` | capture / dispatch 候选入口 | 保留，但暂不升格 | 用户明确反馈其效果目前不如 TUI / IDE |
| `OpenClaw openmind_advisor_ask` | OpenClaw 内的 slow-path cognition 工具名 | `K Secondary Keep` | 插件侧次要入口 | 保留，但不作为 planning 第一主线 | 插件仍真实打 `/v3/agent/turn`，但不是当前最优工作台 |

## 5. Matrix B — ChatgptREST Northbound / Orchestration

| Surface | 当前作用 | Freeze 等级 | 第一阶段 posture | 退休/收口结论 | 依据 |
| --- | --- | --- | --- | --- | --- |
| public advisor-agent MCP `http://127.0.0.1:18712/mcp` | coding-agent canonical northbound | `P1 Canonical` | 默认 northbound | 保留并继续主投 | `AGENTS.md`、`contract_v1.md`、`runbook.md` 都已冻结这一点 |
| `advisor_agent_turn/status/cancel/wait` | public MCP canonical tools | `P1 Canonical` | 默认工具面 | 保留并继续主投 | slim public MCP 已稳定收口为这些高层工具 |
| `/v3/agent/turn` | public facade 后端编排面 | `P1 Canonical` | canonical orchestration backend | 保留并继续主投 | 真实 central facade；public MCP 直接投影到这里 |
| `/v2/advisor/ask` | advisor ask 入口，仍可 route 到 low-level ask | `K Secondary Keep` | 保留为 advisor/internal 次主线 | 暂不退，但不再当 coding-agent 默认 northbound | 仍 live，且有真实 caller，但已不是默认 coding-agent 主入口 |
| `/v2/advisor/advise` | advisor graph 入口 | `K Secondary Keep` | 保留为 advisor/openmind 次主线 | 暂不退，但不再当 planning 第一主入口 | 仍被 advisor/openmind/部分 integrations 使用 |
| `openmind-advisor -> /v3/agent/turn` | OpenClaw 主桥 | `K Secondary Keep` | integration bridge | 保留，但不当用户主工作台 | 是真实 bridge，但属于 integration，不是 daily planning workbench |

## 6. Matrix C — Provider / Job Substrate

| Surface | 当前作用 | Freeze 等级 | 第一阶段 posture | 退休/收口结论 | 依据 |
| --- | --- | --- | --- | --- | --- |
| `chatgpt_web.ask` provider kind | ChatGPT Web 执行 substrate | `I Internal` | 内部 provider lane | 保留，不暴露为默认用户入口 | 是真实执行底座，但对 coding agent 已默认禁止直打 |
| `gemini_web.ask` provider kind | Gemini Web 执行 substrate | `I Internal` | 内部 provider lane | 保留，不暴露为默认用户入口 | 同上；也承载 Gemini 专项能力 |
| `consult` lane | 多模型双审/复核编排 | `I Internal` | 高风险专项 lane | 保留，不作日常默认入口 | 适合复核，不适合 everyday planning 主路径 |
| `/v1/jobs kind=*web.ask` | low-level job ingress | `M Maintenance-only` | 受控维护入口 | 不删，但明确降级 | docs 和 write guards 都表明 coding agent 默认不得直打 |

## 7. Matrix D — Wrapper / MCP / CLI Legacy Stack

| Surface | 当前作用 | Freeze 等级 | 第一阶段 posture | 退休/收口结论 | 依据 |
| --- | --- | --- | --- | --- | --- |
| `chatgptrest_call.py` agent mode | wrapper 经 public MCP 调高层 agent 面 | `K Secondary Keep` | 支持性 helper | 保留，但 authority 在 public MCP，不在 wrapper | 它是 helper，不是 root authority |
| `chatgptrest_call.py --no-agent --maintenance-legacy-jobs` | provider-first legacy wrapper path | `M Maintenance-only` | 仅维护/受控例外 | 不删，但明确降级 | skill 文档和 runbook 都把它限定为 maintenance-only |
| `python -m chatgptrest.cli agent` | CLI 走高层 agent 面 | `K Secondary Keep` | 支持性 helper | 保留，但不作为 repo 主叙事 | 是 helper client，不是主 authority |
| `python -m chatgptrest.cli jobs` | CLI 走 low-level jobs | `M Maintenance-only` | ops/debug power-user 工具 | 不删，但明确降级 | 仍有价值，但不应再当默认使用法 |
| broad/admin MCP `chatgptrest/mcp/server.py` | 混挂 low-level ask、consult、legacy tools、部分 agent tools | `M Maintenance-only` | admin/debug broad surface | 保留，但只给 ops/debug | 当前最大混乱来源之一，不应再当普通 coding-agent surface |
| `chatgptrest_ask` / `chatgptrest_consult` | broad MCP 旧工具名 | `C Compatibility-only` | 兼容老调用 | 停止扩张，后续进入 retirement backlog | 名称层与当前 canonical 面不一致 |
| `chatgptrest_chatgpt_ask_submit` / `chatgptrest_gemini_ask_submit` | deprecated provider-specific submit helpers | `C Compatibility-only` | 兼容老调用 | 不扩张，进入 retirement backlog | 代码和文档都已把它们降为 deprecated |

## 8. 最关键的 freeze 结果

### 8.1 现在就应该停止混用的口径

下面这些以后不应该再混叫“执行层”：

1. `Codex / Claude Code / Antigravity`
2. `tmuxagent(8702)`
3. public MCP `/v3/agent/turn`
4. `chatgpt_web.ask / gemini_web.ask / consult`

它们分别属于：

1. 主工作台
2. 远程入口 + 控制面
3. canonical northbound + orchestration backend
4. internal provider/job substrate + 专项 lane

### 8.2 第一阶段最该保护的主线

如果目标是先把 `planning/` 工作型 agent 做出来，最该保护的是：

1. native workbench 主线
2. `tmuxagent` 远程接入
3. public MCP + `/v3/agent/turn` 这条 canonical northbound
4. `chatgpt_web.ask / gemini_web.ask / consult` 只作为内部能力与专项 lane

### 8.3 第一阶段先不要做的事

1. 不要把 `Feishu / OpenClawBot` 过早承诺成可替代 Codex/IDE 的主工作台
2. 不要再把 broad/admin MCP 当普通 coding-agent surface 教给用户
3. 不要再把 low-level `/v1/jobs kind=*web.ask` 当普通 planning workflow 入口
4. 不要试图一次性删掉 `/v2/advisor/*` 或所有 legacy/helper surfaces

## 9. Retirement Backlog v1

以下 surface 建议进入后续 retirement/backlog，但现在不做破坏性动作：

1. broad/admin MCP 里的 legacy tool teaching
2. `chatgptrest_ask`
3. `chatgptrest_consult`
4. deprecated `*_ask_submit`
5. provider-first wrapper / jobs CLI 在面向普通用户文档中的默认叙事

这些东西目前更适合的 posture 是：

1. 代码仍留
2. 文档降级
3. 调用面收紧
4. 等 caller inventory 做完后再决定是否真正退役

## 10. 一句话结论

planning 第一阶段的正确收口，不是“把所有 surface 统一成一个词”，而是明确承认系统现在有四层：

1. `Codex / Claude Code / Antigravity`
2. `tmuxagent(8702)`
3. public MCP + `/v3/agent/turn`
4. internal provider/job substrate

真正该收口的是 authority 和默认 posture，而不是先急着删层。
