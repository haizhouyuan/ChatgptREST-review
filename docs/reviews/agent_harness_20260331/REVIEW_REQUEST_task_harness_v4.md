# External Review Request A — Task Harness / Agent Harness v4

Review target:

- `2026-03-31_Agent_Harness工程调研_最终综合结论_v4.md`
- `CODE_CONTEXT_MAP.md`
- `source_pack/*`
- current code files listed in `CODE_CONTEXT_MAP.md`

Question:

Given the current ChatgptREST implementation, is `v4` the right high-standard architecture for upgrading the system from “good memory + job contracts” into a true long-running task harness?

Please answer at implementation depth, not product-vision depth.

## What to evaluate

1. Which parts of `v4` are genuinely strong and should be kept.
2. Which parts are structurally wrong, too abstract, or not grounded in the current codebase.
3. Which missing pieces would cause this proposal to fail even if implemented faithfully.
4. Whether the proposed control chain is correct:
   - task intake
   - frozen task context
   - task spec
   - execution plan
   - chunk contract
   - execution
   - evaluator report
   - promotion decision
   - final outcome
   - completion publication
   - durable memory distillation
5. Whether the boundary between:
   - task control
   - completion contract
   - canonical answer
   - work memory
   is correctly drawn.
6. What the best phase ordering should be if implementation starts now.
7. What must be implemented before this can be called production-grade.
8. What the acceptance criteria should be for a strict implementation.

## Required output format

Please structure the answer into:

1. `Verdict`
2. `What v4 gets right`
3. `What v4 gets wrong`
4. `Missing implementation-critical pieces`
5. `Recommended implementation sequence`
6. `Strict acceptance criteria`
7. `Top failure modes if implemented poorly`

Do not give a shallow “looks good” answer.
Assume the goal is a high-standard production-quality control plane.
