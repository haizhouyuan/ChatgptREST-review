# OpenClaw Project Context Injection — Antigravity Deep Review v1

Date: 2026-04-07
Reviewer: Antigravity (Claude Opus 4.6 Thinking)
Scope: Codex 实施的三仓库改动 + Feishu 端到端验证失败的根因分析
Status: 代码层 LGTM with observations; 端到端验收未通过，根因不在代码质量

---

## 总体评价

**代码改动本身是干净的、收敛的、方向正确的。** Codex 把"项目上下文注入 planning 主链"这个目标分解成三个孤立变更，范围恰当没有扩散，白名单 registry 是对的防线，fail-open 策略是对的取向。

**但这次暴露了一个系统级盲区：实施者对"代码改好 ≠ 运行态生效"的验证缺失。** 这不是 Codex 的代码写坏了，是验收流程设计不完整。

---

## 第一层：代码质量审计

### ✅ 正面判断

| 审查点 | 判断 |
|--------|------|
| `PROJECT_REGISTRY` 白名单设计 | 正确。硬编码 registry 拦截了任意路径注入，`projectRef` 不经 registry 不能转化为文件路径。这是安全的选择 |
| `loadProjectContext` fail-open | 正确。读取失败打 `console.warn` 然后 return null，不阻断 ask 请求 |
| `parseSimpleFrontmatter` 自写解析器 | 可接受。避免引入 `js-yaml` 依赖，正则覆盖了标准 YAML list/scalar 格式。对当前有限复杂度的 frontmatter 够用 |
| `filterExistingPaths` 异步校验权威文档存在性 | 正确。不存在的文件会被过滤掉并打 warn，不会给 backend 传不存在的路径 |
| `enrichProjectContext` 只在字段 undefined 时注入 | 正确。不会覆盖调用方显式传入的值 |
| `mergeUniqueStrings` 去重 | 正确。attachments 不会重复注入同一个权威文档 |
| `buildTaskIntakePayload` 改动范围 | 收敛。只加了 `attachments` 和 `projectContext` 两个可选参数，原有逻辑不变 |
| 不引入新 npm 依赖 | 正确，只用 `node:fs/promises` 和 `node:path` |

### ⚠️ 观察与隐患

#### 1. `_stringify_contract_field` 丢失 project_context 数据

> [!WARNING]
> 这是最重要的一个发现，前置设计 review 没有覆盖到。

`available_inputs` 作为 dict 传到 backend `TaskIntakeSpec` 后，在 `task_intake_to_contract_seed` 里被 `_stringify_contract_field` 序列化为 prompt 模板变量。

看 `_stringify_contract_field` (task_intake.py L855-879)：
- 它只识别 `files`、`notes`、`kb_refs`、`artifacts` 这四个 key
- **不识别 `project_context`、`frozen_facts`、`style_rules`、`current_focus`、`authority_docs`、`project_ref`、`planning_base`**
- 如果这四个 key 全不命中，最终走 `json.dumps(dict(value), ...)` 兜底

这意味着：当 `available_inputs` 是 `{files: [...], project_context: "...", frozen_facts: [...], ...}` 时：
- prompt 里看到的 `{available_inputs}` 会是 `Files: doc1, doc2, doc3 | {"authority_docs": [...], "frozen_facts": [...], ...}` 这种**混合格式**
- `frozen_facts`、`style_rules` 会被压成 JSON 字符串粘在 `{available_inputs}` 模板变量尾部
- **不是完全丢失，但格式很难看，LLM 能否稳定消化取决于 prompt 长度和模型注意力**

**影响等级**：中。数据不丢，但以半结构化 JSON dump 的形式出现在 prompt 里，可能降低 LLM 对 frozen_facts / style_rules 的遵循程度。

**建议**：这不阻断当前版本上线，但后续如果端到端验证发现"模型没遵守写作规则"，第一个应查的就是这个序列化路径。正式修法是让 `_stringify_contract_field` 识别 `project_context`、`frozen_facts`、`style_rules`、`current_focus` 这些新字段，给它们人类可读的格式化输出。

#### 2. 实际实现与 design review 规格的差异

设计 review (claudegac_v1) 建议的注入方式是：
```typescript
// 在 buildTaskIntakePayload 返回后、发送请求前修改 taskIntake
taskIntake.available_inputs = { ..., project_context: raw_file_content };
taskIntake.context = { ..., project_ref: projectRef, project_authority_docs: [...] };
```

实际实现选择了更好的方式：
- `projectContext` 作为参数传入 `buildTaskIntakePayload`，在构建过程中一次性组装
- 注入的不是 raw file content，而是结构化的 frontmatter 字段
- `enrichProjectContext` 在 `mergedContext` 上做 merge，而不是事后修改 payload

**实际实现比设计 review 建议的更好。** Codex 没有机械照抄 review 的伪代码，而是找到了更干净的注入点。这是正面的。

#### 3. context dict 被注入了大量字段

`enrichProjectContext` 会把 `project_ref`、`project_alias`、`planning_base`、`project_context_path`、`authority_docs`、`frozen_facts`、`current_focus`、`style_rules` 共 8 个字段注入到 `mergedContext`。

这些字段会通过 `context: requestContext` 透传到 `/v3/agent/turn` 的 HTTP body。后端 `build_task_intake_spec` 里，`context_dict` 会被存储在 `TaskIntakeSpec.context` 里。

这不是错误操作 — 后端对 `context` 是开放 schema 的。但有两个需要注意的：
- `context` 里的 `authority_docs` 和 `available_inputs` 里的 `authority_docs` 会冗余（两个地方各一份）
- `frozen_facts` / `style_rules` 同样冗余

冗余本身不是 bug，但要意识到后续如果在 prompt_builder 或 scenario_pack 里决定消费这些字段，需要明确**从哪个位置读**。当前 backend 的 `_scenario_haystack` 只从 `available_inputs.notes` 读，不看 `available_inputs.frozen_facts` 等新字段。

#### 4. `parseSimpleFrontmatter` 的边界行为

手写的 frontmatter parser 有一个小瑕疵：`keyMatch` 正则是 `^([A-Za-z0-9_]+):\s*(.*)$`，这意味着带中文字符的 key 名不会匹配。但当前 `_project_context.md` 的 frontmatter 里所有 key 都是英文的（`project`、`alias`、`planning_base` 等），所以不影响。

但如果将来有人写 `项目名: xxx` 这种 key，会被静默跳过。建议在 `_project_context.md` 的格式规范里明确：frontmatter key 必须是 ASCII。

#### 5. 测试覆盖的局限

新增的测试（`test_openclaw_cognitive_plugins.py`）是**源码子串断言**，不是功能测试。它验证的是：
- `projectRef: Type.Optional(Type.String` 出现在源码里
- `PROJECT_REGISTRY` 的 key-value 存在
- `loadProjectContext`、`enrichProjectContext` 这些函数名存在

这证明了代码存在，但不证明代码正确运行。不过考虑到这是 OpenClaw plugin（TypeScript），在 Python test 里只能做源码断言，这个限制是合理的。

---

## 第二层：架构决策审计

### ✅ 决策正确的部分

| 决策 | 为什么正确 |
|------|-----------|
| 不建新 agent/workspace | 历史教训明确（`pm/` 100+ 残骸），符合"keep the shell lean" |
| 白名单而非路径拼接 | 安全第一，不给调用方暴露文件系统路径构造能力 |
| 在 plugin 层注入而非 backend 层 | plugin 是入口收敛点，改 backend 影响面大得多 |
| fail-open 而非 fail-closed | 项目上下文是增强不是必要条件，读不到该走就走 |
| 结构化 frontmatter 而非自由格式 markdown | 机器解析确定性高，不依赖 LLM 自己从自由文本里提取字段 |

### ⚠️ 架构级风险

#### 1. 依赖 LLM 的 tool-calling 决策做路由 — 这是系统性脆弱点

AGENTS.md 的路由规则：
```
当用户消息涉及以下高信号项目词时，调用 openmind_advisor_ask 时带上 projectRef
```

这不是代码逻辑，这是给 LLM 看的自然语言指令。它的可靠性取决于：
1. 当前 session 是否加载了最新的 AGENTS.md
2. LLM（MiniMax M2.5）是否在 tool-calling 决策时真的遵循了这条规则
3. 上下文窗口的压力 — 如果 session 已经很长，这条规则可能被注意力稀释

**这不是 Codex 的代码问题，这是整个 OpenClawBot 架构的系统性弱点。** 项目路由依赖 LLM 的"理解力"，而不是确定性的代码匹配。

**建议**：在当前架构约束下，AGENTS.md 路由是唯一可行的方案，不需要改。但要认清：这一层的可靠性上限就是 ~80%（乐观估计）。长期方向应该是在 OpenClaw 的 plugin 调用层（或 message preprocessing 层）加一个确定性的关键词匹配，在 LLM 决策之前就把 projectRef 注入到 tool_call 参数里。

#### 2. 权威文档作为 attachments 传入 — 但 backend 目前不读文件内容

权威文档路径被注入到 `attachments` 里，backend 的 `_derive_attachment_inventory` 会处理它们。但实际上，**ChatgptREST 的 planning 主链目前不会读取这些权威文档的内容**。它只是把路径作为元数据传入 prompt。

真正"读文件内容并注入到 prompt"的行为发生在 ChatGPT/Gemini Web driver 侧：如果文件通过 rclone 上传到 Drive 再在 Gemini UI 里作为附件添加。

也就是说：当前这些 `authority_docs` 路径可能只起到了"告诉 LLM 有这些文档存在"的效果，但 LLM 不能实际阅读它们的内容。**除非后端 scenario_pack 或 knowledge_ingress 在编译 prompt 时主动打开并注入文件内容。**

这是一个重要的"看似注入了实则可能没消化"的盲区。

#### 3. `_project_context.md` 的维护是人工的

当业务推进、新文档产出时（比如 v4 稿、新的简报），`_project_context.md` 的 `authority_docs` 列表需要手动更新。这不是自动化的。

这本身不是 bug，但在日常使用中，最容易出现的问题是：用户已经产出了 v4 稿，但 `_project_context.md` 还指向 v3，导致 planning 主链用的是过时文档。

---

## 第三层：端到端验证失败的根因分析

### Codex 的诊断

Codex 诊断为：
1. 旧 session 没有重新读入 AGENTS.md
2. 运行态没刷新到新版本的 plugin schema

### 我的独立判断

**Codex 的诊断方向正确，但不够深入。** 根因不是单纯的"旧 session"，而是更本质的问题：

#### 根因 1：OpenClawBot 的 session 不是热加载的

OpenClawBot main agent 的 session 一旦启动，它读取的 AGENTS.md / SOUL.md / ROLE_PACKS.md 就冻结在 session 启动时的版本。session 运行期间修改这些文件，对当前 session 没有任何效果。

这意味着：**任何对 AGENTS.md 的改动，都需要"重启 session"才能生效。** 这不是 bug，是 OpenClaw 的架构特征。但 Codex 的验收流程没有把"重启 session"作为必要步骤。

#### 根因 2：plugin schema 热更新未验证

`openmind_advisor_ask` 新增了 `projectRef` 参数，但 OpenClaw 的 plugin 系统是否支持运行时 schema 热更新？如果 plugin 注册是在 session 启动时一次性完成的，那新参数 `projectRef` 即使代码已经部署，旧 session 里的 tool definition 也不会包含 `projectRef`。

#### 根因 3：验收流程缺少"部署 → 重启 → 验证"环节

Codex 的验收做了：
- ✅ blast radius check
- ✅ pytest 回归
- ✅ gitnexus detect_changes
- ✅ check_doc_obligations

但缺少了最关键的一步：
- ❌ 重启 OpenClawBot main session
- ❌ 通过真实 Feishu 消息触发 end-to-end flow
- ❌ 在 ChatgptREST 侧确认新的 advisor_run 出现

walkthrough L103-109 写了"后续用真实项目句子验证三件事"，说明 Codex 自己也知道端到端还没做。但问题是：它把端到端验收定义为"后续"，而不是"交付前必须完成"。

---

## 第四层：Codex 诊断+建议的评判

Codex 提出的修复方案（按顺序）：
1. 重启 main agent session
2. 确认 plugin 运行态刷新
3. 用短话术做最小验收
4. 再测完整复杂话术

**这个方案是正确的。** 顺序对，逻辑清楚，先验证管道通不通，再验证内容对不对。

但我补充一点：**第 2 步"确认 plugin 运行态刷新"不是一句话能完成的。** 需要确认 OpenClaw 的 plugin 加载机制 — 是 session 级别加载还是进程级别加载。如果是进程级别，可能需要重启 OpenClaw 进程本身。

---

## 总结

| 维度 | 评分 | 说明 |
|------|------|------|
| 代码质量 | ✅ 合格 | 改动干净、范围收敛、安全意识到位 |
| 架构方向 | ✅ 正确 | 不扩拓扑、白名单 registry、fail-open |
| 设计 review 执行 | ✅ 超出预期 | 实际实现比 review 伪代码更优 |
| 验收完整度 | ❌ 不足 | 缺端到端验收，缺"部署→重启→验证"环节 |
| 后端消化路径认知 | ⚠️ 有盲区 | `_stringify_contract_field` 不识别新字段 |
| 系统性思考 | ⚠️ 有缺口 | 没有识别到"AGENTS.md LLM 路由"的不可靠性 |

### 当前应做的三件事

1. **重启 OpenClawBot main session + 确认 plugin schema 刷新** — 这是最紧急的
2. **发一条最小话术做端到端验证** — "继续处理 0497 和金彭这条线"
3. **在 ChatgptREST 侧 advisor_runs 表确认新 run 出现，并检查 task_intake payload 里有没有 project_context**

### 中期应做的一件事

4. **在 `_stringify_contract_field` 里加对 `project_context`、`frozen_facts`、`style_rules`、`current_focus` 的人类可读格式化** — 否则 LLM 看到的是 JSON dump，遵循度会打折

### 长期该想的一件事

5. **项目路由不应完全依赖 LLM 的理解力** — 在 plugin 调用前加确定性的关键词匹配，把 projectRef 注入到 tool_call 参数发起之前
