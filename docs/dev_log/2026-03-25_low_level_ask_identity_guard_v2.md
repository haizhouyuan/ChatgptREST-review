# 2026-03-25 Low-Level Ask Identity Guard v2

## 背景

在 v1 合入后，客户端验证又指出了两点需要立即修复：

1. `User-Agent: testclient` 可以伪造身份豁免，绕过 low-level ask identity gate。
2. `allow_with_limits` 只是审计字段，入口并没有真的把限制写回请求参数。

此外，`README.md` 里仍保留了一个不带注册身份头的 bare `/v1/jobs chatgpt_web.ask` curl 示例，和新契约不一致。

## 本次修复

### 1. 收紧 testclient exemption

文件：`chatgptrest/core/ask_guard.py`

`_testclient_identity_exempt()` 现在除了 `user-agent` 外，还要求：

- `request.client.host == "testclient"`
- 仍然没有 `X-Client-*` / body client identity

这意味着：

- 真正的 in-process FastAPI `TestClient` 仍可保持现有测试便利
- 仅靠伪造 `User-Agent: testclient` 的真实网络请求，不再能绕过 identity gate

### 2. 把 allow_with_limits 做成真实 enforcement

文件：

- `chatgptrest/core/ask_guard.py`
- `chatgptrest/api/routes_jobs.py`

新增 `apply_low_level_ask_guard_limits()`，当 Codex classifier 返回 `allow_with_limits` 时，入口会真的降权：

- `allow_deep_research=false` -> `params.deep_research=false`
- `allow_pro=false` -> 对支持非 Pro preset 的 provider 降成安全 preset（当前 `chatgpt_web.ask` / `qwen_web.ask` -> `auto`）
- `min_chars_override` / `short_answer_ok` -> 写回 `params.min_chars`

如果 classifier 要求“非 Pro 降级”，但 provider 根本没有 non-Pro low-level preset，则 fail-closed：

- `low_level_ask_limit_unenforceable`

同时，实际生效的限制会记录到：

- `params.ask_guard.enforced_limits`

### 3. 修正文档示例

文件：

- `README.md`
- `docs/contract_v1.md`
- `docs/runbook.md`

README 里的 low-level ask 示例现在明确改成 maintenance-scoped curl，并补了：

- `X-Client-Name`
- `X-Client-Instance`
- `X-Request-ID`

同时文档里明确写明：

- interactive coding client 不能照抄这个例子
- 应走 public advisor-agent MCP
- `allow_with_limits` 现在会真的降权请求字段

## 回归

执行通过：

- `./.venv/bin/python -m py_compile chatgptrest/core/ask_guard.py chatgptrest/api/routes_jobs.py tests/test_low_level_ask_guard.py`
- `./.venv/bin/pytest -q tests/test_low_level_ask_guard.py tests/test_block_smoketest_prefix.py tests/test_write_guards.py tests/test_jobs_write_guards.py tests/test_client_name_allowlist.py tests/test_direct_provider_execution_gate.py`

新增覆盖：

- `User-Agent: testclient` 伪造请求不会被当成 test-only exemption
- `allow_with_limits` 会真实写回 `preset/deep_research/min_chars`
