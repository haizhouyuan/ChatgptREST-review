# Issue #161 OpenClaw Hot-Path Visibility Todo v1

**日期**: 2026-03-13  
**分支**: `codex/issue-161-implementation-20260313`

---

## 主 checklist

- [x] 复核 `#121 #128 #129 #132 #134 #161` 当前状态
- [x] 在独立 worktree 建分支，隔离脏工作树
- [x] 在改代码前完成核心 blast radius 检查
- [x] 新建详细执行计划文档
- [x] 修改 `openmind-memory` 默认 recall sources
- [x] 让 `graph_scopes` 与 `graph` source 对齐
- [x] 更新 `openmind-memory` README / 版本信息
- [x] 更新或新增 plugin regression tests
- [x] 跑 targeted tests
- [ ] 写 walkthrough
- [ ] 提交代码
- [ ] 开 PR，并把 PR 链接回 `#161`
- [ ] 执行 closeout

---

## 备注

- 本轮只做 `#161` 的热路径修复，不顺手改 `#128/#129/#132/#134`
- `#129` 是本轮之后最明确的下一阶段 blocker
- 已完成验证：
  - `python3 -m py_compile tests/test_openclaw_cognitive_plugins.py tests/test_cognitive_api.py`
  - `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_openclaw_cognitive_plugins.py tests/test_cognitive_api.py`
