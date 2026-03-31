# 2026-03-17 cc-sessiond SDK Live Probe Addendum v1

## Summary

After installing the official `claude-code-sdk` into the shared project
environment, a live MiniMax-backed SDK smoke test was executed successfully.

Result:

- `is_error = False`
- returned `result = "OK"`
- returned a real Claude session id
- usage and cost metadata were present

This upgrades the SDK path from "import/signature validated" to
"live runtime confirmed on this host".

## Command

```bash
cd /vol1/1000/projects/ChatgptREST
timeout 45s ./.venv/bin/python - <<'PY'
import asyncio, os
from claude_code_sdk import query, ClaudeCodeOptions, ResultMessage

async def main():
    opts = ClaudeCodeOptions(
        permission_mode='bypassPermissions',
        max_turns=1,
        env={
            'ANTHROPIC_BASE_URL': os.environ.get('MINIMAX_ANTHROPIC_BASE_URL', 'https://api.minimaxi.com/anthropic'),
            'ANTHROPIC_API_KEY': os.environ['MINIMAX_API_KEY'],
        },
    )
    async for msg in query(prompt='Reply with exactly OK.', options=opts):
        if isinstance(msg, ResultMessage):
            print({
                'is_error': msg.is_error,
                'session_id': msg.session_id,
                'result': msg.result,
                'cost': msg.total_cost_usd,
                'usage': msg.usage,
            })
            return

asyncio.run(main())
PY
```

## Output Summary

Observed result:

```text
is_error: False
result: OK
session_id: caf6c275-d613-4be9-b6c6-429498759722
```

Cost/usage metadata was also returned.

## Note About GeneratorExit Warning

The ad-hoc probe returned from the outer `async for` immediately after receiving
the `ResultMessage`, which triggered an SDK-internal cleanup warning:

- `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in`

This warning came from the probe harness shape, not from `cc-sessiond`
production flow:

- the probe exited early
- `cc-sessiond` backend code does not `return` from inside the stream loop; it
  yields events and lets iteration complete naturally

So this probe still counts as a successful live connectivity/runtime validation.
