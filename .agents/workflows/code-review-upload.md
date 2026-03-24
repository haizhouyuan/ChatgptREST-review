---
description: How to pack and upload codebase code for AI code review (Gemini, ChatGPT)
---

# Code Review Upload Workflow

## Quick Reference

| Target | Command | Output |
|--------|---------|--------|
| Gemini (10 files) | `python ops/code_review_pack.py --mode gemini` | 10 `.md` files |
| ChatGPT (zip) | `python ops/code_review_pack.py --mode chatgpt` | 1 `.zip` file |
| PR only | `python ops/code_review_pack.py --mode pr --base master` | ≤10 changed files |
| **Review branch** | `python ops/sync_review_repo.py --sync --push` | branch in public repo |
| Finalize reviewed bundle | `python ops/sync_review_repo.py --finalize` | auto-resolve current review branch, delete it, clear stable import branch |
| TTL cleanup | `python ops/sync_review_repo.py --cleanup` | stale remote branches deleted |
| Purge all review code | `python ops/sync_review_repo.py --purge-all` | delete all remote review branches + clear stable import branch |

## Platform Limits

### Gemini Consumer App
- **10 files per prompt** (hard limit)
- Each file ≤100MB
- Code folder / GitHub repo import: **≤5000 files, ≤100MB total**
- Context window: 1M tokens
- If you need **Gemini DeepThink / GeminiDT**, treat it as a **web capability**, not a Gemini CLI/API-key capability.

### ChatGPT
- Zip with many files supported
- GitHub connector: Plus/Pro/Team plans
- **Pro model cannot read private repos** — use public mirror
- Context window: 128K tokens

## Workflows

### 1. Full Codebase Review via Gemini

```bash
# Generate 10 concatenated markdown files
// turbo
python ops/code_review_pack.py --mode gemini --output-dir /tmp/review_gemini

# Upload all 10 files to Gemini in a single prompt
# Then ask your review question
```

Important:

- This section is about the Gemini consumer app / web path.
- Do not reinterpret `GeminiDT / DeepThink` review as `gemini cli -p`.
- For coding-agent mediated DeepThink reviews, the valid automated lane is `gemini_web.ask`, not Gemini CLI.

### 2. Full Codebase Review via ChatGPT

```bash
# Generate zip file
// turbo
python ops/code_review_pack.py --mode chatgpt --output-dir /tmp/review_chatgpt

# Upload the zip file to ChatGPT
# For ChatGPT Pro with public repo connector:
python ops/sync_review_repo.py --sync --push
# Then paste the repo URL in the ChatGPT prompt
```

### 3. PR Review

```bash
# Pack only changed files for targeted review
// turbo
python ops/code_review_pack.py --mode pr --base master --output-dir /tmp/review_pr

# Upload the generated files (≤10) to Gemini or ChatGPT
```

### 4. Branch-Based Review via Public Repo (Recommended)

The most efficient approach — both ChatGPT Pro and Gemini can read the same public repo.

```bash
# First time: create the public repo
python ops/sync_review_repo.py --create --repo-name ChatgptREST-review

# Push code for review (creates review-YYYYMMDD-HHMMSS branch)
// turbo
python ops/sync_review_repo.py --sync --push

# With PR context:
python ops/sync_review_repo.py --sync --push \
    --pr-branch feat/my-feature \
    --review-instructions "Review the new feature"

# Custom branch name:
python ops/sync_review_repo.py --sync --push --branch-name my-review

# After the answer is generated: finalize this review bundle immediately
# If REVIEW_SOURCE.json is present, branch name no longer needs to be typed manually
python ops/sync_review_repo.py --finalize

# Optional TTL cleanup for any stale leftover branches
python ops/sync_review_repo.py --cleanup --max-age-hours 24 --clear-import-when-empty

# Emergency: clear the public review repo completely
python ops/sync_review_repo.py --purge-all
```

Output: 574 files, 7.6MB (within Gemini limits).

## Review Channel Policy

When choosing the execution channel, keep these rules hard:

- `ChatGPT Pro review`: standard public-review-repo / upload workflow is fine.
- `Gemini DeepThink / GeminiDT review`: web-automation-only.
- `Gemini CLI` is not the substitute for `GeminiDT`.
- `OAuth/API key` issues should not be treated as the root cause of a `GeminiDT` routing failure when the real problem is that the task was not sent to `gemini_web.ask`.

For coding agents:

- if the requested review lane is `GeminiDT / DeepThink`
- and the current executor is not `gemini_web.ask` (or a higher-level surface that compiles to it)
- then fail fast instead of silently downgrading to Gemini CLI

`--finalize` is the preferred lifecycle closeout because it clears the stable
import branch to a placeholder-only commit, so the public review repo no longer
retains mirrored source code after the answer has been collected.

### 5. ChatGPT GitHub Connector Activation

The driver now **automatically handles repo indexing activation**:

- When `github_repo` is specified and the repo is **greyed out** (not indexed), the driver:
  1. Clicks the repo to trigger indexing
  2. Closes the indexing modal
  3. Polls every 60s for up to 20min (configurable via `CHATGPT_GITHUB_INDEX_WAIT_SECONDS`)
  4. Re-opens the picker and retries until the repo becomes active
  5. Selects the repo (checkmark)

```bash
# Coding agents should prefer the wrapper or public REST, not legacy MCP bare names:
/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --provider chatgpt \
  --preset pro_extended \
  --idempotency-key code-review-001 \
  --github-repo haizhouyuan/ChatgptREST \
  --question "Review the codebase and identify the highest-risk regressions."
```

See `docs/2026-03-18_coding_agent_mcp_surface_policy_v1.md` for the coding-agent MCP surface rule.

> **Note**: Only **public repos** work for ChatGPT Pro's file content reading.
> Use `ops/sync_review_repo.py` to create a public mirror for private repos.

## Tips

- **Gemini code import** (code folder button): Upload a folder directly
  from your machine. This counts as 1 "code folder" and must be ≤5000
  files, ≤100MB. Good for full codebase review.
- **Always verify uploads**: Check that all file chips/badges appear
  in the chat input before sending. Re-upload if any are missing.
- **PR reviews are most effective**: For targeted code review, use
  `--mode pr` to pack only changed files with diff context.
- **Include review instructions**: Use `--review-context` flag to
  embed specific review criteria in the pack.
