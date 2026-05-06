# 2026-03-12 Issue Dev Controller OpenClaw Loop Walkthrough v3

## 本轮目标

把 `PR #139` review 中剩余的 hcom follow-up 真正落成代码，而不是只留在审查结论里。

本轮聚焦：

1. hcom 消息体从自定义 `key=value` 切换为 JSON
2. output 写入约束改成 `output_tmp_path -> atomic rename -> output_path`
3. target 匹配从“宽松前缀”收紧为“精确匹配或显式通配”
4. 补齐 `list-failure / send-failure / timeout` 错误路径测试

## 代码改动

更新文件：

- `chatgptrest/ops_shared/issue_dev_controller.py`
- `tests/test_issue_dev_controller.py`

### 1. hcom 消息体改为 JSON

旧实现：

- controller 发出的消息是多行 `key=value`
- 消费端必须靠约定好的 split 规则解析

新实现：

- `_build_hcom_task_message()` 现在返回 JSON body
- 增加 `message_type` 和 `schema_version`
- 结构里显式携带：
  - `worktree_path`
  - `prompt_path`
  - `output_path`
  - `output_tmp_path`
  - `schema_path`
  - `task_readme`
  - `pull_request_url`
  - `instructions`

这样远程角色不再依赖自定义 key=value 解析。

### 2. 原子写约束

新增 helper：

- `_hcom_output_tmp_path(output_path)`

controller 发给远程角色的消息里现在明确要求：

- 先把完整 JSON 写到 `output_tmp_path`
- 再通过原子 rename 切换到 `output_path`

`_wait_for_json_output()` 也增加了：

- `tmp_exists`
- `size`
- `mtime_ns`

并且只在同一文件签名稳定后才尝试解析，以降低读到“仍在写入中的最终文件”的概率。

### 3. target 匹配收紧

旧实现的问题：

- `@impl` 会匹配 `impl-1`、`impl-2`、`impl-anything`

新实现：

- 默认只接受精确匹配
- 只有显式写成 `@impl-*` 才做前缀通配

### 4. 错误路径测试补齐

新增/补充测试：

- `test_hcom_target_matching_is_exact_unless_wildcard`
- `test_hcom_task_message_is_json_with_atomic_output_hint`
- `test_wait_for_json_output_accepts_atomic_result_after_partial_file`
- `test_controller_loop_reports_hcom_list_failure`
- `test_controller_loop_reports_hcom_send_failure`
- `test_controller_loop_reports_hcom_output_timeout`

fake hcom 也同步升级：

- 支持 JSON message 解析
- 支持 `FAKE_HCOM_LIST_FAIL`
- 支持 `FAKE_HCOM_SEND_FAIL_TARGETS`
- 支持 `FAKE_HCOM_SKIP_OUTPUT_TARGETS`
- 默认走 `output_tmp_path -> os.replace()`

## 文档改动

更新文件：

- `docs/runbook.md`
- `ops/systemd/chatgptrest.env.example`

新增说明：

- hcom message 现在是 JSON，不再是 key=value
- output 必须走原子写
- wildcard 只能用显式 `@impl-*`

## 验证

### 编译

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/python -m py_compile \
  chatgptrest/ops_shared/issue_dev_controller.py \
  tests/test_issue_dev_controller.py
```

结果：通过。

### 测试

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_issue_dev_controller.py \
  tests/test_controller_lane_wrapper.py
```

结果：`13 passed`

## 本轮收口后的状态

`PR #139` review 里最后列的三项 follow-up 已经落地：

1. `_wait_for_json_output()` 的 TOCTOU 风险下降
2. hcom 消息体已迁移为 JSON
3. `send-failure / timeout / list-failure` 测试已补齐

仍未在本轮处理的项：

- controller 对“远程角色长期未上线”的 early-timeout 分层策略
- hcom 多机共享存储场景下的 stronger auth / origin validation
