# Claude Code Kimi Effect Comparison

## Scope Correction

The requested comparison is **not** official Claude Code vs. Claude Code with Kimi.

The relevant lane is:

- **Claude Code Kimi:** Paperclip `claude_local` adapter with command `/home/yuanhaizhou/.local/bin/claudekimi`
- **Purpose:** use Claude Code compatibility UX/tooling while routing the model call through the local Kimi coding endpoint
- **Comparison target:** this new result compared with the previous same-task outputs already generated in this package

## Run Result

| Item | Result |
|------|--------|
| Paperclip agent | `Claude Code Kimi Content Lead` |
| Issue | `RUN-3` / `5521d6b7-b772-45b7-b247-904a20ad9e3a` |
| Final issue status | `done` |
| Successful run | `8cb4fcd5-944b-4976-868e-fdc28c74c23d` |
| Artifact | `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs/claude_kimi_code_demo.md` |
| Deterministic score | 100 / 100 |
| Corrected self-score | 97 / 100 |

First run failed because the Paperclip child process did not inherit `KIMI_CODINGPLAN_API_KEY`. I fixed this by creating a Paperclip encrypted `secret_ref` and binding it to the `claudekimi` agent env. The final issue closeout required an explicit operator closeout because `claude_local` writes the final assistant response as an issue comment but does not always transition the issue status to `done`.

## Runtime Truth

This lane has a metadata conflict that must be stated plainly:

| Evidence | Value | Interpretation |
|----------|-------|----------------|
| Agent adapter config | command `/home/yuanhaizhou/.local/bin/claudekimi` | Confirms the Claude Code compatibility wrapper route |
| Raw stream-json log | `model: kimi-for-coding` | Best evidence for actual upstream model in this wrapper lane |
| Paperclip aggregate `usageJson` | `claude-sonnet-4-6` / `provider: anthropic` | Wrapper/accounting metadata conflict; do not use as the upstream model claim |

Conclusion: the generated content should be evaluated as **Claude Code compatibility path backed by Kimi**, with the above caveat.

## Output Comparison

| Dimension | Previous Native Kimi (`kimi_demo.md`) | New Claude Code Kimi (`claude_kimi_code_demo.md`) |
|-----------|----------------------------------------|---------------------------------------------------|
| Length | 27,747 chars | 42,099 chars |
| Self-score | 97 / 100 | 97 / 100 after correction |
| Evidence density | 8 local path hits | 19 local path hits |
| Claim labels | 34 Fact / 6 Inference / 8 Hypothesis | 53 Fact / 10 Inference / 9 Hypothesis |
| Strength | Cleaner boss narrative and product taste | More complete control-plane synthesis and cross-lane analysis |
| Weakness | Less exhaustive evidence ledger | Initially over-trusted `usageJson`; needed correction |

## Judgment

The `claudekimi` route produced a **stronger board-pack artifact** than the previous native Kimi lane: richer structure, more evidence, more workflow detail, and better synthesis of the prior Claude/Kimi artifacts. It feels closer to a "complete package" than a single-lane answer.

But native Kimi was cleaner on taste and had less runtime-truth confusion. The new `claudekimi` lane behaved more like a tool-heavy coding agent: it used files, committed output, verified status, and generated a larger integrated report, but it also over-believed the Paperclip aggregate `usageJson` until corrected.

Practical takeaway: use `claudekimi` for the high-bar demo generation workflow, but keep strict guardrails:

- force raw stream-json vs aggregate `usageJson` distinction;
- require explicit Paperclip issue PATCH closeout;
- score after correction, not from the model's first self-score;
- keep native Kimi's product/visual taste as a reference when judging "wow".
