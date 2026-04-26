---
name: runtime-duel-operator
description: Operate the Paperclip runtime duel demo with strict issue hygiene, durable artifact output, and evidence-safe closeout.
---

# Runtime Duel Operator

Use this skill when executing the Claude Code vs Kimi runtime comparison.

Rules:

- Work only on the assigned Paperclip issue for the current heartbeat.
- Read the shared target brief and rubric before drafting.
- Save the final artifact to the lane-specific output path.
- Add a concise Paperclip issue comment with the artifact path, self-score, and any blockers.
- Move the assigned issue to `done` only when the artifact is complete and non-empty.
- If any source is missing, label the gap and continue with the available local evidence.
- Do not expose secrets, raw tokens, or private keys.
- Do not claim internet browsing or external validation.

Required local files:

- `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/brief/shared_target_brief.md`
- `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/brief/rubric_100.yaml`

Closeout comment must include:

- `Artifact:` absolute path
- `Self-score:` numeric score out of 100
- `Evidence:` short list of local files used
- `Residual risk:` one sentence
