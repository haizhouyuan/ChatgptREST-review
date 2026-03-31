# ChatgptREST Document Plane Guide Walkthrough v1

> 日期: 2026-03-25
> 范围: 文档平面口径收口
> 结果: 完成 current guidance 与 `docs/dev_log/` 混合档案的显式区分，无运行时改动

## 1. 本轮落地内容

本轮只做了以下 docs-only 动作：

- 新增 `docs/ops/2026-03-25_document_plane_guide_v1.md`
- 在 `docs/README.md` 的建议阅读顺序中加入该文档
- 在 `AGENTS.md` 的建议阅读顺序中加入该文档

## 2. 本轮解决的问题

在这轮之前，repo 已经有：

- 正式 maintainer entry
- worktree policy
- artifact retention policy
- entrypoint matrix

但仍然缺一个明确口径：

- `docs/dev_log/` 不是单一语义平面
- 新 agent 不应把 `docs/dev_log/*` 整体当成 current canonical guidance

本轮补的 guide 解决的是：

- current guidance 在哪里
- `docs/dev_log/*` 里哪些更像 history
- 哪些更像 proposal / planning
- 哪些更像 review / validation / issue pack
- 发生冲突时默认以什么为准

## 3. 本轮刻意没有做的事

这轮刻意保持保守，没有提前做这些动作：

- 没有批量改旧 `docs/dev_log/*` 文件头
- 没有给旧 surface inventory 文档统一加 `historical reference only` 标签
- 没有改 `docs/dev_log/INDEX.md` 的旧内容结构
- 没有做任何文档删除、迁移、归档

原因很简单：

- 这些动作虽然也是 docs-only
- 但属于 backlog 里原先标成“需确认”的范围
- 本轮先把读取规则写清楚，比批量给旧文档贴标签更稳

## 4. 为什么这轮安全

本轮没有：

- 改代码
- 改脚本行为
- 改端口
- 改 systemd
- 改 runtime topology
- 改 `.run/` / `state/` / `artifacts/*`

因此这轮属于纯文档收口，不会影响 ChatgptREST 正常工作，也不会影响其他 Codex 的运行态。

## 5. 一句话结论

> 这轮把“当前 guidance 从哪读、dev_log 应该怎么读”写成了正式 maintainer guidance，但没有把需要二次确认的历史文档批量标记动作提前执行。
