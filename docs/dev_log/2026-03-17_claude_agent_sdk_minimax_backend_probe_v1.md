# Claude Agent SDK MiniMax Backend Probe v1

Date: 2026-03-17

## Question

Can the official Claude Agent SDK use the existing MiniMax key as its backend credential?

## Short Answer

**Yes, but not through the current `cli_path=claudeminmax` wrapper path.**

What works:

- official Python Agent SDK
- official compatible/bundled Claude Code CLI
- environment:
  - `ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic`
  - `ANTHROPIC_API_KEY=$MINIMAX_API_KEY`

What does not work:

- official Python Agent SDK
- `ClaudeAgentOptions(cli_path='/home/yuanhaizhou/.local/bin/claudeminmax')`

## Local Validation

### Probe 1: bundled CLI + MiniMax env

Environment on this host:

- `MINIMAX_API_KEY` is set
- `MINIMAX_ANTHROPIC_BASE_URL` is set

Test pattern:

```bash
ANTHROPIC_BASE_URL="${MINIMAX_ANTHROPIC_BASE_URL:-https://api.minimaxi.com/anthropic}" \
ANTHROPIC_API_KEY="${MINIMAX_API_KEY}" \
python probe.py
```

Where `probe.py` used:

```python
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
```

Result:

```json
{"ok":true}
```

So the MiniMax key itself is usable as the SDK backend credential as long as the CLI path is compatible.

### Probe 2: `cli_path=claudeminmax`

Test pattern:

```python
ClaudeAgentOptions(
    cwd=Path('/vol1/1000/projects/ChatgptREST'),
    cli_path='/home/yuanhaizhou/.local/bin/claudeminmax',
    max_turns=1,
)
```

Result:

```text
error: unknown option '--setting-sources'
```

This means the current wrapper/backend combination is not directly SDK-compatible as a `cli_path` target.

## Interpretation

The blocker is **not** the MiniMax key.

The blocker is the execution path:

- SDK transport expects a Claude Code CLI that supports the control flags it sends
- the current `claudeminmax` path points to a local Claude Code CLI version that does not support at least one of those flags

## Practical Conclusion

If we build `cc-sessiond` on the official Python Agent SDK, there are two viable paths:

1. **Preferred immediate path**
   - use the official SDK-compatible Claude Code CLI
   - inject MiniMax via `ANTHROPIC_BASE_URL` + `ANTHROPIC_API_KEY`

2. **Later compatibility path**
   - make the `claudeminmax` wrapper chain SDK-compatible
   - which likely requires aligning the underlying Claude Code CLI version and control-flag support

So the correct answer to “can we directly use the MiniMax key as SDK backend?” is:

- **Yes for the key/provider**
- **No for the current wrapper path as-is**
