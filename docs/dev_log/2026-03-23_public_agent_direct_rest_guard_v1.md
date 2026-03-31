## Public Agent Direct REST Guard v1

Summary:

- `/v3/agent/turn`
- `/v3/agent/cancel`

now reject normal coding-agent direct REST calls and require the public advisor-agent MCP as the normal northbound path.

### What changed

Server:

- `chatgptrest/api/routes_agent_v3.py`
  - added a narrow direct-REST guard for coding-agent client names
  - returns `403 coding_agent_direct_rest_blocked`
  - keeps internal/maintenance clients allowed

CLI:

- `chatgptrest/cli.py`
  - `--agent-direct-rest` now sends `X-Client-Name: chatgptrestctl-maint`
  - default agent commands still go through public MCP

Tests:

- `tests/test_routes_agent_v3.py`
- `tests/test_cli_improvements.py`
- `tests/test_cli_chatgptrestctl.py`

### Why

The previous cutover made public MCP the default path, but direct REST was still easy to fall back to accidentally.

This round turns the policy into a live route-level guard:

- normal coding-agent northbound entry => MCP
- explicit maintenance/debug => maintenance client identity

### Verified behavior

- `chatgptrestctl` direct `/v3/agent/turn` => blocked
- `chatgptrestctl-maint` direct `/v3/agent/turn` => allowed
- public MCP traffic is unaffected because it uses `chatgptrest-mcp`
