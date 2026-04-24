---
name: hermes-workbench
description: Hermes-native workbench sidecar for task state, handoff state, and executor context packets.
version: 1.0.0
author: Codex
platforms: [linux]
metadata:
  hermes:
    category: planning
    tags: [planning, workbench, taskboard, handoff, context]
    requires_toolsets: [terminal]
    gateway_direct_handler_script: scripts/direct_gateway_workbench.py
---

# Hermes Workbench

## Purpose

This skill is the first repo-managed foundation for the Hermes-native work surface.

It does **not** try to replace Codex or Claude Code as an execution engine.
It exists to let Hermes hold:

1. task state
2. handoff state
3. context packets for downstream executors

## Scope

This skill is responsible for:

1. initializing a local workbench state file
2. rendering a minimal task-board entry
3. generating a minimal handoff/context packet
4. applying executor results back into the local task state

This skill is **not** responsible for:

1. calling legacy `advisor_agent_turn` as a front-door
2. writing shared long-term memory directly
3. auto-spawning multiple subagents
4. replacing specialist executors

## Canonical assumptions

1. Hermes is the sole front-end work surface
2. ChatgptREST is a retained back-end asset source, not the front-end center
3. task-board data should align with `ActiveProjectObject + HandoffObject`
4. handoff packets should be concise, stable, and executor-agnostic

## Local assets

### Scripts

- `scripts/workbench_cli.py`
  - unified CLI for init, status, task upsert, handoff render, context render, automation submit, automation push record, automation reconcile, and result apply
- `scripts/openmind_contract.py`
  - protocol-aligned hot-path clients for `context/resolve`、`graph/query`、`memory/capture`

- `scripts/init_workbench_state.py`
  - initialize a repo-local Hermes workbench state file

- `scripts/render_taskboard_entry.py`
  - normalize one task-board entry from minimal CLI input

- `scripts/render_handoff_packet.py`
  - build a compact handoff packet for downstream execution

- `scripts/render_context_packet.py`
  - build a compact execution packet from task + latest handoff state

- `scripts/apply_executor_result.py`
  - merge one executor result back into the local task-board state

### Templates

- `templates/taskboard_entry_example.json`
- `templates/handoff_packet_example.json`
- `templates/context_packet_example.json`

## Expected operating model

1. Initialize workbench state once
2. Add or refresh a task-board entry before delegating work
3. Generate a handoff packet for the chosen executor
4. Generate a context packet for the chosen executor
5. If the task needs external Web automation, submit one canonical automation ask from workbench
6. When automation completes in the background, write the pushed completion back with `automation-record`
7. If旧任务因为历史版本遗留了 `phase=active` / `review_status=active`，用 `automation-reconcile` 做一次终态修复
8. 对明确标记为高复用的完成任务，可通过 task entry 的 `memory_capture` 配置启用 fail-closed 记忆写回，并限制 capture 文本上限
9. After execution, update the task-board entry and handoff trail
8. In Feishu DM, query current state with plain text like `工作台状态`

### Recommended CLI entrypoint

Prefer the unified wrapper:

```bash
python hermes-skills/hermes-workbench/scripts/workbench_cli.py --help
```

instead of wiring each helper script separately.

For external model/web automation from the Hermes front surface, use:

```bash
python hermes-skills/hermes-workbench/scripts/workbench_cli.py automation-submit ...
```

This path submits:

- question
- attachment list
- client-side preflight checklist
- provider-selection rationale
- scoped shared cognition
- optional OpenMind graph/context hot-path enrichments

to the canonical `ChatgptREST` automation-only wrapper, then writes the returned receipt back into repo-local workbench state.


## Deep-interview fallback guidance

When a Feishu DM task is not handled locally by the gateway sidecar and therefore reaches the main Hermes agent, apply the following rules for **deep-interview / long-form strategy / historical-material retrieval** requests:

1. **Do not start with whole-home search.** Before any `/home`、`/mnt/data`、`/vol1` broad search, first inspect these planning business directories in order:
   - `/vol1/1000/projects/planning/两轮车车身业务/`
   - `/vol1/1000/projects/planning/业务PPT/`
   - `/vol1/1000/projects/planning/十五五规划/`
   - `/vol1/1000/projects/planning/机器人代工业务规划/`
   - `/vol1/1000/projects/planning/预算/`

2. **Prefer business-final materials over process or runtime notes.** Do not treat Hermes investigation notes, runtime diagnostics, or workbench tracking docs as the target business document unless the user is explicitly asking about Hermes itself.

3. **Use a hard early stopping rule.** Once you have 1-3 plausible candidate materials, stop broad searching and move to output. Do not keep searching just because the exact filename is not yet certain.

4. **Question-list output beats exhaustive search.** For deep-interview tasks, if the exact final material cannot be confirmed quickly, output:
   - the best candidate materials found so far
   - the key missing evidence
   - a first-pass deep-interview question list

5. **Missing-source fallback is allowed.** If no strong candidate appears after the preferred directories are checked, explicitly state the missing source and still produce a usable question list draft instead of continuing unlimited search.


## Recording deep-research fallback guidance

When a Feishu DM task is about a call recording, transcript, or archived deep-research package, apply these rules after the task reaches the main Hermes agent:

1. **First decide whether this is a new audio object or a second-pass analysis of an existing archive.** If the archive already contains:
   - audio input
   - cleaned transcript
   - deep research report
   then treat the task as **second-pass synthesis**, not a brand-new ingestion run.

2. **Prefer the archive project root before broader search.** Check in this order:
   - `/vol1/1000/projects/planning/archives/projects/`
   - then related `docs/` tracking reports
   - only after that expand to broader directories.

3. **Use a hard output-first stopping rule.** As soon as you confirm these three ingredients exist for the same archive project:
   - audio file
   - cleaned transcript
   - deep research or补证 report
   stop broad searching and write the answer. Do not continue searching just to make the archive “more complete.”

4. **Default output skeleton for recording deep-research tasks:**
   - 一句话结论
   - 当前最稳判断
   - 三个最重要未决点
   - 下一步补证建议

5. **Second-pass synthesis is a valid completion.** If no newer audio exists and the archive package already covers the core material, you may answer by reorganizing the existing findings into a clearer decision-ready synthesis. Do not insist on discovering new facts before you respond.

6. **Archive-rich means answer-now.** If you already have transcript + final report + unresolved-gaps report, the default action is to synthesize and answer, not to keep reading every file in the archive.

7. **Do not block on proving a newer Drive file exists.** If the request mentions Google Drive but the local archive already contains audio + transcript + report, and you cannot immediately prove a newer file exists, assume the user is asking for a second-pass synthesis of the existing archive and answer from that archive. Do not stop only to ask whether Drive is connected.

8. **For recording tasks, prefer a decision-ready answer over an environment question.** Only ask about Drive connectivity when the user explicitly asks you to fetch a new file or when no usable local archive package exists.

## Notes

This is a foundation skill.
It is intentionally narrow and is safe to use as a gateway-side sidecar before the main Hermes agent turn.
