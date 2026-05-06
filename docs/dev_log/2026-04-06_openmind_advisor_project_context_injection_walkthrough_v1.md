---
title: OpenMind Advisor projectRef 项目上下文注入 walkthrough v1
status: completed
updated: 2026-04-06
owner: Codex
---

# OpenMind Advisor projectRef 项目上下文注入 walkthrough v1

## 本次目标

让 `Feishu -> OpenClawBot -> openmind_advisor_ask -> /v3/agent/turn` 这条链路在不新增 agent/workspace、不改后端的前提下，能够把复杂业务项目的权威上下文稳定带入 planning 主链。

## 为什么这样做

这次要解决的问题不是 planning backend 不会做复杂任务，而是入口层把任务送进来时只有裸问题，没有项目边界、权威文档、冻结事实和表达规则。

当前系统已经确认：

- `main` 是唯一正式入口 agent
- `memorySearch` 没有为该项目提供稳定 recall
- 为单个业务项目重建专属 agent/workspace 会违背 `keep the shell lean` 的原则

所以本次方案收敛为：

1. 在项目目录维护一个机器优先的 `_project_context.md`
2. 在 `openmind_advisor_ask` 增加 `projectRef`
3. 用白名单 registry 把 `projectRef` 映射到 `_project_context.md`
4. 把项目上下文注入 `task_intake.available_inputs.project_context`
5. 把权威文档路径追加进 `attachments`
6. 在 `main` agent 只加轻量关键词路由，不重长 agent 拓扑

## 本次改动

### 1. 项目上下文文件

新增：

- `/vol1/1000/projects/planning/两轮车车身业务/_project_context.md`

设计原则：

- frontmatter 机器优先
- 正文人类可读
- authority docs 使用绝对路径
- 风格规则、冻结事实、当前焦点显式结构化

### 2. openmind-advisor plugin

改动文件：

- `openclaw_extensions/openmind-advisor/index.ts`

核心变化：

- `openmind_advisor_ask` 新增可选参数 `projectRef`
- 新增 `PROJECT_REGISTRY`
- 插件侧异步读取 `_project_context.md`
- 解析 frontmatter，不新增依赖
- fail-open：上下文读取失败只打 warning，不阻断 ask
- 将以下内容注入到 `task_intake.available_inputs`
  - `project_context`
  - `project_ref`
  - `planning_base`
  - `authority_docs`
  - `frozen_facts`
  - `current_focus`
  - `style_rules`
- 将 authority docs 去重后并入 `attachments`
- 将 `project_ref / planning_base / authority_docs / frozen_facts / current_focus / style_rules` 投影到 request context

### 3. main agent 轻路由

改动文件：

- `/vol1/1000/openclaw-workspaces/main/AGENTS.md`

只新增一条项目上下文路由规则：

- 高信号命中 `两轮车车身业务 / shortmobility / 0497 / 金彭 / 绿源 / 袁海州 / 孙群慧`
  时，调用 `openmind_advisor_ask` 自动带 `projectRef="shortmobility"`
- 高信号命中 `行星滚柱丝杠 / prs / 蔡总` 时，自动带 `projectRef="prs"`

## 为什么不做

这次明确没有做：

- 不改 `openclaw.json`
- 不新增 project agent/workspace
- 不改 memory 配置
- 不改 ChatgptREST backend
- 不在 plugin 内做复杂 markdown section 解析

## 验收口径

### plugin 层

至少确认两件事：

1. `task_intake.available_inputs.project_context` 有值
2. `attachments` 包含 authority docs

### Feishu 端到端层

后续用真实项目句子验证三件事：

1. `main` 能否自动带上 `projectRef`
2. 输出是否真正体现 authority docs 与冻结事实
3. 输出是否遵循项目写作规则

## 当前边界

这次改动只是把项目上下文稳定送入 planning 主链。

如果后续端到端输出没有真正使用这些上下文，问题应优先排查：

1. `main` 的 tool-calling 是否正确带了 `projectRef`
2. executor prompt 是否正确消费了 `available_inputs.project_context`
3. 当前所选 executor 的内容消化能力是否足够
