# 2026-04-03 Planning Task Checkpoint Query CLI Execution Review v1

## 本批目标

为深度工作台补上最缺的两条薄入口：

1. 通过 `task_id` 直接读取 planning task checkpoint / handoff
2. 通过稳定 identity 列出最近 planning task，便于继续旧任务

这批不改 task store 内核，不改 agent route，只把已有 task truth 能力暴露成可直接使用的 CLI。

## 实际改动

1. 新增 `scripts/planning_task_checkpoint_get.py`
   - 输入 `task_id`
   - 默认必须带 identity，或显式设置 `PLANNING_TASK_SESSION_ID`
   - 默认返回 handoff-oriented compact payload
   - 只有 `--full` 才返回完整允许 payload
   - 只有 `--unsafe-local-read` 才允许绕过 identity 直接读 raw local record
2. 新增 `scripts/planning_task_checkpoint_list.py`
   - 支持 `account_id / thread_id / user_id / session_id`
   - 支持 `task_type / status / limit`
   - 支持 `--compact`
   - 缺 identity 时 fail-closed
   - 默认不再把 `TMUX_PANE / TERM_SESSION_ID` 当作隐式 session 身份
3. 新增 `tests/test_planning_task_checkpoint_query.py`
   - `get compact handoff`
   - `get requires identity`
   - `get ignores TMUX_PANE implicit fallback`
   - `get identity mismatch fail-closed`
   - `get explicit session env fallback`
   - `get unsafe-local-read explicit sharp edge`
   - `list recent identity tasks`
   - `list account/thread env fallback`
   - `list ignores TMUX_PANE implicit fallback`
   - `list explicit session env fallback`
   - `list requires identity`

## 验证结果

已通过：

1. `python3 -m py_compile scripts/planning_task_checkpoint_get.py scripts/planning_task_checkpoint_list.py tests/test_planning_task_checkpoint_query.py`
2. `./.venv/bin/pytest -q tests/test_planning_task_checkpoint_query.py tests/test_planning_task_checkpoint_complete.py tests/test_planning_task_checkpoint_writeback.py`

## 这批完成后代表什么

现在深度工作台跨端继续时，不再只有“写回完成”这一个动作，也有了：

1. 取回某个 task 的当前 checkpoint / handoff
2. 按稳定 identity 查看最近 planning task

这使 `W2` 从“能写回”往“真能继续”走了一步。

## 这批边界也一并收紧了

1. 默认不再偷用 `TMUX_PANE / TERM_SESSION_ID` 当 session 身份
2. session-only 路径必须是显式 `--session-id` 或 `PLANNING_TASK_SESSION_ID`
3. `--unsafe-local-read` 明确只是 maintenance-only sharp edge，不是常规工作流入口

## 这批仍然没有宣称的部分

1. 这还不是完整 task truth layer
2. 这还没有解决 OpenClawBot 材料 intake
3. 这还没有把所有高频 planning task 的 resume 规则做实
