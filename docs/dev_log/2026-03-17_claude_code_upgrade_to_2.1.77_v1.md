# Claude Code Upgrade To 2.1.77 v1

Date: 2026-03-17

## What Changed

Upgraded the Claude Code installation used by `claudeminmax` from `1.0.110` to `2.1.77`.

## Why

The existing install was too old for modern Agent Teams usage and was causing confusion during Claude Code orchestration tasks.

## Actual Install Path

The wrapper in use is:

- `/home/yuanhaizhou/.local/bin/claudeminmax`

That wrapper delegates to:

- `/home/yuanhaizhou/local/node/bin/claude`

Which resolves to the package under:

- `/home/yuanhaizhou/local/node/lib/node_modules/@anthropic-ai/claude-code/`

## Upgrade Command

Used an explicit prefix so the upgrade hit the real install that the wrapper points to:

```bash
/home/yuanhaizhou/local/node/bin/npm install -g @anthropic-ai/claude-code@2.1.77 --prefix /home/yuanhaizhou/local/node
```

## Verification

Verified package version:

```bash
node -e "const p=require('/home/yuanhaizhou/local/node/lib/node_modules/@anthropic-ai/claude-code/package.json'); console.log(p.version)"
```

Output:

```text
2.1.77
```

Verified wrapper-level CLI help:

```bash
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 claudeminmax --help
```

The CLI now exposes the current modern option surface from the upgraded Claude Code install.

## Notes

- This was a system-level tool upgrade, not a product code change.
- The repo itself was not modified beyond this record.
- The wrapper still defaults `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.
