# ChatgptREST

REST-first job service (stable contract) + thin MCP adapter for ChatGPT Web automation.

Design goals:
- Stable service boundary: REST v1 contract does not change frequently.
- Long outputs never travel through tool/client channels: answers are persisted to `artifacts/jobs/<job_id>/answer.md`.
- Idempotency + leases: client aborts/retries do not duplicate side effects.
- No Cloudflare bypass: any verification/login must be done manually in noVNC Chrome.

v1 contract: `docs/contract_v1.md`.

Docs index (recommended entrypoint): `docs/README.md`.
Development history / historical issues: `docs/handoff_chatgptrest_history.md`.
Ops runbook: `docs/runbook.md`.

Maintainer quick links:
- `docs/ops/2026-03-25_agent_maintainer_entry_v1.md`
- `docs/ops/2026-03-25_entrypoint_matrix_v1.md`
- `docs/ops/2026-03-25_worktree_policy_v1.md`
- `docs/ops/2026-03-25_artifact_retention_policy_v1.md`

Coding-agent repo entry:
- `./.venv/bin/python scripts/chatgptrest_bootstrap.py --task "<task>" --runtime quick`
- `./.venv/bin/python scripts/check_doc_obligations.py --diff HEAD`
- `./.venv/bin/python scripts/chatgptrest_closeout.py --agent codex --status completed --summary "..."`
- `chatgptrestctl repo bootstrap|doc-obligations|closeout`

## Env

- `CHATGPTREST_DB_PATH` (default: `state/jobdb.sqlite3`)
- `CHATGPTREST_ARTIFACTS_DIR` (default: `artifacts`)
- `CHATGPTREST_PREVIEW_CHARS` (default: `1200`)
- `CHATGPTREST_LEASE_TTL_SECONDS` (default: `60`)
- `CHATGPTREST_MAX_ATTEMPTS` (default: `3`)
- `CHATGPTREST_CHATGPT_MCP_URL` (default: `http://127.0.0.1:18701/mcp`)
- `CHATGPTREST_DRIVER_MODE` (default: `external_mcp`, options: `external_mcp|internal_mcp|embedded`)
- `CHATGPTREST_DRIVER_URL` (default: `CHATGPTREST_CHATGPT_MCP_URL`)
- `CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS` (default: `61`, applies to `chatgpt_web.ask` send actions)
- `CHATGPTREST_PRO_FALLBACK_PRESETS` (default: `thinking_heavy,auto`)
- `CHATGPTREST_SAVE_CONVERSATION_EXPORT` (default: `1`, best-effort export conversation JSON as `artifacts/jobs/<job_id>/conversation.json`)
- `CHATGPTREST_CHATGPTMCP_ROOT` (optional, default: `../chatgptMCP`; used to read external chatgptMCP debug snapshots for stuck-state detection)
- `CHATGPTREST_DRIVER_ROOT` (optional, used to read internal driver debug artifacts)
- `CHATGPTREST_API_TOKEN` (optional, require `Authorization: Bearer <token>` on all routes)
- `CHATGPTREST_OPS_TOKEN` (optional; `/v1/ops/*` prefers this token, and `/v1/jobs*` also accepts it as a fallback)
- `CHATGPTREST_WORKER_ROLE` (optional, `send|wait|all`; default `all`)
- `CHATGPTREST_WORKER_KIND_PREFIX` (optional; when set, the worker only claims jobs whose `kind` starts with this prefix, e.g. `repair.`)
- Driver env (internal/embedded):
  - `CHATGPT_MIN_PROMPT_INTERVAL_SECONDS` (default: `61`, driver-side send throttle)
  - `CHATGPT_BLOCKED_STATE_FILE` (default: `.run/chatgpt_blocked_state.json`)
  - `CHATGPT_MAX_CONCURRENT_PAGES` (default: `3`, cap concurrent tabs/pages)
  - `CHATGPT_PAGE_SLOT_TIMEOUT_SECONDS` (default: `0`, 0 means wait indefinitely)
  - `CHATGPT_TAB_LIMIT_RETRY_SECONDS` (default: `300`)
  - `MCP_IDEMPOTENCY_DB` (default: `.run/mcp_idempotency.sqlite3`)

## Local dev

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'

# Terminal A (API)
.venv/bin/python -m chatgptrest.api.app --host 127.0.0.1 --port 18711

# Terminal B (worker: send)
.venv/bin/python -m chatgptrest.worker.worker --role send

# Terminal C (worker: wait)
.venv/bin/python -m chatgptrest.worker.worker --role wait

# Terminal D (internal driver, optional)
CHATGPT_CDP_URL=http://127.0.0.1:9222 ops/start_driver.sh

# Terminal E (optional public agent MCP adapter; preferred because it loads env + fails fast on missing auth)
ops/start_mcp.sh
```

Create a dummy job:

```bash
curl -sS -X POST http://127.0.0.1:18711/v1/jobs \\
  -H 'Content-Type: application/json' \\
  -H 'Idempotency-Key: demo-1' \\
  -d '{"kind":"dummy.echo","input":{"text":"hello"},"params":{"repeat":3}}' | jq
```

Poll:

```bash
curl -sS http://127.0.0.1:18711/v1/jobs/<job_id> | jq
curl -sS http://127.0.0.1:18711/v1/jobs/<job_id>/result | jq
```

Fetch answer chunks:

```bash
curl -sS 'http://127.0.0.1:18711/v1/jobs/<job_id>/answer?offset=0&max_chars=2000' | jq
```

Note: `offset/max_chars` are byte-based for UTF-8-safe streaming.

Fetch conversation export chunks (best-effort):

```bash
curl -sS 'http://127.0.0.1:18711/v1/jobs/<job_id>/conversation?offset=0&max_chars=2000' | jq
```

## ChatGPT Web automation (driver)

Prereq: run either the internal driver (`ops/start_driver.sh`) or the external `chatgptMCP` MCP HTTP server with a logged-in Chrome (CDP).

For live `/v1/jobs` smoke, do not assume your current shell token matches the live service. Use the service env or the helper below:

```bash
./.venv/bin/python ops/run_low_level_ask_live_smoke.py
```

The helper now validates all of these against the live process:

- unsigned maintenance probes fail with `low_level_ask_client_auth_failed`
- signed HMAC maintenance probes succeed and return `job_id`
- when `CHATGPTREST_API_TOKEN` and `CHATGPTREST_OPS_TOKEN` are both configured and distinct, `/v1/jobs*` also accepts the OPS token fallback path
- unsigned `planning-wrapper` probes fail with `low_level_ask_client_auth_failed`
- signed `planning-wrapper` sufficiency probes still fail closed as `sufficiency_gate`
- signed substantive `planning-wrapper` review probes succeed, and an immediate duplicate is rejected with `low_level_ask_duplicate_recently_submitted`
- `openclaw-wrapper` and `advisor-automation` low-level `/v1/jobs` probes fail closed because those identities are no longer allowed on the external low-level ask surface

Create a maintenance-scoped low-level job via the CLI wrapper:

```bash
CHATGPTREST_CLIENT_NAME=chatgptrestctl-maint \
CHATGPTREST_CLIENT_INSTANCE=readme-demo \
CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT='replace-with-maint-secret' \
./.venv/bin/python -m chatgptrest.cli jobs submit \
  --kind chatgpt_web.ask \
  --idempotency-key demo-chatgpt-1 \
  --question '请用 3 条要点解释幂等性，并给一个简单例子。' \
  --preset auto \
  --job-timeout-seconds 240 \
  --max-wait-seconds 480 \
  --min-chars 200
```

Notes:
- Low-level web ask now requires a registered source identity. Maintenance/internal low-level callers that are `auth_mode=hmac` must also provide the matching shared secret env so the wrapper can sign each request. Raw HTTP callers must compute `X-Client-Timestamp`, `X-Client-Nonce`, and `X-Client-Signature` themselves.
- `planning-wrapper` is now the only approved automation wrapper identity that still keeps a low-level web-ask lane. That lane is HMAC-scoped, concurrency-limited, and duplicate-suppressed.
- `openclaw-wrapper`, `advisor-automation`, and `finbot-wrapper` are not approved for external low-level `/v1/jobs` web ask. Their supported northbound path is public advisor-agent MCP (or internal runtime, for advisor internals).
- Interactive coding clients should not copy this example; they must use the public advisor-agent MCP surface at `http://127.0.0.1:18712/mcp`.
- Use `preset=pro_extended` when you want Pro+Extended; if Pro is temporarily disabled (`unusual_activity`), ChatgptREST will fallback using `CHATGPTREST_PRO_FALLBACK_PRESETS`.
- To switch driver backends without changing clients:
  - `CHATGPTREST_DRIVER_MODE=internal_mcp` + `CHATGPTREST_DRIVER_URL=http://127.0.0.1:18701/mcp`
  - `CHATGPTREST_DRIVER_MODE=external_mcp` (legacy chatgptMCP)
  - `CHATGPTREST_DRIVER_MODE=embedded` (single-process; no MCP server)
- Follow-ups:
  - `conversation_url` is surfaced in `GET /v1/jobs/{job_id}`; pass it as `input.conversation_url` for the next `chatgpt_web.ask`.
  - Or pass `input.parent_job_id=<previous_job_id>` and let the server reuse the parent job's `conversation_url`.
- Strict formatting without expensive retries:
  - Let the primary turn answer normally (e.g. `preset=pro_extended`), then set `params.format_prompt` and `params.format_preset=thinking_extended` to reformat in a follow-up turn (same conversation; throttled like any other send).

## Ops

- Smoke test (human-like prompts, default `preset=auto`): `ops/smoke_test_chatgpt_auto.py`
- Monitor job events / blocked state (JSONL): `ops/monitor_chatgptrest.py`
- Resident maint daemon (monitor + incident evidence packs): `ops/maint_daemon.py` (see `docs/maint_daemon.md`)
- On-demand diagnostics (no prompt send): `kind=repair.check` (see `docs/contract_v1.md` / `docs/runbook.md`)
- Proxy delay snapshots (mihomo): `ops/mihomo_delay_snapshot.py` (one-shot) or `ops/mihomo_delay_daemon.sh` (loop)
  - On `blocked/cooldown`, the worker also records a best-effort snapshot into job events/artifacts for correlation.
- Public agent MCP adapter (StreamableHTTP): `ops/start_mcp.sh` (default `http://127.0.0.1:18712/mcp`; preferred coding-agent entry)
- Admin/broad MCP adapter (optional, internal only): `ops/start_admin_mcp.sh` (default `http://127.0.0.1:18715/mcp`)

Codex CLI config example (HTTP MCP):

```toml
[mcp_servers.chatgptrest]
url = "http://127.0.0.1:18712/mcp"
```

Claude Code / Antigravity JSON config example:

```json
{
  "mcpServers": {
    "chatgptrest": {
      "type": "http",
      "url": "http://127.0.0.1:18712/mcp"
    }
  }
}
```

The default public MCP now exposes only the high-level agent tools:
- `advisor_agent_turn`
- `advisor_agent_status`
- `advisor_agent_cancel`

Coding-agent policy:
- Other Codex / Claude Code / Antigravity clients should connect to `http://127.0.0.1:18712/mcp`.
- `18711` is the REST API base for `/v1/*`, `/v2/*`, and `/v3/*`; `18712` is only the public MCP base and should only be used as `http://127.0.0.1:18712/mcp`.
- For Antigravity / Claude JSON configs, do not use legacy `serverURL`; the canonical shape is `type=http` plus `url=http://127.0.0.1:18712/mcp`.
- Do not point coding agents directly at ChatgptREST REST endpoints as their default integration path.
- Do not launch ad-hoc public MCP processes unless the ChatgptREST env files are already loaded; use `ops/start_mcp.sh` or the systemd-managed `chatgptrest-mcp.service`.
- Drift audit and one-shot repair for known coding-agent configs: `python3 ops/check_public_mcp_client_configs.py --fix`

If you still need the legacy broad tool surface for ops/debugging, point a separate client at `http://127.0.0.1:18715/mcp`.

Tmux notifications (optional):
- Set `CODEX_CONTROLLER_PANE` to a tmux pane target (e.g. `"%1"`) to receive `submitted/done` notifications from the MCP adapter.

## Tests

```bash
.venv/bin/pytest -q
```
