# OpenClawBot Workspace Material Ops Contract v1

## Purpose

Freeze the second execution lane for the Feishu `OpenClawBot` work ingress.

The existing `feishu-intake -> openmind_advisor_ask` lane already covers:

- work planning
- report/research-style structuring
- task closure through ChatgptREST `/v3/agent/turn`

This contract adds the missing lane for local work-material operations so the same Feishu bot can safely handle asks such as:

- check whether local planning files exist
- inspect workbook sheet names
- preview simple local text/tabular materials
- move files inside the planning workspace under controlled rules

## Live Route

- live OpenClaw state dir: `/home/yuanhaizhou/.home-codex-official/.openclaw`
- live config: `/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json`
- live binding:
  - `channel=feishu`
  - `accountId=default`
  - `agentId=feishu-intake`

## Intake Agent Tool Contract

- agent id: `feishu-intake`
- tool profile: `minimal`
- `alsoAllow` must contain:
  - `openmind_advisor_ask`
  - `openmind_work_material_ops`

The agent is work-only and now exposes two first-class lanes:

1. `openmind_advisor_ask`
   - for planning / research / report style work cognition
2. `openmind_work_material_ops`
   - for local file inspection / controlled move operations

## Required Behavior

When a Feishu work ask requests local-material execution, the intake lane must prefer `openmind_work_material_ops` over free-form commentary.

Covered intent includes:

- local path existence checks
- xlsx/xlsm/xltx sheet-name inspection
- sibling-material listing
- directory entry listing
- controlled move operations under the planning root

The intake lane must not fall back to telling the user that `exec` is unavailable for these supported operations.

## Allowlist Boundary

Read roots:

- `/vol1/1000/projects/planning`
- `/vol1/1000/projects/ChatgptREST`

Write roots:

- `/vol1/1000/projects/planning`

Move operations must remain allowlisted and default to safe posture:

- `dryRun=true` unless explicitly disabled
- destination must remain under allowlisted write roots

## Evidence Required

The lane is not considered ready without all of:

1. `feishu-intake` live config exposes `openmind_work_material_ops`
2. managed workspace guidance explicitly tells the agent to use `openmind_work_material_ops` first for local material asks
3. a live validation transcript shows `openmind_work_material_ops` being called on a real workbook-inspection ask
4. the tool result returns workbook sheet names from real xlsx files
5. the validation session is archived and the live `feishu-intake` session store is reset before formal usage

## Explicit Non-Goals

This contract does not claim:

- arbitrary shell / exec access from Feishu
- unrestricted filesystem browsing
- OCR-first document understanding for every attachment
- non-work domains
- a separate third bot

## Operator Message

After this contract, the supported operator statement is:

- `OpenClawBot` Feishu ingress can be used for work planning asks and for local planning-material inspection under the allowlisted workspace roots.
