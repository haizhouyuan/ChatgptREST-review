# ChatgptREST / OpenClaw 模型路由与 Key 治理蓝图 v1

日期：2026-03-16

## 1. 文档定位

这份文档是当前阶段关于“模型路由、provider fallback、凭证治理、运行态对齐、验收标准”的母文档。

它有 4 个目的：

1. 把这次已经核实的运行事实收敛成一个可执行的统一说明。
2. 明确哪些问题已经处理，哪些问题仍然是结构性缺口。
3. 定义未来整改时必须遵守的高标准，不接受“临时能跑”的最小实现。
4. 为后续版本文档、代码整改、运维验证、客户端同步提供唯一父规范。

本蓝图不替代原始清单类文档，但优先级高于零散 dev log。

关联文档：

- `docs/model_and_key_inventory.md`
- `docs/dev_log/docs_model_routing_for_antigravity_2026-02-28.md`
- `docs/reviews/09_OPENMIND_LATEST_MERGED_REVIEW_BRIEF_20260228.md`
- `docs/dev_log/2026-03-16_openclaw_agent_model_fallback_reorder_walkthrough_v1.md`

## 2. 本轮已完成的变更

截至 2026-03-16，本轮已经完成并验证：

1. OpenClaw 托管 agent 默认链路已统一为：
   `MiniMax-M2.5 -> qwen3-coder-plus -> Gemini`
2. 代码生成入口 `scripts/rebuild_openclaw_openmind_stack.py` 已把上述顺序写入：
   - `main`
   - `maintagent`
   - `finbot`
3. ChatgptREST `LLMConnector` 的直接 Coding Plan 调用链已改为：
   - API 第一跳：`MiniMax-M2.5`
   - API 第二跳：`qwen3-coder-plus`
   - 第三跳：Gemini
   - 最终救援：MiniMax Anthropic 直连
4. 相关测试已补齐并通过：
   - `tests/test_rebuild_openclaw_openmind_stack.py`
   - `tests/test_llm_connector.py`

相关提交：

- `5906a17` `Align agent model fallback order`
- `dda6654` `Record model routing walkthrough`

## 3. 2026-03-16 已核实的运行态事实

### 3.1 OpenClaw 当前 live agent 路由

实测 `openclaw models status --agent {main,maintagent,finbot} --json` 后，3 个托管 agent 当前一致：

| Agent | resolvedDefault | fallbacks |
|---|---|---|
| `main` | `minimax/MiniMax-M2.5` | `qwen-coding-plan/qwen3-coder-plus` → `google-gemini-cli/gemini-2.5-pro` |
| `maintagent` | `minimax/MiniMax-M2.5` | `qwen-coding-plan/qwen3-coder-plus` → `google-gemini-cli/gemini-2.5-pro` |
| `finbot` | `minimax/MiniMax-M2.5` | `qwen-coding-plan/qwen3-coder-plus` → `google-gemini-cli/gemini-2.5-pro` |

真实运行配置路径：

- `/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json`

当前 `openclaw.json` 中，`models.providers.minimax` 与 `models.providers.qwen-coding-plan` 已被生成，且在源配置里保留为 env 引用而不是明文：

- `minimax.apiKey = ${MINIMAX_API_KEY}`
- `qwen-coding-plan.apiKey = ${QWEN_API_KEY}`

### 3.2 OpenMind / Advisor 当前执行现实

已核实的行为仍然存在多层分裂：

1. OpenClaw `openmind-advisor` 插件默认模式仍是 `advise`，不是 `ask`。
2. `/v2/advisor/ask` 的 route 映射仍以 ChatGPT Web 为主，不等于当前 OpenClaw agent 默认链。
3. `report_graph` 会通过 `RoutingFabric` 取 LLM。
4. `quick_ask` 仍调用 `_get_llm_fn("default")`，没有显式走 `quick_qa`。
5. `deep_research` 仍调用 `_get_llm_fn("research")`，而不是 `deep_research` task profile。
6. `funnel` 仍优先直接拿 `llm_connector`，没有被完整纳入统一路由语义。
7. `RoutingFabric._invoke_api()` 当前没有按 candidate provider 精准下发 provider/model，而是把 API/NATIVE_API 都折叠给 `LLMConnector`。

结论：

- OpenClaw agent 默认链已经对齐。
- OpenMind Advisor 内部各 route 的真正执行语义仍未完全统一。

### 3.3 凭证与配置当前现实

当前凭证与 provider 元数据的落点并不单一。

已核实路径与权限：

| 路径 | 权限 | 备注 |
|---|---:|---|
| `/vol1/maint/MAIN/secrets/credentials.env` | `600` | 高优先级凭证源 |
| `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env` | `640` | ChatgptREST 运行态 env |
| `/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json` | `600` | OpenClaw 顶层配置 |
| `/home/yuanhaizhou/.home-codex-official/.openclaw/agents/main/agent/models.json` | `600` | agent 层 provider catalog |
| `/home/yuanhaizhou/.home-codex-official/.openclaw/agents/finbot/agent/models.json` | `600` | agent 层 provider catalog |

已核实的关键事实：

1. 顶层 `openclaw.json` 使用 env 引用。
2. `main/agent/models.json` 中，`minimax` 与 `qwen-coding-plan` provider 已经被 materialize，且 `apiKey` 不再是 env 引用。
3. `finbot/agent/models.json` 中存在 `minimax`、`minimax-portal`、`openrouter` 等 provider 遗留信息。
4. `maintagent/agent/models.json` 当前不存在，本质上依赖默认配置继承。
5. `openclaw models status` 对某些自定义 provider 的 provenance 显示并不稳定，尤其是 API key provider 与 `models.json`/继承路径的对应关系容易误导运维判断。

结论：

- 当前系统已存在“顶层配置用 env 引用，但 agent 层 materialized 文件保留实值”的密钥复制问题。
- 这不是文档问题，而是必须治理的结构性风险。

## 4. 核心发现矩阵

| ID | 严重级别 | 发现 | 当前影响 | 结论 |
|---|---|---|---|---|
| F1 | Critical | 路由源不唯一：OpenClaw agent config、`routing_profile.json`、`LLMConnector`、`/ask` route map 各有一套 | 容易出现“声明路由”和“实际执行”不一致 | 必须收敛为单一 contract |
| F2 | High | `openmind-advisor` 默认走 `advise`，而 `/ask` 语义是另一套 | 同名“advisor”入口在不同模式下行为差异大 | 必须统一 contract 与可观察性 |
| F3 | High | `/v2/advisor/ask` 仍偏 ChatGPT Web preset map | 与当前 agent 默认链和 Coding Plan 策略脱节 | 必须重写为 contract 驱动 |
| F4 | High | `quick_ask` 仍走 `"default"` task type | 无法精确表达 quick_qa 的速度/成本策略 | 必须改成显式 `quick_qa` |
| F5 | Critical | `deep_research` 仍传 `"research"`，而配置里没有该 profile | 实际掉到 default 语义 | 必须改成 `deep_research` |
| F6 | Critical | `funnel` 未完整接入统一 RoutingFabric 语义 | 专门路线与公共路由栈割裂 | 必须纳管 |
| F7 | Critical | `RoutingFabric._invoke_api()` 忽略 provider-specific invoke 语义 | API 与 Native API candidate 只是在表面排序 | 必须做 provider-aware invoke |
| F8 | High | 顶层 env 引用与 agent 层 `models.json` materialized secrets 并存 | API key 重复落盘，扩大泄露面 | 必须消除明文复制 |
| F9 | High | provider provenance / status 输出对 API-key provider 不够清晰 | 排障会误判 provider 是否真正生效 | 必须增强 status/audit |
| F10 | High | `chatgptrest.env` 权限为 `640`，且承担敏感运行配置 | 运行用户组面暴露不必要 | 应收紧到 `600` 或拆分 secret/non-secret |
| F11 | Medium | 仍有历史 provider 遗留，如 `minimax-portal`、旧 OAuth profile | 增加选路噪音和运维混淆 | 必须清理遗留状态 |
| F12 | Medium | telemetry 默认模型仍基于 `main` 的静态默认值而非真实每次命中 provider | 观测层不能还原真实路由 | 必须记录 actual selected provider/model |
| F13 | Medium | quota/health 决策与 OpenClaw/Advisor 实际调用链没有统一闭环 | “健康”不代表“当前链真的会命中” | 必须统一健康与执行事实 |
| F14 | Medium | 客户端文档与服务端路由演进不同步的风险高 | 外部使用者会按过期语义接入 | 必须建立同步流程 |

## 5. 目标架构

目标不是“把几处顺序改成一样”，而是建立 4 层明确的治理面。

### 5.1 Policy Plane

唯一职责：定义“在什么任务语义下，允许哪些 provider/model，以什么顺序、在什么条件下 fallback”。

要求：

1. 只有一个主 contract 文件。
2. 所有 route 名称、task type、agent 默认模型、fallback 规则都从这个 contract 生成。
3. 任何代码不得私自写一份静态路由表。

建议新增：

- `config/model_routing_contract_v1.json`

建议 contract 至少包含：

- route id
- task type
- primary chain
- allowed fallbacks
- specialist override
- timeout policy
- health gate
- cooldown policy
- observability labels

### 5.2 Credential Plane

唯一职责：定义密钥从哪里来、允许去哪里、不允许去哪里、如何轮换、如何审计。

要求：

1. 单一事实源：`/vol1/maint/MAIN/secrets/credentials.env`
2. 运行态派生文件可以存在，但必须是生成产物，不允许人工散落维护。
3. 不允许在 agent-specific `models.json` 中长期保留明文 API key。
4. `.bashrc` 不得承担正式生产密钥分发职责。

### 5.3 Execution Plane

唯一职责：按 contract 执行，并把“最终命中的 provider/model/fallback reason”真实记录出来。

要求：

1. `RoutingFabric` 必须能真实调用选中的 provider，而不是只做排序展示。
2. `LLMConnector`、MCP Web、CLI provider 的执行路径必须被统一包装。
3. `advise` 与 `ask` 的路由语义必须在 contract 层显式映射。

### 5.4 Observability Plane

唯一职责：回答“这次到底用了谁、为什么、失败在哪一跳、下一跳为什么被选中”。

要求：

1. 记录 route decision。
2. 记录 actual winner。
3. 记录 fallback cause。
4. 记录 provider health snapshot。
5. 记录 auth source classification（OAuth / env / generated runtime / explicit secret store）。

## 6. 统一路由标准

### 6.1 Managed OpenClaw Agent Default Chain

这个层面已经按用户要求落地，后续不得回退：

| 范围 | Primary | Fallback 1 | Fallback 2 |
|---|---|---|---|
| `main` | `minimax/MiniMax-M2.5` | `qwen-coding-plan/qwen3-coder-plus` | `google-gemini-cli/gemini-2.5-pro` |
| `maintagent` | `minimax/MiniMax-M2.5` | `qwen-coding-plan/qwen3-coder-plus` | `google-gemini-cli/gemini-2.5-pro` |
| `finbot` | `minimax/MiniMax-M2.5` | `qwen-coding-plan/qwen3-coder-plus` | `google-gemini-cli/gemini-2.5-pro` |

### 6.2 Advisor Canonical Route Policy

后续必须区分“agent 默认链”和“specialist route”。

建议统一为：

| Route / Task | Primary | Fallback 1 | Fallback 2 | 备注 |
|---|---|---|---|---|
| `default` | MiniMax | Qwen Coder | Gemini | 普通问答、分析、报告草稿默认统一 |
| `quick_qa` | MiniMax | Qwen Coder | Gemini | 不再偷用 `default` 字符串 |
| `coding` | MiniMax | Qwen Coder | Gemini | 若后续需要 coding specialist，必须在 contract 显式声明 |
| `analysis` | MiniMax | Qwen Coder | Gemini | 统一人类可理解的默认策略 |
| `funnel` | MiniMax | Qwen Coder | Gemini | 先纳入统一栈，再谈专用优化 |
| `report_writing` | MiniMax | Qwen Coder | Gemini | 如果要给 Web research 特权，必须单列 specialist override |
| `deep_research` | ChatGPT Deep Research | Gemini Deep Research | Qwen summarizer | 唯一允许的 specialist route，必须显式可观察 |

原则：

1. specialist route 只能是显式例外，不能是隐式分叉。
2. specialist route 也必须落在同一 contract，不允许散落在代码里。
3. `quick_ask`、`deep_research`、`funnel`、`report` 不得再各写一套私有字符串。

### 6.3 Direct Coding Plan Chain

对直接 API 调用的统一标准：

1. 第一跳：`MiniMax-M2.5`
2. 第二跳：`qwen3-coder-plus`
3. 第三跳：Gemini
4. 最终救援：可保留 MiniMax Anthropic direct，但必须标注为 disaster-recovery lane，而不是日常 fallback

## 7. Key 治理高标准

### 7.1 单一事实源

正式密钥事实源只允许：

- `/vol1/maint/MAIN/secrets/credentials.env`

允许的派生产物：

- `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env`
- `runtime.env`
- systemd drop-in 注入
- OAuth token store / auth-profiles（仅限 OAuth token）

不允许成为事实源的地方：

- `~/.bashrc`
- `~/.home-codex-official/.bashrc`
- agent-specific `models.json`
- 临时 shell 导出的长期环境变量
- 各项目私有 `.env` 中重复保存同一主密钥

### 7.2 严格禁止项

以下事项必须视为 defect：

1. 把 `MINIMAX_API_KEY` 或 `QWEN_API_KEY` 明文长期写进 `~/.openclaw/agents/*/agent/models.json`
2. 让多个 agent 各自复制同一个 API key
3. 把生产凭证长期保留在 shell rc 文件里
4. 在文档、日志、状态接口中输出未脱敏密钥
5. 让 secret-bearing 文件权限大于 `600`

### 7.3 分发与同步机制

必须建立标准链：

1. `credentials.env` 作为源头
2. `credctl.py` 生成运行态派生 env
3. systemd / OpenClaw / ChatgptREST 只消费派生结果
4. 状态命令只显示脱敏来源，不显示密钥内容

要求：

1. 生成流程幂等
2. 生成结果可重建
3. 生成结果可审计
4. 生成结果支持差异检查

### 7.4 轮换与吊销

必须补齐以下制度：

1. 每个 provider key 有 owner、用途、轮换频率、上次轮换时间、最近验证时间
2. 轮换必须有 smoke test
3. 吊销必须有 blast radius 说明
4. 轮换失败必须有回滚方案
5. 过期 / 401 / 403 必须能触发可观测告警

### 7.5 文件权限标准

目标标准：

| 类型 | 目标权限 |
|---|---:|
| 源凭证文件 | `600` |
| 派生运行态 env | `600` |
| OpenClaw 顶层配置（含 env ref） | `600` |
| agent auth/profile store | `600` |
| 不含 secret 的普通配置 | `640` 或更严格 |

当前已知不满足：

- `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env` 为 `640`

## 8. 完整整改工作流

### W1. 收敛为单一路由 contract

目标：

- 不再允许 `OpenClaw config`、`RoutingFabric`、`LLMConnector`、`/ask route map` 分别维护各自顺序。

要做的事：

1. 新增 `config/model_routing_contract_v1.json`
2. 由 contract 生成：
   - `scripts/rebuild_openclaw_openmind_stack.py`
   - `config/routing_profile.json`
   - `/v2/advisor/ask` route map
   - `LLMConnector` API chain defaults
3. 增加 drift check，任何生成结果与 contract 不一致即失败

验收标准：

1. repo 内不存在第二份未注释的静态主路由表
2. contract 改一处，所有生成结果同步更新
3. `openclaw models status`、`advisor routing stats`、单元测试结论一致

### W2. 修复 Advisor 语义裂缝

目标：

- `quick_ask`、`deep_research`、`funnel`、`report` 全部纳入统一 contract 语义。

要做的事：

1. `quick_ask` 改为显式 `quick_qa`
2. `deep_research` 改为显式 `deep_research`
3. `funnel` 接入统一 helper，不再直接裸拿 `llm_connector`
4. `report_graph`、`funnel_graph`、`advisor/graph.py` 共享统一 route resolver
5. `/advise` 与 `/ask` 使用同一 contract，只允许执行方式不同，不允许路由语义不同

建议涉及文件：

- `chatgptrest/advisor/graph.py`
- `chatgptrest/advisor/funnel_graph.py`
- `chatgptrest/advisor/report_graph.py`
- `chatgptrest/api/routes_advisor_v3.py`

验收标准：

1. 任何 route 都能打印出 `intent -> task_profile -> candidates -> winner`
2. `deep_research` 不再落到 default profile
3. `funnel` 不再绕过统一路由栈

### W3. 让 RoutingFabric 真正执行“被选中的 provider”

目标：

- 解决“排序是 A，执行其实还是 B”的假路由问题。

要做的事：

1. 给 `LLMConnector` 增加 provider/model-aware invoke 接口
2. `RoutingFabric._invoke_api()` 显式传递 provider identity
3. 区分：
   - API provider
   - Native API provider
   - MCP Web provider
   - CLI provider
4. 对失败分类做统一：
   - auth
   - rate limit
   - infra
   - timeout
   - empty response

建议涉及文件：

- `chatgptrest/kernel/routing/fabric.py`
- `chatgptrest/kernel/llm_connector.py`
- `chatgptrest/kernel/mcp_llm_bridge.py`
- `chatgptrest/kernel/routing/types.py`

验收标准：

1. 当 selector 排第一的是某 provider，执行日志里必须看见同一 provider
2. fallback 事件必须记录 from/to provider
3. 单测与 live smoke 能证明 provider-aware invoke 生效

### W4. 消除 agent 层明文 key 复制

目标：

- `main/agent/models.json`、`finbot/agent/models.json` 不能长期保存共享 API key 的明文实值。

要做的事：

1. 盘点 OpenClaw 是否支持 SecretRef / env-ref 保持不展开写盘
2. 若支持：
   - 改生成与加载链，禁止 materialize 明文
3. 若不支持：
   - 在本地 state 层增加 post-apply scrubber
   - 保证 provider catalog 只保留 env marker，不保留实值
4. 清理历史遗留 provider：
   - `minimax-portal`
   - 已失效或不再参与策略的 provider blocks

建议涉及文件：

- `scripts/rebuild_openclaw_openmind_stack.py`
- OpenClaw provider/materialization 相关本地状态治理脚本
- `/vol1/maint/MAIN/scripts/credctl.py`（外部依赖）

验收标准：

1. `grep` 不应在 `~/.openclaw/agents/*/agent/models.json` 命中真实 API key
2. provider 仍可正常工作
3. 状态命令 provenance 清晰可解释

### W5. 统一 provider status / provenance 语义

目标：

- 运维必须能直接看懂“这个 provider 是从哪里来的、是不是可用、为什么可用”。

要做的事：

1. 区分 OAuth provider 与 API-key provider 的展示语义
2. 区分：
   - source of truth
   - effective runtime source
   - materialized local file
3. 修复 provenance 与真实文件不一致的问题
4. 明确 inherited/default/agent-local 的层级关系

验收标准：

1. `openclaw models status` 不再把 API-key provider 误导成“missing”
2. provenance 能对应到真实文件或 env 来源
3. 不存在“status 说来自 models.json，但本地文件并不含该 provider”的歧义

### W6. 观测与审计

目标：

- 每次路由决策和 fallback 都可回放、可聚合、可审计。

要做的事：

1. telemetry 改为记录 actual selected provider/model
2. 增加 route decision 事件
3. 增加 fallback event
4. 增加 provider health snapshot
5. 增加 auth source classification
6. 增加 live routing audit 文档和接口

建议涉及文件：

- `openclaw_extensions/openmind-telemetry/index.ts`
- `chatgptrest/kernel/routing/*`
- `chatgptrest/advisor/runtime.py`
- `chatgptrest/api/routes_advisor_v3.py`

验收标准：

1. 任何一次回答都能追溯到 winner provider/model
2. fallback 不再是黑箱
3. telemetry 与本地日志互相能对上

### W7. 权限、轮换、告警、扫描

目标：

- 建立真正的生产级凭证治理。

要做的事：

1. 把 secret-bearing env 文件统一收敛到 `600`
2. 建立 secret inventory 结构：
   - provider
   - owner
   - source
   - distribution targets
   - rotation SLA
   - last verified
3. 建立轮换脚本与 smoke test
4. 建立 secret scan：
   - repo 内
   - state 目录
   - shell rc
5. 建立 401/403/429 告警策略

验收标准：

1. 不再依赖人工记忆判断 key 是否该轮换
2. 轮换有记录、有验证、有回滚
3. state 目录 secret scan 可定期跑

### W8. 客户端与文档同步

目标：

- 服务端路由变更必须同步影响到使用方文档。

要做的事：

1. 更新 `docs/model_and_key_inventory.md`
2. 更新 runbook 中与 provider 相关章节
3. 检查 `docs/client_projects_registry.md` 中登记项目是否需要同步
4. 建立“路由变更必带文档变更”的提交流程

验收标准：

1. 任何路由调整都有文档版本记录
2. 客户端项目不会继续按旧语义接入

## 9. Definition of Done

只有满足下面全部条件，才可以声称“模型路由与 key 治理完成”：

1. 单一路由 contract 已建立并成为唯一事实源
2. `advise` 与 `ask` 的路由语义完全对齐
3. `quick_ask`、`deep_research`、`funnel`、`report` 全部走统一 contract
4. `RoutingFabric` 真实执行被选中的 provider
5. OpenClaw agent 层不再复制明文 API key
6. 所有 secret-bearing 文件权限符合标准
7. telemetry 能还原真实 winner 与 fallback chain
8. 有 unit test、integration test、live smoke test
9. 有 rollout、rollback、rotation、incident response 文档
10. 客户端和运维文档已同步

## 10. 立即执行清单

建议按以下顺序推进，不跳步：

1. 新建 `config/model_routing_contract_v1.json`
2. 把 `LLMConnector`、`routing_profile.json`、`/ask route map` 改为 contract 生成
3. 修复 `quick_ask` / `deep_research` / `funnel` 的 route 语义
4. 让 `RoutingFabric._invoke_api()` 支持 provider-aware invoke
5. 解决 OpenClaw agent `models.json` 明文 key materialization
6. 清理遗留 provider 与旧 auth profile 噪音
7. 增强 `openclaw models status` provenance
8. 让 telemetry 记录 actual winner
9. 收紧 `chatgptrest.env` 权限或拆分 secret/non-secret
10. 建立 rotation + smoke + alert 闭环
11. 更新 inventory/runbook/client docs
12. 再出 v2 文档，记录实现结果与残余风险

## 11. 本文档的执行原则

后续所有实现必须遵守：

1. 不做只修一条链、放着其它链继续漂移的最小实现。
2. 不接受“代码逻辑对了，但状态输出和 telemetry 还是错的”。
3. 不接受“顶层配置安全，agent 层 state 继续明文复制 key”。
4. 不接受“路由 contract 没有统一，但先靠文档约定”。
5. 任何例外都必须被显式命名、显式配置、显式观测。

这份 v1 蓝图应作为后续 v2 实施文档、v3 验收文档的父规范。
