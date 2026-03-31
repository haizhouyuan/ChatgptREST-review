# External Review Request B — opencli / CLI-Anything Integration v2

Review target:

- `2026-03-31_ChatgptREST_opencli_CLI-Anything_集成详细实施方案_v2.md`
- `CODE_CONTEXT_MAP.md`
- current code files listed in section C of `CODE_CONTEXT_MAP.md`
- mirrored external code:
  - `docs/reviews/agent_harness_20260331/external_code/opencli/`
  - `docs/reviews/agent_harness_20260331/external_code/cli_anything/`

Question:

Given the current ChatgptREST capability-governance and routing architecture, is `v2` the correct implementation plan for integrating `opencli` and `CLI-Anything` at high standards?

## What to evaluate

1. Is the revised positioning correct?
   - `opencli` as controlled external execution substrate
   - `CLI-Anything` as untrusted generated artifact source
2. Is the proposed Phase 1 realistic?
   - subprocess `OpenCLIExecutor`
   - one explicit opt-in lane
   - no image / consult / direct Gemini lane changes
3. Are the risk boundaries strict enough?
   - command allowlist
   - no auto-install
   - no arbitrary passthrough
   - no default logged-in surface
   - no direct canonical-registry writes from generated artifacts
4. Is the proposed intake path correct?
   - generated package / manifest / validation bundle ingest
   - review evidence plane
   - market/quarantine intake
   - owner-controlled registry promotion
5. What is still dangerous, unrealistic, or underspecified?
6. What exact files/modules should Phase 1 touch?
7. What should the first acceptance test matrix be?

## Required output format

Please structure the answer into:

1. `Verdict`
2. `What v2 gets right`
3. `What v2 still gets wrong`
4. `Phase 1 implementation boundaries`
5. `Required safety and governance gates`
6. `Acceptance test matrix`
7. `Top failure modes if this is implemented naively`

Do not give a generic tools-comparison answer.
Judge whether this can actually be implemented safely in the current codebase.
