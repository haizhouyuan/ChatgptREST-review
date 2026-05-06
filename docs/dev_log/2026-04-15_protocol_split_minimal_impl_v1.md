---
title: A类服务协议切分最小实现
date: 2026-04-15
author: codex
status: completed
version: v1
---

# 本次改动

本次只做一件事：把 A 类服务从完整 `AdvisorRuntime` 的隐式依赖，收紧成可验证的最小协议面。

改动范围：

1. 新增 `chatgptrest/kernel/protocols.py`
2. 新增 `chatgptrest/cognitive/runtime_adapters.py`
3. 收紧 `ContextResolver` 与 `MemoryCaptureService` 的构造参数类型
4. 新增三组协议切分测试

# 关键决策

1. 协议定义放在 `kernel/`，不是 `cognitive/`
2. adapter 不做大容器封装，只做最小字段投影
3. `MemorySubstrate` 冻结为 7 个方法：
   - `stage`
   - `promote`
   - `stage_and_promote`
   - `audit_trail`
   - `get_episodic`
   - `get_by_key`
   - `update_record_value`

# 为什么这样做

原因不是类型整洁，而是要证明两件事：

1. `ContextResolver` 和 `MemoryCaptureService` 真正依赖的是少量资源句柄，不是整个 runtime 容器
2. Hermes 原生化后，A 类服务可以先通过最小协议面重宿主，而不是继续绑死旧前台壳层

# 测试结果

使用项目虚拟环境执行：

```bash
.venv/bin/pytest -q \
  tests/test_advisor_api.py \
  tests/cognitive/test_context_protocol_split.py \
  tests/cognitive/test_memory_capture_protocol_split.py \
  tests/kernel/test_work_memory_manager_memory_substrate_contract.py
```

结果：

- `tests/test_advisor_api.py` 通过
- 新增 3 组协议切分测试通过
- 总计 `16 passed`

# 额外说明

仓内存在无关改动：

- `ops/chrome_start.sh`
- `ops/chrome_stop.sh`
- `ops/chrome_profile_state.py`
- `tmp/`

这些不是本次任务的一部分，没有纳入本次提交。
