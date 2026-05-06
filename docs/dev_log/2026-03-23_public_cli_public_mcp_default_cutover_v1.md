## Public CLI Public-MCP Default Cutover v1

Summary:

- `chatgptrestctl agent turn`
- `chatgptrestctl agent status`
- `chatgptrestctl agent cancel`

now default to the public advisor-agent MCP surface instead of direct `/v3/agent/*` REST.

### What changed

- Added a public MCP helper to `chatgptrest/cli.py`
- Default execution path for `agent turn|status|cancel` now calls:
  - `advisor_agent_turn`
  - `advisor_agent_status`
  - `advisor_agent_cancel`
- Added explicit maintenance/debug override:
  - `--agent-direct-rest`
- Added top-level CLI flag:
  - `--public-mcp-url`

### Why

The northbound control plane was already live on the public advisor-agent MCP surface.
The remaining governance gap was that repo CLI still defaulted to direct `/v3/agent/*` REST.

This cutover aligns:

- repo CLI
- skill wrapper
- coding-agent configs

onto the same northbound surface.

### Validation

- `tests/test_cli_improvements.py`
- `tests/test_cli_chatgptrestctl.py`
- `python3 -m py_compile chatgptrest/cli.py tests/test_cli_improvements.py tests/test_cli_chatgptrestctl.py`

Key assertions:

- `agent turn` defaults to `advisor_agent_turn`
- `agent status` defaults to `advisor_agent_status`
- `agent cancel` defaults to `advisor_agent_cancel`
- `--agent-direct-rest` still preserves explicit maintenance/debug access to direct REST
