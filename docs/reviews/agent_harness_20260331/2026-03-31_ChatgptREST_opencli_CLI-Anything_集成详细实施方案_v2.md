# ChatgptREST 与 opencli、CLI-Anything 集成详细实施方案 v2

更新时间：2026-03-31

## 0. 文档定位

这是本主题当前**唯一建议执行的实施方案**。

本版明确 supersede：

- `/vol1/1000/projects/planning/docs/2026-03-31_ChatgptREST_opencli_CLI-Anything_集成详细实施方案_v1.md`

`v1` 不作废它的方向判断，但不应直接拿来开工。  
`v1` 的两个关键错位是：

1. 把 `skill_suite_review_plane` 误当成 canonical registry intake 主桥
2. 把 `routes_agent_v3` 的 execution seam 低估成了单点插缝

本版在以下前提下重写：

- `opencli` 可以作为执行层候选，但第一阶段必须按**受控外部 substrate**处理
- `CLI-Anything` 可以作为离线能力生产上游，但第一阶段必须按**untrusted artifact source**处理
- `ChatgptREST` 现有 provider web 主链、completion contract、memory/audit 主链都不能被破坏

---

## 1. 本版的独立核验结论

### 1.1 当前 `ChatgptREST` 已经有 capability governance，不是“只有 provider lane”

我独立核验过：

- canonical registry / bundle resolver：
  - `/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/skill_manager.py`
- skill pre-check：
  - `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py`
  - `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/dispatch.py`
- capability gap / quarantine candidate store：
  - `/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/market_gate.py`

因此，正确起点不是“从零做能力平台”，而是：

**在现有 capability governance 之上，补执行层与离线导入层。**

### 1.2 `skill_suite_review_plane` 当前不是 canonical registry intake plane

独立核验结果：

- `skill_suite_review_plane` 当前写入的是 EvoMap review evidence：
  - `Document`
  - `Episode`
  - `Atom`
  - `Evidence`
- 对应入口：
  - `/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/skill_suite_review_plane.py`
- ingest 脚本把 validation bundle 导到：
  - telemetry
  - experiment registry
  - review plane
  - 而不是 canonical registry
  - `/vol1/1000/projects/ChatgptREST/ops/ingest_skill_suite_validation_to_evomap.py`
- canonical registry authority 目前仍是：
  - `/vol1/1000/projects/ChatgptREST/ops/policies/skill_platform_registry_v1.json`

因此：

**`review_plane` 只能作为证据/审查平面，不能在本版中被表述成 canonical registry 的现成 intake 主桥。**

### 1.3 `routes_agent_v3` 当前不是可单点插缝的统一 route mapping

独立核验结果：

- image lane 直提 `gemini_web.generate_image`
- consult / dual_review 走 consultation path
- direct Gemini lane 单独分叉
- 只有剩余 controller path 才真正落到 `route_mapping`

因此：

**Phase 1 不应试图在“provider route mapping 之前”插一个全局 execution seam。**

### 1.4 `opencli` 第一阶段必须被视为高风险外部 substrate

独立核验结果：

- 依赖 Browser Bridge extension + micro-daemon
- 复用浏览器登录态
- 内建 anti-detection / anti-fingerprinting
- 支持 external CLI hub / register / auto-install
- runtime 在 BrowserBridge / CDPBridge 间切换

因此：

**第一阶段不能把 `opencli` 当普通 deterministic executor，也不能把它默认视为“低风险桌面自动化工具”。**

### 1.5 `CLI-Anything` 第一阶段必须视为 untrusted capability producer

独立核验结果：

- 它不是简单吐 bundle 的工具，而是完整的 agent-native CLI/harness 生成系统
- README 的 7-phase pipeline 和 `HARNESS.md` 都表明：
  - 生成 CLI
  - 生成 stateful REPL
  - backend integration
  - 测试与发布

因此：

**`CLI-Anything` 产物在第一阶段一律按 untrusted generated artifacts 处理，不能直接进入 runtime projection，也不能直接写 canonical registry。**

---

## 2. 本版总目标与非目标

### 2.1 总目标

把 `ChatgptREST` 从：

- 有 provider web 执行主链
- 有 capability governance
- 但没有统一外部软件执行接入面

升级到：

- provider web 主链保持稳定
- 新增一条**受控 executor lane**
- 新增一条**离线能力导入线**
- 两条线都进入 audit / review / quarantine / authority 更新闭环

### 2.2 第一阶段最重要的目标

不是“大一统 execution platform”，而是：

1. 证明 `OpenCLIExecutor` 能以受控方式跑起来
2. 证明 `CLI-Anything` 生成物能被当作 candidate artifact 进入 review / quarantine 流程
3. 不破坏当前：
   - provider web
   - completion contract
   - memory / audit / active context
   - canonical registry authority

### 2.3 非目标

本版**明确不做**：

- 不做全局 `CapabilityExecutorRegistry` 大一统重构
- 不重写 `advisor_agent_turn`
- 不重写 `routes_agent_v3`
- 不在第一阶段接入 image / consult / direct Gemini lane
- 不把 `CLI-Anything` 直接写入 canonical registry
- 不把 `opencli` 默认放到已登录 surface 或桌面 AI app 控制上
- 不允许 `opencli` 的 auto-install / 任意 CLI passthrough 进入 Phase 1

---

## 3. 正确的分层模型

### 3.1 三者职责分层

本版冻结的分层如下：

#### `ChatgptREST`

职责：

- northbound task facade
- 上下文
- 审计
- 完成契约
- 记忆
- capability governance
- candidate intake / quarantine / review / authority update

#### `opencli`

职责：

- **受控执行 substrate**
- 在 allowlisted command set 内执行外部命令
- 返回结构化结果与 artifacts

它不是：

- canonical registry
- review plane
- runtime truth source
- 默认安全执行器

#### `CLI-Anything`

职责：

- **离线能力生成上游**
- 生成 package / manifest / harness / tests / validation artifacts

它不是：

- runtime 热路径组件
- canonical registry 自动写入器
- 默认可信 bundle source

### 3.2 四个平面

正确的平面划分应该是：

1. **Execution Plane**
   - provider web
   - controlled `OpenCLIExecutor`

2. **Review Evidence Plane**
   - `skill_suite_review_plane`
   - validation bundles
   - telemetry / experiment registry / EvoMap evidence

3. **Candidate & Quarantine Plane**
   - `market_gate`
   - capability gap
   - market candidate intake
   - quarantine state

4. **Authority Plane**
   - canonical registry JSON
   - owner-controlled promotion/update

这个划分的关键点是：

**review evidence plane 和 authority plane 不能混。**

---

## 4. 目标架构：可落地的 v2 版本

### 4.1 不是“全局 execution seam”，而是“显式 capability execution branch”

Phase 1 正确做法不是全局抽象，而是：

- 在 `routes_agent_v3.py` 中新增一个**显式 capability execution branch**
- 只在一小条 opt-in lane 上触发
- 不碰 image / consult / direct Gemini
- 不改动默认 provider-web path

建议的触发条件：

- `provider_request.capability_id` 明确存在
- `provider_request.executor_kind == "opencli"` 或等价实验标志
- 命中 allowlisted capability family

如果条件不满足：

- 保持现有主链不变

### 4.2 第一版 `OpenCLIExecutor` 的边界

第一版必须是：

**subprocess wrapper**

而不是：

- 嵌入 Node 运行时
- 深耦合 `opencli` 内部 TypeScript 模块
- 依赖 `./registry` export 作为稳定 SDK

建议输入 contract：

- `capability_id`
- `command_id`
- `args`
- `env`
- `timeout_seconds`
- `artifact_rules`
- `trace_id`
- `task_ref`

建议输出 contract：

- `executor_kind`
- `exit_code`
- `stdout`
- `stderr`
- `structured_result`
- `artifacts`
- `execution_status`
- `retryable`
- `audit_envelope`

### 4.3 `opencli` 第一阶段硬安全边界

第一阶段必须写死以下限制：

1. **allowlisted command set only**
2. **禁用 auto-install**
3. **禁用 arbitrary external CLI passthrough**
4. **禁用默认接入已登录 surface**
5. **禁用桌面 AI app 控制**
6. **所有执行必须有 artifact + audit**

如果某条命令不在 allowlist：

- 直接拒绝
- 不允许 silent fallback

### 4.4 第一阶段 capability family 选择

第一阶段不应该做：

- ChatGPT 桌面消息发送
- Codex / Antigravity 控制
- consult-like multi-app choreography

第一阶段应只做下面三类之一：

1. **public/no-auth browser command**
2. **纯 local CLI passthrough（受控、无 auto-install）**
3. **受控 CDP deterministic action**

推荐首批只选 1-2 个 capability：

- 一个 public/no-auth browser capability
- 一个 pure local deterministic capability

不要超过 2 个。

### 4.5 `CLI-Anything` 的正确 intake 路径

第一阶段不应写成：

`CLI-Anything -> review_plane -> canonical registry`

第一阶段应写成：

`CLI-Anything generated package/manifest/validation bundle -> candidate ingest -> review evidence plane + market/quarantine candidate -> owner decision -> canonical registry update`

也就是说：

- review evidence plane 负责提供证据
- market/quarantine plane 负责治理状态
- authority plane 负责最终 canonical 更新

### 4.6 `CLI-Anything` 生成物的默认信任模型

本版明确冻结：

**默认不可信（untrusted）**

允许进入的第一阶段形态只有：

- generated package metadata
- manifest
- validation bundle
- tests / test reports
- review evidence

禁止第一阶段直接进入的形态：

- runtime projection
- canonical registry
- active executor selection

---

## 5. 文件级实施蓝图

## Phase 0：边界冻结

### 目标

冻结现状，明确哪些路径动、哪些不动。

### 涉及文件

- `/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/skill_manager.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/market_gate.py`
- `/vol1/1000/projects/ChatgptREST/ops/policies/skill_platform_registry_v1.json`

### 输出

- route branch map
- capability vs executor vs provider 边界说明
- `opencli` allowlist policy 草案

### 验收

- 文档写清：
  - 哪些任务仍强制走 provider web
  - 哪些任务允许 capability execution opt-in

## Phase 1：`OpenCLIExecutor` POC

### 新增文件

- `/vol1/1000/projects/ChatgptREST/chatgptrest/executors/opencli_executor.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/executors/opencli_policy.py`
- `/vol1/1000/projects/ChatgptREST/config/opencli_executor_policy.yaml`

### 修改文件

- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py`
  - 注入 `opencli_executor`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py`
  - 新增一个 opt-in capability execution branch
  - 不全局改 provider mapping

### 实现要求

- subprocess 调用 `opencli ... --format json`
- 强制 policy allowlist
- 强制 audit envelope
- 失败语义标准化
- 默认禁用 auto-install / 任意 passthrough

### 验收

- 现有 image / consult / direct Gemini 行为零回归
- 新 capability branch 可以跑 1-2 个受控场景
- 北向 `/v3/agent/turn` contract 不破

## Phase 2：artifact 与审计收口

### 新增文件

- `/vol1/1000/projects/ChatgptREST/chatgptrest/executors/executor_artifacts.py`

### 修改文件

- `/vol1/1000/projects/ChatgptREST/chatgptrest/core/completion_contract.py`
  - 只在需要时补 executor provenance 字段
- `/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/artifact_store.py`
  - 复用现有 artifact store 记录外部执行结果

### 实现要求

- 每次 `OpenCLIExecutor` 执行都保留：
  - params
  - stdout/stderr
  - structured result
  - artifacts
  - executor provenance

### 验收

- 外部执行结果可追溯
- replay / retry 语义明确
- 失败能区分：
  - command blocked
  - substrate unavailable
  - runtime execution failed
  - business outcome failed

## Phase 3：`CLI-Anything` candidate ingest

### 新增文件

- `/vol1/1000/projects/ChatgptREST/chatgptrest/ingest/cli_anything_candidate_ingest.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/ingest/cli_anything_validation_models.py`

### 修改文件

- `/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/market_gate.py`
  - 接 candidate intake / quarantine linkage
- `/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/skill_suite_review_plane.py`
  - 只增强 evidence ingest，不改成 registry intake

### 实现要求

- ingest 的输入是：
  - generated package metadata
  - manifest
  - validation bundle
  - test evidence
- ingest 的结果是：
  - review evidence
  - market candidate
  - quarantine state

### 明确禁止

- 不直接写 canonical registry
- 不直接让生成产物进 runtime projection

### 验收

- 至少 1 条 CLI-Anything candidate 线能进 review/quarantine
- 未审产物不能误入 runtime

## Phase 4：owner-controlled registry promotion

### 修改文件

- `/vol1/1000/projects/ChatgptREST/ops/policies/skill_platform_registry_v1.json`
  - 只在 owner 决策后更新

### 实现要求

- owner 审查基于：
  - validation evidence
  - quarantine state
  - real-use trace
- 只有通过 owner 决策，才允许把 candidate 变成 canonical registry entry

### 验收

- canonical registry 的 authority 不被绕过
- review evidence 与 registry entry 有可追溯链接

---

## 6. 测试矩阵

### 6.1 Phase 1 必测

- `routes_agent_v3` opt-in branch test
- `OpenCLIExecutor` policy allow/block test
- subprocess output parsing test
- provider-web regression tests

建议新增测试：

- `tests/test_opencli_executor.py`
- `tests/test_opencli_executor_policy.py`
- `tests/test_routes_agent_v3_capability_branch.py`

### 6.2 Phase 2 必测

- artifact persistence
- audit envelope completeness
- failure classification
- replay/idempotency

建议新增测试：

- `tests/test_opencli_executor_artifacts.py`
- `tests/test_opencli_executor_replay.py`

### 6.3 Phase 3 必测

- CLI-Anything ingest schema validation
- candidate -> quarantine linkage
- review evidence ingestion
- untrusted artifact 不得进入 runtime

建议新增测试：

- `tests/test_cli_anything_candidate_ingest.py`
- `tests/test_market_gate_candidate_ingest.py`
- `tests/test_skill_suite_review_plane_candidate_evidence.py`

### 6.4 端到端验收

必须至少覆盖：

1. provider-web 典型任务无回归
2. `opencli` 受控 capability 成功
3. `opencli` 非 allowlisted capability 被拦截
4. `CLI-Anything` candidate 能进入 review/quarantine
5. 未审 candidate 不进入 runtime
6. owner 决策后 registry 才变化

---

## 7. 验收标准

只有同时满足以下条件，才允许说“v2 第一阶段落地完成”：

1. 现有 provider-web 主链无回归
2. 至少 1 个 public/no-auth capability 稳定跑通
3. 至少 1 个 CLI-Anything candidate ingest 跑通
4. review evidence 与 quarantine 链成立
5. canonical registry authority 未被绕过
6. `opencli` auto-install / 任意 passthrough 没有进入 Phase 1
7. 所有外部执行都有 audit envelope

---

## 8. 主要风险与对策

### 风险 1：`opencli` 被误当成普通 deterministic executor

对策：

- 只允许 allowlist
- 禁用 auto-install
- 禁止任意 passthrough
- 默认不接已登录 surface

### 风险 2：`CLI-Anything` 生成物过早进入 runtime

对策：

- 默认 untrusted
- 只先进 review evidence + quarantine
- canonical registry 仍 owner-controlled

### 风险 3：为接 executor 破坏 `routes_agent_v3`

对策：

- 只加 opt-in branch
- 不做全局 route_mapping 重构
- 不碰 image / consult / direct Gemini

### 风险 4：术语混乱导致实现错位

对策：

- 统一术语：
  - `execution seam`
  - `executor layer`
  - `review evidence plane`
  - `candidate/quarantine plane`
  - `authority plane`

---

## 9. 最终结论

本版最终判断如下：

1. **方向保留：**
   - `opencli = 执行层候选`
   - `CLI-Anything = 离线生成层候选`

2. **`v1` 不可直接执行：**
   - 因为它低估了 `routes_agent_v3` 的真实分叉
   - 也把 `skill_suite_review_plane` 写成了错误的 intake 主桥

3. **第一阶段正确目标不是全局 executor registry，而是受控 POC：**
   - subprocess 版 `OpenCLIExecutor`
   - 一条 opt-in capability branch
   - 一条 `CLI-Anything` candidate ingest 线

4. **第一阶段最重要的高标准要求是治理，不是功能数量：**
   - allowlist
   - audit
   - quarantine
   - owner-controlled promotion

5. **一句话冻结：**

**这条集成线值得做，但第一阶段必须按“受控执行 substrate + 不可信生成产物 + owner 审批 authority”来落，不允许再按 v1 那种过于顺滑的大一统叙事开工。**
