# FINBOT-ENG-002 Kimi Code Controlled Artifact Smoke

Status: closed_with_no_mcp_smoke_pass

## Objective

Ask Kimi Code to create one controlled artifact inside the allowed root and validate it.

## Allowed Write Scope

- `artifacts/kimi_smoke/`

## Expected Artifact

- `artifacts/kimi_smoke/KIMI_SMOKE_RESULT.json`

## Validation

```bash
python3 tools/validate_issue_closeout.py artifacts/kimi_smoke/KIMI_SMOKE_RESULT.json
```

## Runtime Evidence

Two Kimi Code attempts were made:

1. `/vol1/maint/ops/scripts/kimi-direct.sh --work-dir ... --afk -y --max-steps-per-turn 6 -p ...`
   - waited more than 20 minutes;
   - no stdout;
   - no `artifacts/kimi_smoke/KIMI_SMOKE_RESULT.json`;
   - process manually terminated.
2. `kimicode --print --work-dir ... --afk -y --max-steps-per-turn 4 -p ...`
   - visible startup output reached MCP loading;
   - waited about 10 minutes after MCP loading;
   - no target artifact;
   - process manually terminated.

Blocked evidence: `artifacts/kimi_smoke/KIMI_SMOKE_BLOCKED.json`

## P0 Follow-Up Result

After Pro review, a repo-local no-MCP profile was added:

- `contracts/kimi_mcp_none.json`
- `tools/run_kimi_controlled_smoke.sh`
- `tools/validate_kimi_smoke_result.py`

Kimi Code wrote the target artifact:

- `artifacts/kimi_smoke/KIMI_SMOKE_RESULT.json`

Validator result:

```bash
python3 tools/validate_kimi_smoke_result.py artifacts/kimi_smoke/KIMI_SMOKE_RESULT.json
# status: pass
```

The wrapper command returned non-zero because Kimi stopped at `Max number of steps reached: 2`, but stdout shows the file was written successfully and the local validator passed.
