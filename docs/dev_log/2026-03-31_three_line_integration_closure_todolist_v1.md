# 2026-03-31 三线集成收口 Todo 与验收冻结 v1

## 目标

把以下三条已分别开发/评审过的主线合到同一主代码快照，并做一次高标准联合验证：

1. `Task Runtime / Agent Harness foundation`  
   来源：PR #210 及后续 `master`
2. `Repo cognition / bootstrap / doc obligations / closeout`  
   来源：`68729134` + `61a0a480`
3. `opencli / CLI-Anything integration`  
   来源：`feat/opencli-cli-anything-integration-20260331`

## 主控原则

- 不在当前脏主工作树上直接做合并。
- 不覆盖并行 Codex 尚未提交的 Gemini 相关修改。
- 先在干净集成 worktree 合并和联测，联测绿后再回推主线。
- 联测中暴露出的真实集成缺口，必须先修掉再报告完成。

## 待办清单

- [x] 确认三条线中哪些已经在 `master`
- [x] 确认未合并分支并建立干净集成 worktree
- [x] 合并 `feat/opencli-cli-anything-integration-20260331`
- [x] 解决与当前 `master` 的冲突
- [x] 跑三条线联合回归
- [x] 跑 bootstrap / doc-obligations / closeout 运行面验证
- [x] 安装 `opencli` binary 并补 `doctor --no-live`
- [x] 跑 `opencli smoke`
- [x] 修掉联测新暴露的真实缺口
- [x] 把集成结果推回 `origin/master`
- [x] 留痕本收口文档

## 合并策略与实际决策

### 已在主线

- `Task Runtime / Agent Harness foundation`
- `Repo cognition / bootstrap / obligations / closeout`

### 未在主线

- `feat/opencli-cli-anything-integration-20260331`

### 集成 worktree

- 路径：`/tmp/chatgptrest-integration-20260331`
- 分支：`tmp/integration-20260331`

### 冲突处理原则

- `repo_cognition/contracts.py`：保留主线更完整 contract
- `ops/health_checks.py`：保留主线更完整 quick/deep runtime summary
- `ops/health_probe.py`：保留主线 shared helper delegation
- `ops/registries/doc_registry.yaml`：保留主线 `check_doc_obligations.py` / `chatgptrest_closeout.py` 入口
- `docs/gemini_web_ui_reference.md`：保留主线，视作无关快照漂移
- `chatgptrest/cli.py`：合并保留 `repo` 子命令与 `opencli` 子命令

## 联测期间新发现并修复的真实缺口

### 1. worktree 场景下 GitNexus repo name 漂移

症状：

- `tests/test_repo_cognition_gitnexus_adapter.py` 在集成 worktree 中失败
- 原因是 `repo_cognition.gitnexus_adapter` 使用 `REPO_ROOT.name` 作为 GitNexus repo 名
- 在 worktree 中 repo root basename 变成 `chatgptrest-integration-20260331`

修复：

- 改成优先从 `git config --get remote.origin.url` 解析 canonical repo name
- fallback 才使用当前目录名

对应提交：

- `fix(repo-cognition): resolve canonical repo name in worktrees`

### 2. opencli live success 结果可以是 JSON array

症状：

- `opencli smoke` 在真实执行成功后，`structured_result` 返回 list
- `ops/run_opencli_executor_smoke.py` 把 `structured_result` 一律当 dict 调 `.keys()`
- `OpenCLIExecutionResult.structured_result` 的 contract 也写窄了

修复：

- `structured_result` contract 放宽为任意 JSON 值
- `from_dict()` 保留原始 JSON 结构
- smoke script 改成区分 dict / list / scalar 打印 shape
- 新增 list-payload 回归测试

## 联合测试矩阵

命令：

```bash
cd /tmp/chatgptrest-integration-20260331
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_task_runtime.py \
  tests/test_finbot.py \
  tests/test_llm_connector.py \
  tests/test_opencli_policy.py \
  tests/test_opencli_executor.py \
  tests/test_cli_anything_market_manifest.py \
  tests/test_routes_agent_v3_opencli_lane.py \
  tests/test_import_skill_market_candidates.py \
  tests/test_repo_cognition_gitnexus_adapter.py \
  tests/test_repo_cognition_runtime.py \
  tests/test_chatgptrest_bootstrap.py \
  tests/test_doc_obligations.py \
  tests/test_chatgptrest_closeout.py \
  tests/test_health_probe.py \
  tests/test_agent_mcp.py \
  tests/test_cli_chatgptrestctl.py
```

结果：

- 退出码：`0`

## 运行面验证

### bootstrap

命令：

```bash
PYTHONPATH=. ./.venv/bin/python scripts/chatgptrest_bootstrap.py \
  --task 'Fix public MCP ingress drift' \
  --goal-hint public_agent \
  --runtime quick
```

验收点：

- `schema_version = bootstrap-v1`
- `task_relevant_symbols.status = resolved`
- `surface_policy.default_for_coding_agents = http://127.0.0.1:18712/mcp`

### doc obligations

命令：

```bash
PYTHONPATH=. ./.venv/bin/python -m chatgptrest.cli --output json \
  repo doc-obligations \
  --changed-files chatgptrest/mcp/agent_mcp.py AGENTS.md
```

验收点：

- `ok = true`
- `required_docs = [AGENTS.md]`

### closeout

命令：

```bash
PYTHONPATH=. ./.venv/bin/python scripts/chatgptrest_closeout.py --json \
  --agent codex \
  --status completed \
  --summary 'integration closure smoke' \
  --changed-files chatgptrest/repo_cognition/gitnexus_adapter.py tests/test_repo_cognition_gitnexus_adapter.py
```

验收点：

- 单个结构化 JSON
- `ok = true`

### opencli

安装：

```bash
cd /vol1/1000/projects/jackwener/opencli
npm install
npm run build
npm link
```

安装结果：

- `opencli` 已可执行
- 版本：`1.5.6`

doctor：

```bash
PYTHONPATH=. ./.venv/bin/python -m chatgptrest.cli --output json opencli doctor --no-live
```

验收点：

- `ok = true`
- daemon running
- extension 未连接被明确报告，不是假成功

smoke：

```bash
PYTHONPATH=. ./.venv/bin/python -m chatgptrest.cli --output json opencli smoke
```

验收点：

- `ok = true`
- allowlisted command 成功
- invalid command / invalid args fail-closed

## 已推回主线

- remote: `origin/master`
- 推送前：`a0b42bb4`
- 推送后：以本次集成头覆盖为最新 `master`

## 剩余边界

- 当前主工作树仍有与本次三线任务无关的 Gemini 脏改，未处理
- `opencli` Browser Bridge extension 仍未接入，因此浏览器桥接 lane 的 live success 不是本次验收范围
- 本次 `opencli smoke` 已验证 binary + policy + subprocess lane + public command 成功，但不等于浏览器桥接模式已完成

## 最终判定

这三条线现在已经在同一主线快照内完成：

- 合并
- 联测
- 运行面验证
- 集成缺口修复

可作为当前 `master` 的有效集成基线继续推进。
