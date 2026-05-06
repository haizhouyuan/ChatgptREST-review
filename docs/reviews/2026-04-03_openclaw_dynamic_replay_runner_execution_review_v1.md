# 2026-04-03 OpenClaw Dynamic Replay Runner Execution Review v1

## 1. 这批改动解决了什么

这批没有改 `dynamic replay gate` 本体逻辑，而是修了它一直存在的 runner 断点：

- `python3 ops/run_openclaw_dynamic_replay_gate.py`

此前会直接报：

- `ModuleNotFoundError: No module named 'chatgptrest'`

也就是说，gate 本体虽然可以通过 `PYTHONPATH=.` 直接 import 运行，但最自然的 repo runner 其实是坏的。

这批补完后：

- runner 可直接运行
- 支持 `CHATGPTREST_EVAL_OUT_DIR`
- 会写 `manifest.json`
- exit code 与 gate 绿红一致

## 2. 我独立确认成立的事实

### 2.1 当前 dynamic replay gate 本体是 green，不再应该沿用旧的 fetch-failed 口径

我现场直接 import 运行过 gate，本体结果是：

- `num_checks=3`
- `num_failed=0`

通过的 3 条检查是：

- `dynamic_tool_registration`
- `dynamic_contract_capture`
- `live_planning_clarify_replay`

所以现在更准确的口径是：

> dynamic replay harness 当前本体可运行且为 green；之前阻塞运维使用的是 runner 可执行性，而不是 gate 核心逻辑本身。

### 2.2 这仍然不是 Feishu 聊天面证明

我当前只签：

- dynamic replay bridge/harness 是可运行的
- bridge contract capture 是通的
- live clarify replay 是通的

我不签：

- Feishu/OpenClawBot 真正聊天入口已证明
- planning 第一阶段已经完成

## 3. 验证

- `python3 -m py_compile ops/run_openclaw_dynamic_replay_gate.py tests/test_openclaw_dynamic_replay_gate.py tests/test_run_openclaw_dynamic_replay_gate.py`
- `./.venv/bin/pytest -q tests/test_openclaw_dynamic_replay_gate.py tests/test_run_openclaw_dynamic_replay_gate.py`
- `python3 ops/run_openclaw_dynamic_replay_gate.py`
