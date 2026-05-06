# 2026-03-12 Issue Dev Controller OpenClaw Loop Walkthrough v2

## 本轮目标

在已有的 Issue Ledger -> GitHub -> worktree -> implementer/reviewer -> PR/merge -> health 闭环上，补上 hcom/OpenClaw 远程角色派工模式，让 controller 不再只依赖本地 command template。

## 本轮改动

### 1. controller 支持 hcom 远程角色

更新文件：

- `chatgptrest/ops_shared/issue_dev_controller.py`

新增能力：

- `ControllerLoopConfig` 新增 `implementer_hcom_target`、`reviewer_hcom_target`、`hcom_dir`、`hcom_sender`、`hcom_poll_seconds`、`implementer_timeout_seconds`、`reviewer_timeout_seconds`
- controller 现在支持两种执行模式：
  - 本地模式：`implementer_command_template` / `reviewer_command_template`
  - hcom 模式：`implementer_hcom_target` / `reviewer_hcom_target`
- hcom 模式下先执行 `hcom list --names` 做目标发现
- controller 通过 hcom 消息把 `prompt_path`、`output_path`、`schema_path`、`worktree_path`、`task_readme` 发给远程角色
- controller 以共享文件系统上的 `output_path` JSON 作为 authoritative result，并等待其落盘
- lane continuity 状态在 hcom 模式下仍写回 `state/controller_lanes.sqlite3`

### 2. 修正 reviewer 成功判定

原实现里 reviewer 只要 wrapper 进程退出，就有可能被记成成功，即使结构化 JSON 没有真正写回。

本轮收口为：

- 只要 reviewer 被配置，就必须同时满足：
  - 执行器返回成功
  - `reviewer_result.json` 被成功解析

这避免了 hcom 超时或远程角色未写回结果时的假成功。

### 3. CLI 暴露 hcom 参数

更新文件：

- `ops/run_issue_ledger_openclaw_controller.py`

新增参数：

- `--implementer-hcom-target`
- `--reviewer-hcom-target`
- `--hcom-dir`
- `--hcom-sender`
- `--hcom-poll-seconds`
- `--implementer-timeout-seconds`
- `--reviewer-timeout-seconds`

并支持对应环境变量：

- `CHATGPTREST_DEV_LOOP_IMPLEMENTER_HCOM_TARGET`
- `CHATGPTREST_DEV_LOOP_REVIEWER_HCOM_TARGET`
- `CHATGPTREST_DEV_LOOP_HCOM_DIR`
- `CHATGPTREST_DEV_LOOP_HCOM_SENDER`
- `CHATGPTREST_DEV_LOOP_HCOM_POLL_SECONDS`
- `CHATGPTREST_DEV_LOOP_IMPLEMENTER_TIMEOUT_SECONDS`
- `CHATGPTREST_DEV_LOOP_REVIEWER_TIMEOUT_SECONDS`

### 4. 文档更新

更新文件：

- `docs/runbook.md`
- `ops/systemd/chatgptrest.env.example`

补充内容：

- hcom 远程 controller 的示例命令
- hcom 与 command template 的优先级规则
- `HCOM_DIR` 透传规则
- 远程角色必须共享 worktree 并写回结构化 JSON 的约束

## 验证

### 定向编译

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/python -m py_compile \
  chatgptrest/ops_shared/issue_dev_controller.py \
  ops/run_issue_ledger_openclaw_controller.py \
  tests/test_issue_dev_controller.py
```

结果：通过。

### 定向测试

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_issue_dev_controller.py \
  tests/test_controller_lane_wrapper.py
```

结果：`7 passed`

新增覆盖：

- hcom implementer + reviewer 完整 PR/merge/health 闭环
- hcom target 缺失时的失败收口

## 当前限制

- 当前 hcom 模式只做“发现 + 发消息 + 等共享输出文件”，还没有自动远程 `spawn`
- controller 不解析 hcom 回复正文；结果仍以共享文件落盘为准
- 若同时设置 command template 和 hcom target，当前实现优先使用 command template

## 后续建议

下一步可以继续补：

1. controller 直接调用 hcom/OpenClaw agent team 的远程唤醒与 lane 分配，而不要求目标预先在线
2. reviewer 完成后自动把 review 结论回写到 GitHub PR comment
3. merge 后接真实 systemd 服务与多服务 health bundle，而不只是一条 health URL
