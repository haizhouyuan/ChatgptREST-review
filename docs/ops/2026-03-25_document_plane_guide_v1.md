# ChatgptREST Document Plane Guide v1

> 日期: 2026-03-25
> 状态: current maintainer guidance
> 目的: 明确当前 canonical guidance 与 `docs/dev_log/` 混合档案的读取口径

## 1. 先说结论

这几个位置才应该被新维护 agent 当成当前 guidance 的默认入口：

- `AGENTS.md`
- `docs/README.md`
- `docs/ops/*`
- `docs/runbook.md`
- `docs/contract_v1.md`
- `docs/repair_agent_playbook.md`

`docs/dev_log/` 不是一个单一语义平面。

它同时混有：

- 历史实现记录
- 提案 / blueprint / 计划
- review / validation / issue pack
- walkthrough / completion

所以：

- 不要把 `docs/dev_log/*` 统一当成 current canonical guidance
- 也不要因为某个 dev log 写过某个方案，就默认它已经 live

## 2. 当前文档平面怎么分

### 2.1 Current canonical guidance

这些文档回答“现在应该怎么进、怎么跑、怎么排障、当前口径是什么”：

- `AGENTS.md`
- `docs/README.md`
- `docs/ops/2026-03-25_agent_maintainer_entry_v1.md`
- `docs/ops/2026-03-25_worktree_policy_v1.md`
- `docs/ops/2026-03-25_artifact_retention_policy_v1.md`
- `docs/ops/2026-03-25_entrypoint_matrix_v1.md`
- `docs/runbook.md`
- `docs/contract_v1.md`
- `docs/repair_agent_playbook.md`

如果这些文档与旧的 dev log 文档冲突，默认以这里为准。

### 2.2 Historical curated history

这些文档回答“以前发生过什么、为什么会这样、当时修了哪里”：

- `docs/handoff_chatgptrest_history.md`
- `docs/client_projects_registry.md` 中的历史接入/迁移上下文
- `docs/dev_log/*walkthrough*`
- `docs/dev_log/*completion*`
- 已经完成并有对应提交/测试痕迹的 fix/containment/followthrough 记录

这类材料适合用来：

- 追溯根因
- 找代码路径
- 找历史提交和测试

但它们不是 live runbook。

### 2.3 Proposal / planning plane

这些文档回答“有人提过什么方案、打算怎么做、边界怎么拆”：

- `docs/dev_log/*plan*`
- `docs/dev_log/*proposal*`
- `docs/dev_log/*blueprint*`
- `docs/dev_log/*task_spec*`
- `docs/dev_log/*todolist*`

读取规则：

- 它们说明的是某一轮设计意图
- 除非内容已被投影进 `docs/ops/*`、`runbook`、`contract_v1` 或实际代码/测试
- 否则不要把它们当成已落地事实

### 2.4 Reference / evidence plane

这些文档回答“当时看到了什么证据、评审怎么说、验证结果是什么”：

- `docs/reviews/*`
- `docs/dev_log/*review*`
- `docs/dev_log/*issue_pack*`
- `docs/dev_log/*validation*`
- `docs/dev_log/*retest*`
- `docs/dev_log/artifacts/*`

这类材料适合用来：

- 支撑判断
- 找验证包
- 理解为什么某个 guard/policy 被加上

但它们不是运行时 source of truth。

## 3. `docs/dev_log/` 的实用读取规则

当你打开一个 `docs/dev_log/*.md`，先问 3 个问题：

1. 这是在描述“现在应该怎么做”，还是“当时做了什么”？
2. 它有没有被投影到 `docs/ops/*`、`runbook`、`contract_v1` 或代码里？
3. 它是 proposal，还是 evidence，还是 historical record？

可以用文件名先做粗分类：

- `*_walkthrough_vN.md`
  - 历史执行记录
- `*_completion_vN.md`
  - 历史收口记录
- `*_plan_vN.md` / `*_proposal_vN.md` / `*_blueprint_vN.md`
  - 设计/计划，不默认代表 live
- `*_review_*` / `*_validation_*` / `*_issue_pack_*` / `*_retest_*`
  - 证据/评审/验证包
- `*_fix_vN.md` / `*_containment_vN.md` / `*_followthrough_vN.md`
  - 历史修复记录，需要再对照代码和 runbook 判断当前是否仍成立

## 4. 发生冲突时怎么判

优先级默认按这个顺序：

1. 代码、测试、当前配置
2. `docs/runbook.md` / `docs/contract_v1.md` / `docs/ops/*`
3. `AGENTS.md` / `docs/README.md`
4. `docs/handoff_chatgptrest_history.md`
5. `docs/dev_log/*`
6. `docs/reviews/*` 与 `docs/dev_log/artifacts/*`

例外：

- 如果问题是“某次历史变更为什么这么做”，`docs/dev_log/*` 和 `reviews/*` 价值会高于当前 runbook
- 如果问题是“现在服务该怎么启动/恢复”，仍然以 runbook 和当前脚本/代码为准

## 5. Promotion 规则

一个 dev log 里的结论，只有在被提升到下面这些位置后，才应被视为 current guidance：

- `docs/ops/*`
- `docs/runbook.md`
- `docs/contract_v1.md`
- `AGENTS.md`
- `docs/README.md`
- 相关代码、测试、脚本注释

换句话说：

> dev log 可以提出、记录、证明；但 current guidance 需要被显式投影到正式入口。

## 6. 对这轮 repo maintenance 的直接意义

本轮低风险整顿已经把几类高价值 current guidance 从 `docs/dev_log/` 升格出来：

- maintainer entry
- worktree policy
- artifact retention policy
- entrypoint matrix

后续再看 dev log 时，默认应把它理解成：

- 历史上下文库
- 设计与评审档案库
- walkthrough / validation archive

而不是新 agent 的第一入口。

## 7. 一句话结论

> 先看 `AGENTS.md`、`docs/README.md`、`docs/ops/*`、`runbook`、`contract_v1`；`docs/dev_log/` 用来追溯、找证据、读旧方案，不要把它整体当成 current canonical guidance。
