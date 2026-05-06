# Claude Agent SDK Session Manager Research Walkthrough v1

Date: 2026-03-17

## What I Investigated

- Re-read the current shared `claudecode-agent-runner` skill and the patched stream-json runner behavior
- Checked the official Anthropic Agent SDK docs for:
  - Python SDK
  - TypeScript SDK
  - session management
  - options surface
- Validated local environment behavior against the official SDK

## Key Findings

1. The official Agent SDK is real and materially stronger than our current shell runner.
2. The pasted `CCSessionManager` idea is directionally right but far too thin for production use.
3. The current local `claudeminmax` wrapper cannot be used directly as `cli_path` for the Python SDK right now.
4. The official SDK works locally when using its own compatible bundled CLI.

## Local Proofs

### Direct Claude CLI

- `claudeminmax -v` => `1.0.110`
- direct `claudeminmax -p ... --output-format json` works

### Python Agent SDK

- `claude-agent-sdk` is not preinstalled
- installed it in a temporary venv
- official SDK + bundled CLI succeeded with a minimal JSON reply
- official SDK + `cli_path=/home/yuanhaizhou/.local/bin/claudeminmax` failed with:

```text
error: unknown option '--setting-sources'
```

## Outcome

I wrote the formal assessment here:

- [2026-03-17_claude_agent_sdk_session_manager_assessment_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-17_claude_agent_sdk_session_manager_assessment_v1.md)

Core recommendation:

- keep the improved runner as fallback
- build a real `cc-sessiond` on top of the official Python Agent SDK
- do not attempt a direct drop-in replacement using the current `claudeminmax` wrapper until CLI compatibility is solved
