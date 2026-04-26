---
name: runtime-duel-rubric
description: Apply the 100-point boss-demo rubric for Claude Code vs Kimi same-goal output comparison.
---

# Runtime Duel Rubric

Score against `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/brief/rubric_100.yaml`.

Hard requirements:

- All required sections from the shared brief must exist.
- `Evidence Ledger` must contain at least five local evidence entries.
- `Final Self-Score` must include point-level reasoning.
- Any quantitative business, safety, certification, ROI, launch, or market claim must be labeled as `Hypothesis` unless explicitly present in the local sources.
- The answer must include a concrete visual/interaction direction, not just strategy prose.

When comparing two outputs, evaluate:

- understanding of Paperclip boundaries
- usefulness for a boss demo
- creativity and specificity
- governance discipline
- evidence traceability
- whether the artifact would make a strong first impression
