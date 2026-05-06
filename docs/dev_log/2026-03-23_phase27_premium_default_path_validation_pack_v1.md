# 2026-03-23 Phase27 Premium Default Path Validation Pack v1

## Goal

Prove the last explicit blueprint DoD item:

- regression tests prove ordinary premium asks still stay on LLM default paths

This pack is intentionally scoped to the controller-backed premium ingress path.
It does not try to prove external provider completion.

## What It Validates

For covered ordinary premium asks, the system must still:

- stay on `job` execution, not `team`
- keep `objective_kind` on the normal delivery shapes (`answer` / `artifact_delivery`)
- submit a normal LLM job (`chatgpt_web.ask`)
- preserve the expected public default presets (`auto`, `thinking_heavy`, `deep_research`, `pro_extended`)

## Covered Cases

- business planning light memo
- workforce planning
- topic research
- research report
- code review
- explicit `thinking_heavy` research

## Non-Goals

- live provider completion proof
- heavy execution lane approval
- proving every route semantic is ideal

The pack is only about ensuring these asks still remain on LLM default lanes instead of drifting into the execution cabin.
