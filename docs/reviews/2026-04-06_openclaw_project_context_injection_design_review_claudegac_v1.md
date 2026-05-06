# OpenClaw Project Context Injection — Design Review v1

Date: 2026-04-06
Reviewer: Claude Opus 4.6 (Claude Code)
Status: approved for implementation

## Problem

OpenClawBot 通过 Feishu 收到业务请求时，`task_intake` 只携带裸句子（如"帮我改一下激励方案"），不携带任何项目上下文。这导致 planning backend 无法区分这是哪个项目、哪些文档是权威输入、哪些事实已冻结、输出应遵循什么风格。

对比：codex2 session `019d37b6-aca1-7640-9da7-a66c9169474b` 能产出高质量输出，是因为用户手动喂了全部文档。OpenClawBot 缺的不是模型能力，是入口层的上下文注入。

## 被否决的方案

为每个业务项目创建专属 agent + workspace。否决原因：
- 违反 USER.md "keep the shell lean; do not re-grow the old half-finished role-agent topology"
- `/vol1/1000/openclaw-workspaces/pm/` 的 100+ 残留文件是前车之鉴
- 每个新项目都要重复全套配置，维护成本线性增长

## 采纳方案

在 task_intake 入口层注入项目上下文，不改 agent 拓扑。

### 变更 1: `_project_context.md`

路径: `/vol1/1000/projects/planning/两轮车车身业务/_project_context.md`

设计要求：
- frontmatter 必须机器优先，`authority_docs`、`style_rules`、`current_focus` 作为结构化字段
- 正文给人看，但 plugin 只解析 frontmatter
- `planning_base` 字段标明项目文档根目录

frontmatter 规范：

```yaml
---
project: 两轮车车身业务
alias: shortmobility
planning_base: /vol1/1000/projects/planning/两轮车车身业务
updated: 2026-04-06
authority_docs:
  - /vol1/1000/projects/planning/两轮车车身业务/2026-04-04_袁海州下一步工作初版_0497项目与董事长汇报及产品规划_v3.md
  - /vol1/1000/projects/planning/两轮车车身业务/2026-04-05_事实补洞校准稿_金彭与0497_v1.md
  - /vol1/1000/projects/planning/两轮车车身业务/2026-04-05_智能短交通业务激励方案_v1.md
  - /vol1/1000/projects/planning/docs/2026-04-03_蔡总三次沟通与最新进展简报_v1.md
style_rules:
  - 去掉"不是而是"结构
  - 直接表达判断，不做绕行定义
  - 军令状相关表述统一为"重新设计"，不叫"改进"
  - 过程奖励与结果奖励并行表述，不写成二选一或加权
  - 少解释定义，直接说判断
current_focus:
  - 按4月3日SRT复核孙群慧交办事项是否遗漏
  - 重构0497激励为两套方案（里程碑兑现版 + 量产后按件提成版）
  - 给领导层保留对比选择
  - 重做激励总包与优先级测算视角
---
```

正文区域写冻结事实和当前阶段的人类可读说明。

### 变更 2: `openmind-advisor/index.ts` — 加 `projectRef` 参数

文件: `/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts`

#### 2a. 项目白名单 registry

在文件顶部（`readConfig` 之后）加硬编码 registry：

```typescript
const PROJECT_REGISTRY: Record<string, string> = {
  "两轮车车身业务": "/vol1/1000/projects/planning/两轮车车身业务/_project_context.md",
  "shortmobility": "/vol1/1000/projects/planning/两轮车车身业务/_project_context.md",
  "行星滚柱丝杠": "/vol1/1000/projects/planning/行星滚柱丝杠/_project_context.md",
  "prs": "/vol1/1000/projects/planning/行星滚柱丝杠/_project_context.md",
};
```

projectRef 必须经过此 registry 解析，不允许直接拼路径。未命中 registry 的 projectRef 静默忽略（warn log），不阻断请求。

#### 2b. 参数注册

在 `openmind_advisor_ask` 的 `Type.Object({...})` 里加：

```typescript
projectRef: Type.Optional(Type.String({
  description: "Project key (e.g. '两轮车车身业务' or 'shortmobility'). Resolves to a _project_context.md file via allowlist."
})),
```

位置：与 `goalHint`、`roleId` 同级。

#### 2c. 文件读取与注入逻辑

在 `buildTaskIntakePayload` 调用之前，加 projectRef 解析：

```typescript
// resolve projectRef
const projectRef = String((params as Record<string, unknown>).projectRef ?? "").trim();
let projectContext: string | undefined;
let projectAuthorityDocs: string[] = [];

if (projectRef) {
  const contextPath = PROJECT_REGISTRY[projectRef];
  if (contextPath) {
    try {
      const raw = await readFile(contextPath, "utf8");
      const fmMatch = raw.match(/^---\n([\s\S]*?)\n---/);
      if (fmMatch) {
        // parse YAML frontmatter minimally
        const fmText = fmMatch[1];
        // extract authority_docs as array
        const docsMatch = fmText.match(/authority_docs:\n((?:\s+-\s+.+\n?)+)/);
        if (docsMatch) {
          projectAuthorityDocs = docsMatch[1]
            .split("\n")
            .map(line => line.replace(/^\s+-\s+/, "").trim())
            .filter(Boolean);
        }
      }
      projectContext = raw;
    } catch (err) {
      // fail-open: log warning, continue without project context
      console.warn(`[openmind-advisor] projectRef "${projectRef}" resolved to ${contextPath} but read failed:`, err);
    }
  } else {
    console.warn(`[openmind-advisor] projectRef "${projectRef}" not found in PROJECT_REGISTRY`);
  }
}
```

注入点（在 `buildTaskIntakePayload` 返回后、发送请求前）：

```typescript
if (projectContext) {
  const existingInputs = (taskIntake.available_inputs ?? {}) as Record<string, unknown>;
  taskIntake.available_inputs = {
    ...(typeof existingInputs === "object" ? existingInputs : {}),
    project_context: projectContext,
  };
}
if (projectAuthorityDocs.length > 0) {
  const existingAttachments = Array.isArray(taskIntake.attachments) ? taskIntake.attachments : [];
  taskIntake.attachments = [...new Set([...existingAttachments, ...projectAuthorityDocs])];
}
if (projectRef) {
  taskIntake.context = {
    ...(taskIntake.context ?? {}),
    project_ref: projectRef,
    project_authority_docs: projectAuthorityDocs,
  };
}
```

#### 2d. 关键约束

- 必须用 `node:fs/promises` 的 `readFile`，不能用同步 IO
- 读取失败必须 fail-open：warn log + 继续执行
- 不引入新 npm 依赖（YAML 解析用正则，不用 `js-yaml`）
- `available_inputs` 可能已有值（从 context files 派生），必须 merge 不能覆盖
- `attachments` 去重（`new Set`）

### 变更 3: main agent AGENTS.md 路由规则

文件: `/vol1/1000/openclaw-workspaces/main/AGENTS.md`

在 `## Operating rules` 之后加：

```markdown
## 项目上下文路由
当用户消息包含以下高信号词时，调用 openmind_advisor_ask 时带上对应的 projectRef：
- 两轮车车身业务 / shortmobility / 0497 / 金彭 / 绿源 / 袁海州 / 孙群慧 → projectRef="两轮车车身业务"
- 行星滚柱丝杠 / prs / 蔡总 → projectRef="行星滚柱丝杠"

不确定时不带 projectRef，让用户自己指定。
```

关键词选择原则：宁可少触发不要误触发。"车身"、"两轮车"、"丝杠"等泛词不列入。

### 不改的东西

- `openclaw.json` — 不动
- 不新建 workspace
- 不改 memory 配置（`openmind-memory` 保持现状）
- 不改 backend（`routes_agent_v3.py`、`task_intake.py`、`prompt_builder.py`）— `available_inputs` 和 `attachments` 的处理链路已存在
- 不改 Feishu channel bindings

## 验收标准

### 第一层：plugin 层（Codex 必须验证）

1. 发送带 `projectRef="两轮车车身业务"` 的 `openmind_advisor_ask` 调用
2. 检查 backend 日志确认：
   - `task_intake.available_inputs.project_context` 有值且包含 frontmatter 内容
   - `task_intake.attachments` 包含 4 个权威文档路径
   - `task_intake.context.project_ref` = "两轮车车身业务"
3. 发送不存在的 `projectRef="不存在的项目"` 确认 fail-open：请求正常完成，无报错

### 第二层：Feishu 路由层（Codex 验证）

1. 通过 Feishu 发送"0497激励方案需要调整"
2. 确认 main agent 自动识别并带上 `projectRef="两轮车车身业务"`
3. 确认 backend 收到的 task_intake 包含项目上下文

### 第三层：输出质量层（用户验证）

1. 输出是否体现了 4 月 3 日简报里的要点
2. 是否产出了两套激励方案（里程碑版 + 量产提成版）
3. 是否遵循了 style_rules（无"不是而是"、军令状用"重新设计"）
4. 是否体现了冻结事实（金彭量级不作为已确认事实）

第三层失败不阻断 plugin 上线，但标记为后续 executor prompt 优化方向。

## 实施顺序

1. 建 `_project_context.md`（零风险，纯文件）
2. 改 `openmind-advisor/index.ts`（加 registry + projectRef 参数 + 读取注入逻辑）
3. 改 `main/AGENTS.md`（加路由规则）
4. 重新安装 plugin
5. 执行第一层 + 第二层验收
6. 用户执行第三层验收

## 风险

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| `_project_context.md` frontmatter 解析正则不够健壮 | 低 | authority_docs 丢失 | 用 `authority_docs:\n((?:\s+-\s+.+\n?)+)` 匹配，覆盖标准 YAML list 格式 |
| MiniMax M2.5 关键词识别不准 | 中 | 该带 projectRef 时没带 | 用户可手动在消息里说"projectRef=两轮车车身业务" |
| 权威文档路径变更后 frontmatter 未同步 | 中 | attachments 指向不存在的文件 | backend `_derive_attachment_inventory` 会静默跳过不存在的文件，不会报错 |
| 项目上下文文件过大导致 token 超限 | 低 | prompt 被截断 | `_project_context.md` 控制在 2000 字以内 |

