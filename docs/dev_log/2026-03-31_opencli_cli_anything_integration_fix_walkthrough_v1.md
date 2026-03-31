# 2026-03-31 opencli CLI-Anything 集成修复 walkthrough v1

## 背景

针对分支 `feat/opencli-cli-anything-integration-20260331` 的 Phase 1-5 实施结果做代码级接手修复，目标不是扩范围，而是把已实现的 opencli 窄 lane、CLI-Anything candidate manifest 和相关验证收成可合并状态。

接手时存在 3 类阻断问题：

1. `OpenCLIExecutor` 文件本身不能通过 `py_compile`
2. Phase 5 manifest 结构与现有 `import_skill_market_candidates.py` 不兼容
3. 路由与回归测试大量是占位、失效或 mock 了错误的运行时语义

## 本次修复

### 1. OpenCLIExecutor 运行时修复

- 删除重复的 `_execute_once()` 定义，修复语法错误
- 把 `subprocess.CompletedProcess.exit_code` 改为真实字段 `returncode`
- 默认 artifact 根目录改为 repo-root 下的 `artifacts/opencli`
- 增加 `capability_id` 与 allowlisted command policy 的一致性校验
- command 构造改为尊重 policy 的 `output_format`
- retryable 判定改为 `classify_exit_code()` 与 policy `retryable_exit_codes` 联合决定

### 2. Policy 路径与 CLI 行为修复

- `OpenCLIExecutionPolicy` 默认从 repo-root 解析 `ops/policies/opencli_execution_catalog_v1.json`
- 避免服务启动工作目录变化导致策略文件静默找不到
- 验证 `chatgptrest.cli opencli policy` 可正确读取当前 catalog

### 3. opencli lane 响应结构修复

- 增加 `_opencli_artifact_rows()`，把 executor 返回的本地文件路径转换成统一 artifact dict
- `routes_agent_v3.py` 在 opencli 分支里不再把 `list[str]` 直接塞进 `artifacts`
- opencli 分支的 provenance 不再复用 provider-selection 语义
- opencli 解析失败分支也统一去掉 provider request 投影，避免把 executor 伪装成 provider fallback

### 4. CLI-Anything candidate intake 修复

- `build_cli_anything_market_manifest.py` 改为输出真正的 manifest：
  - `schema_version`
  - `source_market`
  - `generated_at`
  - `candidates`
- 保留 candidate 内部字段：
  - `candidate_id`
  - `skill_id`
  - `source_uri`
  - `capability_ids`
  - `status=quarantine`
  - `trust_level=unreviewed`
  - `quarantine_state=pending`
  - `evidence.*`
- 新增测试验证：生成的 manifest 可被现有 `import_skill_market_candidates.py` 直接消费

### 5. 测试修复

- `tests/test_opencli_executor.py`
  - 改用真实 `CompletedProcess(returncode=...)` 语义
  - 增加 capability mismatch 测试
- `tests/test_cli_anything_market_manifest.py`
  - 改为验证 top-level manifest + `candidates[0]`
  - 增加与 importer 的兼容性测试
- `tests/test_routes_agent_v3_opencli_lane.py`
  - 删除占位 `pass`
  - 改为真实 `TestClient` 路由测试
  - 覆盖：
    - 无 execution_request 不触发 opencli
    - 错误 executor_kind 不触发 opencli
    - 有效 execution_request 进入 opencli lane
    - opencli 失败时不静默 fallback 到 controller/provider web
    - image / consult / direct Gemini 既有分支保持原优先级
    - provider registry 仍只有 `chatgpt` / `gemini`

## 验证结果

### 代码级验证

已通过：

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/python -m py_compile \
  chatgptrest/executors/opencli_executor.py \
  chatgptrest/executors/opencli_policy.py \
  chatgptrest/api/routes_agent_v3.py \
  ops/build_cli_anything_market_manifest.py \
  tests/test_opencli_policy.py \
  tests/test_opencli_executor.py \
  tests/test_cli_anything_market_manifest.py \
  tests/test_routes_agent_v3_opencli_lane.py \
  tests/test_import_skill_market_candidates.py
```

### 定向测试

已通过：

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_opencli_policy.py \
  tests/test_opencli_executor.py \
  tests/test_cli_anything_market_manifest.py \
  tests/test_routes_agent_v3_opencli_lane.py \
  tests/test_import_skill_market_candidates.py
```

结果：`42 passed`

### CLI / operator 面验证

已验证：

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python -m chatgptrest.cli --output json opencli policy
```

结果：

- 能成功读取当前 allowlist catalog
- 当前 catalog 有 1 条命令：`hackernews.top`

### 环境约束验证

本机当前 **没有** `opencli` 二进制：

```bash
which opencli
```

结果为空。

因此 live smoke 当前只能验证“缺二进制时 fail-closed 正常”，不能验证真实 Browser Bridge / daemon / CDP 执行。已验证：

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python -m chatgptrest.cli --output json opencli doctor --no-live
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python -m chatgptrest.cli --output json opencli smoke
```

结果：

- `opencli doctor --no-live` 返回 `opencli binary not found in PATH`
- `opencli smoke` 返回 `config_error`，不会假成功，也不会静默 fallback

## 当前结论

本次接手修复已经把 **代码正确性、manifest 兼容性、窄 lane 回归测试** 收到可合并状态。

当前剩余的不是代码阻断，而是环境阻断：

- 需要在目标环境安装 `opencli`
- 如果后续要推进 Browser Bridge/browser-mode 命令，还需要额外验证扩展、daemon、登录态与受控执行策略

在现有环境下，这条分支已经完成：

1. 代码修复
2. 结构修复
3. 测试修复
4. fail-closed 行为验证

未完成且不应在本次虚构完成的事项：

1. 真实 `opencli` browser command live success smoke
2. Browser Bridge / daemon / logged-in Chrome 环境验收
3. Phase 6 生产化扩展
