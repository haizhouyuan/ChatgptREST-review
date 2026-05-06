# OpenClawBot Workspace Material Ops Readiness Review v1

## Verdict

`OpenClawBot` is ready for formal work usage across two lanes under the same Feishu ingress:

- `openmind_advisor_ask` for planning-style work cognition
- `openmind_work_material_ops` for local planning-material operations

This closes the previously observed gap where the bot could structure work asks but failed when the user asked it to inspect local `xlsx` files or move materials.

## Root Cause

The earlier failure was real and reproducible:

- the intake lane received a work ask correctly
- it then tried to use `exec`
- the runtime returned `Tool exec not found`
- the assistant degraded into asking the user for screenshots

That was not a planning-lane failure. It was a missing execution lane for local work-material operations.

## What Changed

### Repo

- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
  - added host-side tool `openmind_work_material_ops`
  - supports `inspect` and `move`
  - supports workbook sheet-name extraction, sibling-material listing, directory listing, and guarded move operations
- [rebuild_openclaw_openmind_stack.py](/vol1/1000/projects/ChatgptREST/scripts/rebuild_openclaw_openmind_stack.py)
  - added `openmind_work_material_ops` to `feishu-intake`
  - updated managed workspace guidance so local material asks go to the new tool first
  - removed the incorrect sandbox-bind approach; the lane now uses a host-side plugin tool instead
- [README.md](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/README.md)
  - documented the new lane and its allowlist roots
- tests:
  - [test_rebuild_openclaw_openmind_stack.py](/vol1/1000/projects/ChatgptREST/tests/test_rebuild_openclaw_openmind_stack.py)
  - [test_openclaw_cognitive_plugins.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py)

### Live Runtime

- rebuilt live OpenClaw stack with:
  - `PYTHONPATH=. python3 scripts/rebuild_openclaw_openmind_stack.py --topology ops`
- restarted:
  - `openclaw-gateway.service`
- verified live config exposes:
  - `feishu/default -> feishu-intake`
  - `openmind_work_material_ops` in `feishu-intake.tools.alsoAllow`

## Evidence

### Real failure evidence before fix

- transcript entry:
  - `/home/yuanhaizhou/.home-codex-official/.openclaw/backups/feishu-intake-wmops-clean-20260410T1845/validation_session_8ba11bbf-e228-413f-9d0e-9a0271de4a35.jsonl`
- key proof:
  - `toolName:"exec" -> Tool exec not found`

### Real success evidence after fix

- same archived validation transcript contains:
  - assistant tool call:
    - `openmind_work_material_ops`
  - tool result:
    - all 4 files existed
    - workbook sheet names were returned
    - sibling materials were listed
- the live gateway log also captured the corrected reply posture:
  - `已查过，结果在上一条... 下一步直接读内容还是继续整理归档？`
  - no fallback request for screenshots

### Concrete workbook results from live validation

- `2025年度绩效考核表-袁海州1.xlsx`
  - `sheet_names = ["绩效考核表"]`
- `2025年度绩效考核表-袁海州2.xlsx`
  - `sheet_names = ["绩效考核表"]`
- `20260410171637394.xlsx`
  - `sheet_names = ["金固工作周报"]`
- `20260410175608127.xlsx`
  - `sheet_names = ["周报", "金固工作周报"]`

### Validation-session hygiene

- archived validation state:
  - `/home/yuanhaizhou/.home-codex-official/.openclaw/backups/feishu-intake-wmops-clean-20260410T1845`
- live session store after cleanup:
  - `/home/yuanhaizhou/.home-codex-official/.openclaw/agents/feishu-intake/sessions/sessions.json`
  - content reset to `{}` before gateway restart

## Scope Boundary

Ready now:

- local file existence checks in work asks
- workbook sheet-name inspection
- sibling-material discovery in planning root
- controlled move operations under planning root
- continued planning/report/research closure through `openmind_advisor_ask`

Not claimed:

- arbitrary shell access
- generic desktop automation from Feishu
- non-work domain support
- full spreadsheet semantic extraction from Feishu in one step

## Final Operator Posture

`OpenClawBot` can now be used as a single work-only Feishu entry for both:

- work reasoning
- local planning-material inspection / controlled organization

No extra bot is required for this gap.
