# 2026-03-25 Low-Level Ask Identity Guard v1

## 背景

过去的 low-level web ask (`/v1/jobs kind=chatgpt_web.ask|gemini_web.ask|qwen_web.ask`) 主要靠 prompt 规则和少量 legacy client block 收口，存在三个结构性问题：

1. 来源身份不强制，很多 ask caller 只有 `name`，甚至完全空白，追责困难。
2. 交互式 coding client 与自动化 bot/pipeline 共用同一低层入口，容易绕开 public advisor-agent MCP。
3. automation caller 会把 extractor / sufficiency gate / JSON-only microtask 直接打到 live web ask，制造低价值会话与噪音。

## 本次改动

### 1. 新增 low-level ask client registry

- 文件：`ops/policies/ask_client_registry.json`
- 作用：把 low-level ask caller 注册成明确 profile，记录：
  - `client_id`
  - `aliases`
  - `source_type`
  - `trust_class`
  - `allowed_surfaces`
  - `allowed_kinds`
  - `allow_live_chatgpt / allow_gemini_web / allow_qwen_web / allow_deep_research / allow_pro`
  - `codex_guard_mode`
  - `auth_mode`

当前 registry 已覆盖：

- interactive coding family：`codex*` / `claude-code*` / `antigravity` / legacy bare wrappers
- maintenance/internal：`chatgptrest-admin-mcp` / `chatgptrestctl-maint` / submit wrappers
- registered automation：`advisor_*` / `openclaw-chatgptrest-call` / `planning-chatgptrest-call`
- testing-only：`smoke*` / `ops_smoke` / `chatgptrest.smoke` / `route_debug*`

### 2. 新增 identity-first ask guard

- 文件：`chatgptrest/core/ask_guard.py`
- 入口：`chatgptrest/api/routes_jobs.py`

low-level web ask 现在先过 identity/authz，再进入原有 prompt policy：

- 缺身份：`low_level_ask_client_identity_required`
- 未注册：`low_level_ask_client_not_registered`
- HMAC profile 缺签名 / 过期 / nonce replay：`low_level_ask_client_auth_failed`
- interactive coding client 直打 low-level ask：
  - `chatgpt_web.ask` -> `direct_live_chatgpt_ask_blocked`
  - `gemini_web.ask|qwen_web.ask` -> `coding_agent_low_level_ask_blocked`
- caller 超出 registry 权限：
  - `low_level_ask_surface_not_allowed`
  - `low_level_ask_kind_not_allowed`
  - `low_level_ask_live_chatgpt_not_allowed`
  - `low_level_ask_provider_not_allowed`
  - `low_level_ask_deep_research_not_allowed`
  - `low_level_ask_pro_not_allowed`

### 3. 新增 low-level ask intent guard

对于 registered automation caller：

- deterministic block：
  - synthetic smoke / trivial ping
  - sufficiency gate
  - structured microtask
  - JSON-only extractor
  - low-context `deep_research`
- gray-zone client 可选走 Codex schema classify：
  - schema：`ops/schemas/ask_guard_decision.schema.json`
  - 当前用于 `openclaw-wrapper` / `planning-wrapper`

### 4. 审计落盘

成功通过 guard 的 low-level ask，会把以下信息写入作业：

- `client_json`
  - canonical `client_id`
  - `requested_name`
  - `source_type`
  - `trust_class`
  - provenance headers
- `params.ask_guard`
  - registry version
  - resolved client identity
  - auth method
  - guard decision

## 行为变化

- `params.allow_direct_live_chatgpt_ask=true` 不再允许 interactive/unregistered caller 绕过 low-level ask gate。
- 维护例外只保留给 registry 中的 maintenance/internal identity。
- `smoke_test_chatgpt_auto` 这类 testing-only caller，会先在 identity/authz 层 fail-closed，不再依赖后续 prompt policy 才拦住。

## 回归

执行通过：

- `./.venv/bin/python -m py_compile chatgptrest/core/ask_guard.py chatgptrest/api/routes_jobs.py tests/test_block_smoketest_prefix.py tests/test_low_level_ask_guard.py`
- `./.venv/bin/pytest -q tests/test_block_smoketest_prefix.py tests/test_low_level_ask_guard.py`
- `./.venv/bin/pytest -q tests/test_write_guards.py tests/test_jobs_write_guards.py tests/test_client_name_allowlist.py tests/test_direct_provider_execution_gate.py`

新增覆盖：

- 缺身份 / 未注册来源
- interactive client low-level block
- registered automation 的 Codex classify allow/block
- HMAC-authenticated low-level ask
- `ask_guard` 元数据落库
