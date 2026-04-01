# 2026-03-10 Role Runtime Integration + KB Hint

## 背景

`1A` 的 Role Pack plumbing 已经落地，但真实运行时还没有显式把 `role` 接进入口链路。当前阶段不需要再改 `RoleSpec`/`source.role` 基础结构，而是要把：

- OpenMind cognitive API
- Advisor v3 API
- OpenClaw OpenMind plugins

真正接到显式 `role_id` 上，同时保持：

- `source.agent` 继续表示组件归因
- `source.role` 只表示业务角色
- KB 角色视图默认 `fail-open`

## 这轮改动

### 1. Cognitive API 接显式 role

- `routes_cognitive.py`
  - `/v2/context/resolve`
  - `/v2/memory/capture`
  - `/v2/policy/hints`
  全部新增 `role_id`

- `memory_capture_service.py`
  - `MemoryCaptureItem` 新增 `role_id`
  - capture 写入时显式落 `MemorySource.role`
  - capture 事件补充 `role_id`

- `policy_service.py`
  - `PolicyHintsOptions` 新增 `role_id`
  - 下传到 `ContextResolveOptions`

### 2. ContextResolver 接 role-aware memory + KB hint

- `ContextResolveOptions` 新增 `role_id`
- `ContextResolver.resolve()`：
  - 先显式读取 `role_id`
  - 再 fallback 到 `role_context`
  - 读取 `RoleSpec.kb_scope_tags`
- `_NoEmbedKBHub` 改成支持三态：
  - `off`
  - `hint`
  - `enforce`

当前默认策略：
- 如果 role 无 tags，则 `off`
- 如果 role 有 tags，默认 `hint`
- 不改 `KBHub.search()` 全局行为，只在 hot-path context resolver 内局部生效

### 3. Advisor v3 接显式 role binding

- `routes_advisor_v3.py`
  - 新增 `_bind_role(role_id)`
  - `/v2/advisor/advise`
  - `/v2/advisor/ask`
  在真实路由执行期间进入 `with_role(...)`
- 修正了一个真实回归：
  - `invalid_role_id` 现在返回 `400`
  - 不再被通用异常包装成 `500`

### 4. OpenClaw 插件接显式 role

- `openmind-memory`
  - `defaultRoleId`
  - recall/capture 支持显式 `roleId`
  - 自动 hook 也会转发默认 role

- `openmind-advisor`
  - `defaultRoleId`
  - `openmind_advisor_ask` 支持显式 `roleId`
  - `/v2/advisor/ask` 和 `/v2/advisor/advise` 都会转发 `role_id`

## 验证

执行过：

```bash
./.venv/bin/python -m py_compile \
  chatgptrest/api/routes_cognitive.py \
  chatgptrest/cognitive/context_service.py \
  chatgptrest/cognitive/memory_capture_service.py \
  chatgptrest/cognitive/policy_service.py \
  chatgptrest/api/routes_advisor_v3.py

./.venv/bin/pytest -q \
  tests/test_cognitive_api.py \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_controller_lane_continuity.py

./.venv/bin/pytest -q \
  tests/test_advisor_v3_end_to_end.py \
  tests/test_routes_advisor_v3_security.py
```

新增/覆盖的关键行为：

- role memory 冷启动不报错
- role recall 不覆盖 component identity
- KB hint 优先 role tags 命中，但不 hard fail
- advisor v3 显式 role 生效
- unknown role 返回 `400 invalid_role_id`
- OpenClaw 插件 manifest / source / README 对 role 参数一致

## 决策

这一轮之后：

- `1A` 不再只是底层 plumbing，而是已经开始进入真实入口链路
- KB role scope 仍然不是强过滤，仍保持 `hint`/`off` 思路
- continuity 继续按 observability-only 收口，不在本轮扩大

下一步重点应转向：

- continuity live fleet onboarding
- role 的真实业务流验收
- 在 1C tag 治理基础上把 KB scope 从 `off` 推到稳定 `hint`
