# Agent Harness External Review Packet Index

This review packet is for a dual external review of two related proposals:

1. `2026-03-31_Agent_Harness工程调研_最终综合结论_v4.md`
2. `2026-03-31_ChatgptREST_opencli_CLI-Anything_集成详细实施方案_v2.md`

Read in this order:

1. `00_INDEX.md`
2. `CODE_CONTEXT_MAP.md`
3. `REVIEW_REQUEST_task_harness_v4.md`
4. `REVIEW_REQUEST_opencli_cli_anything_v2.md`
5. `2026-03-31_Agent_Harness工程调研_最终综合结论_v4.md`
6. `2026-03-31_ChatgptREST_opencli_CLI-Anything_集成详细实施方案_v2.md`
7. `source_pack/source_registry.json`
8. `source_pack/*.md`

Purpose:

- get one deep review on the task-harness / long-running-agent architecture proposal
- get one deep review on the `opencli` / `CLI-Anything` integration proposal
- force both reviews to ground themselves in the actual current codebase instead of discussing generic ideas

Hard review expectations:

- identify what is correct
- identify what is structurally wrong
- identify missing implementation pieces
- identify phase ordering mistakes
- identify governance / safety / audit gaps
- give a concrete implementation sequence and acceptance bar

Do not treat these as marketing or high-level vision docs.
Treat them as implementation proposals that may contain hidden architectural mistakes.
