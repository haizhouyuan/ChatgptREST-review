# Pro Submission Log

Date: 2026-04-27

## Purpose

Ask ChatGPT Pro to critically review the Labebe product intelligence and website design prework plan before any further website implementation.

## Packet

Local packet:

- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_product_intel_and_design/pro_packet/labebe_product_intel_design_prework_pro_packet_20260427.zip`

Upload-copy path used by ChatGPTREST:

- `/tmp/chatgptrest_uploads/labebe_product_intel_design_prework_pro_packet_20260427.zip`

Prompt:

- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_product_intel_and_design/05_PRO_REVIEW_ASK.md`

## Submission Attempts

1. `v1`
   - Result: local runtime rejected.
   - Cause: `automation-kernel-v1` does not accept non-default `--depth`.
   - Fix: removed `--depth heavy`.

2. `v2`
   - Result: preflight blocked.
   - Cause: `provider_selection.reason` missing.
   - Fix: added top-level `reason` to `provider_selection.json`.

3. `v3`
   - Result: MCP 400.
   - Cause: attachment path was relative and resolved under the ChatGPTREST repo.
   - Fix: changed attachment path to absolute.

4. `v4`
   - Result: MCP 403.
   - Cause: absolute attachment path was outside ChatGPTREST allowed upload roots.
   - Fix: copied the zip to `/tmp/chatgptrest_uploads/`.

5. `v5`
   - Result: accepted.
   - Job id: `c33acc4b812e41cea92f4e317efad589`
   - Conversation URL: `https://chatgpt.com/c/69eef06f-4828-83e8-a318-286bd2b51b12`
   - Kind: `chatgpt_web.ask`
   - Provider: `chatgpt`
   - Preset: `pro_extended`
   - Status at receipt: `queued`
   - Watch id: `wait-1777266773-0013-c33acc4b`
   - Summary file: `pro_submit_summary.json`

## Operational Lessons

- ChatGPTREST Pro packet attachments must be absolute and under an allowed upload root.
- Provider selection JSON must include top-level `reason`.
- Do not pass non-default `--depth` to `automation-kernel-v1`.
- Treat the first successful response as a receipt, not as the final Pro answer.
