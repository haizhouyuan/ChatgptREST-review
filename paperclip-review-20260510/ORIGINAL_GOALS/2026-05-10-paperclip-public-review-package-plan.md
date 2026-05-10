# Paperclip Public Review Package Plan

Date: 2026-05-10
Owner: Codex / codex2 execution handoff
Source repo: `/vol1/1000/projects/toyresearch`
Purpose: prepare a public GitHub review package for ChatGPT Pro / external model review.

## Goal

Create a sanitized, reviewable GitHub repository snapshot that lets a reviewer answer one core question:

> Given the user's original goal for Paperclip as a company/agent operating system, what has actually been built, where did the work drift, what is useful, what is still missing, and what should the next architecture and execution plan be?

This is not a source dump. It is a curated review packet with enough code, docs, evidence, and final artifacts to support critical review.

## Non-goals

- Do not publish secrets, API keys, credentials, private browser/session files, provider env files, or local auth artifacts.
- Do not publish large caches, `.venv`, `.pytest_cache`, `__pycache__`, screenshots, raw crawl dumps, or unrelated Labebe assets unless specifically summarized.
- Do not claim investment readiness or autonomy completion in the package.
- Do not rewrite history or clean the source worktree destructively.
- Do not include MiniMax / DeepSeek / Tavily / Brave credentials or recovery materials.

## Review Repo Layout

Recommended target layout inside the public review repo:

```text
paperclip-review-20260510/
  README.md
  REVIEW_PROMPT.md
  REVIEW_SCOPE.md
  MANIFEST.tsv
  CURRENT_STATE/
  ORIGINAL_GOALS/
  CODE/
  EVIDENCE/
  FINBOT/
  PLANNING/
  GOVERNANCE_MEMORY_SKILL_RUNTIME/
  PRO_ANSWERS/
  VALIDATORS/
  EXCLUDED_PRIVATE_MATERIALS.md
```

## Must Include

### 1. Review entry files

Create these files manually in the package:

- `README.md`: concise orientation, no hype.
- `REVIEW_PROMPT.md`: exact prompt to Pro.
- `REVIEW_SCOPE.md`: what is included/excluded, public-safety boundaries.
- `MANIFEST.tsv`: every included file with source path, destination path, reason, sha256, size.
- `EXCLUDED_PRIVATE_MATERIALS.md`: explain categories excluded for privacy/security and why.

### 2. Original goals and planning baseline

Include:

- `/vol1/1000/projects/toyresearch/docs/2026-05-06_paperclip_learning_research_company_requirements.md`
- `/vol1/1000/projects/toyresearch/docs/2026-05-06_paperclip_mvp_execution_plan.md`
- `/vol1/1000/projects/toyresearch/docs/superpowers/plans/2026-05-07-finbot-supervised-research-ops-master-plan.md`
- `/vol1/1000/projects/toyresearch/docs/superpowers/plans/2026-05-09-finbot-engineering-capability-platform-v1-plan.md`
- `/vol1/1000/projects/toyresearch/docs/superpowers/plans/2026-05-09-paperclip-repeatable-ops-8h-monitor-plan.md`
- `/vol1/1000/projects/toyresearch/docs/superpowers/plans/2026-05-10-paperclip-full-company-overnight-ops-goal.md`

If any file is missing, record it in `MANIFEST.tsv` as missing rather than inventing a replacement.

### 3. Current state and truth artifacts

Include latest current state:

- `/vol1/1000/projects/toyresearch/docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery/current_truth.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery/current_truth.json`
- `/vol1/1000/projects/toyresearch/docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery/blocker_board.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery/blocker_board.json`
- `/vol1/1000/projects/toyresearch/docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery/company_execution_matrix.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery/company_execution_matrix.json`
- `/vol1/1000/projects/toyresearch/docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery/22_closeout.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery/20_final_validation.json`
- `/vol1/1000/projects/toyresearch/docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery/15_live_paperclip_readback.json`

Include older correction context only if clearly marked as historical:

- `/vol1/1000/projects/toyresearch/docs/paperclip_correction_audits/2026-05-08_round5_11_real_agent_loop_correction/round5_11_real_agent_loop_correction_audit.md`
- `/vol1/1000/projects/toyresearch/docs/paperclip_correction_audits/2026-05-08_round5_11_real_agent_loop_correction/goal_completion_audit_20260508.md`

### 4. Core code required to understand the system

Include source code, tests, validators, and scripts, but not virtualenvs/caches:

- `/vol1/1000/projects/toyresearch/AGENTS.md`
- `/vol1/1000/projects/toyresearch/README.md`
- `/vol1/1000/projects/toyresearch/pyproject.toml`
- `/vol1/1000/projects/toyresearch/paperclip_company_os/AGENTS.md`
- `/vol1/1000/projects/toyresearch/paperclip_company_os/*.py`
- `/vol1/1000/projects/toyresearch/paperclip_company_os/tests/`
- `/vol1/1000/projects/toyresearch/scripts/validate_finbot_open_alpha_discovery_20260510.py`
- `/vol1/1000/projects/toyresearch/scripts/finbot_open_alpha_live_issue_runner_20260510.py`
- `/vol1/1000/projects/toyresearch/tools/validate_finbot_capability_platform.py`
- `/vol1/1000/projects/toyresearch/tests/test_finbot_capability_platform.py`
- `/vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company/AGENTS.md`
- `/vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company/README.md`

Optional but useful if not too large:

- `/vol1/1000/projects/toyresearch/runtime_allocator/README.md`
- selected runtime allocator files only if the review asks about runtime complexity drift.

### 5. Finbot evidence and output quality

Include these from latest run:

- `00_goal_contract.md`
- `01_history_asset_coverage.md`
- `03_source_alpha_map.md`
- `04_theme_map.md`
- `05_opportunity_board.md`
- `06_top_surprising_opportunities.md`
- `07_alpha_qualified_casebook.md`
- `08_full_decision_memo_pack.md`
- `09_evidence_claim_ledger.md`
- `10_valuation_range_pack.md`
- `11_risk_reversal_qa_pack.md`
- `12_human_review_queue.md`
- `13_next_7_day_research_campaign.md`
- `16_cycle_by_cycle_substantive_delta_audit.md`
- `final_evidence_manifest.json`
- `runtime_summary.json`
- `global_ops_runtime_summary.json`
- `anti_idle_audit.jsonl`
- `work_stealing_audit.jsonl`
- `cycle_ledger.jsonl`

Also include Finbot evolution history:

- `/vol1/1000/projects/toyresearch/docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp/02_pro_answer_digest.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp/03_historical_research_synthesis.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp/05_finbot_research_os_architecture.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp/22_critical_review_of_4d7321748.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp/30_semantic_reconciliation_digest.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp/66_alpha_quality_gate_spec.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp/69_alpha_quality_casebook.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp/79_alpha_final_validator_result.json`

### 6. Finbot Engineering / capability platform

Include:

- `/vol1/1000/projects/toyresearch/docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/00_execution_contract.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/01_current_state_audit.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/02_data_source_readiness_matrix.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/03_governed_connector_smoke_protocol.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/04_skill_contracts_for_finbot_agents.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/08_valuation_range_research_prototype.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/10_decision_memo_prototype.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/14_final_validation.json`
- `/vol1/1000/projects/toyresearch/docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/15_closeout.md`

### 7. Planning / Governance / Memory / Skill-MCP / Runtime / Learning / Local LLM / Labebe packets

Include latest company packet files from the 8h run:

- `Planning_overnight_closeout.md`
- `Governance_correction_packet.md`
- `Memory_research_and_replay_packet.md`
- `Skill_MCP_readiness_matrix.md`
- `Runtime_fallback_matrix.md`
- `Learning_Research_roadmap.md`
- `Local_LLM_research_only_packet.md`
- `Labebe_transformation_packet.md`
- `company_by_company_closeout.md`
- `company_by_company_closeout.json`

Include baseline docs:

- `/vol1/1000/projects/toyresearch/docs/PAPERCLIP_RUNTIME_INVENTORY_20260506.md`
- `/vol1/1000/projects/toyresearch/docs/PAPERCLIP_SKILLS_MCP_RUNTIME_RECONCILED_20260506.md`
- `/vol1/1000/projects/toyresearch/docs/LOCAL_MODEL_HANDOVER_20260506.md`

### 8. Maint docs supplied by user

Copy only these public-safe docs:

- `/vol1/maint/docs/个人投研助理方法.md`
- `/vol1/maint/docs/投研助理插件推荐.md`
- `/vol1/maint/docs/agent - 记忆系统评审与优化 1.md`
- `/vol1/maint/docs/agent - 五类agent能力评审.md`

Before publishing, scan for private names, accounts, credentials, phone numbers, emails, tokens, cookie/session text, and sensitive local paths. If sensitive, redact into `REDACTED_*` placeholders and note in `EXCLUDED_PRIVATE_MATERIALS.md`.

### 9. Pro answers

Include Pro answers that are directly relevant:

- `/vol1/1000/projects/toyresearch/docs/pro_review_packets/paperclip_production_master_pro_answer_20260507.md`
- `/vol1/1000/projects/toyresearch/docs/pro_review_packets/paperclip_production_master_v2_pro_answer_20260507.md`
- `/vol1/1000/projects/toyresearch/docs/pro_review_packets/paperclip_production_unblock_hard_review_pro_answer_20260507.md`

Do not include large zip packets unless needed; include text answers and manifests instead.

## Exclude

Exclude all:

- `.git/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `node_modules/`
- `MAIN/secrets/`, `.env`, credentials, tokens, keys, auth/session files
- provider key rotation recovery packs with sensitive operational details
- raw browser profiles, cookies, screenshots unless sanitized
- large SEC cache files unless summarized by ledger and manifest
- raw crawl dumps, Amazon review raw CSV/JSONL, unrelated product images
- unrelated Labebe demo source if the review target is Paperclip architecture rather than ecommerce implementation
- personal/private notes not needed to understand Paperclip.

## Sanitization Requirements

Run at minimum:

```bash
cd /path/to/review/package
rg -n --hidden -S "api[_-]?key|secret|token|authorization|bearer|cookie|session|password|BEGIN (RSA|OPENSSH|PRIVATE)|sk-[A-Za-z0-9]|AKIA|xox[baprs]-|TAVILY|BRAVE|DEEPSEEK|MINIMAX" .
find . -type f -size +5M -print
```

Any hit must be reviewed. Redact or exclude. Record exclusions.

## Packaging Commands Template

Codex2 should create a fresh package directory, copy curated files with path preservation, generate manifest, then commit to the public review repo.

```bash
set -euo pipefail

SRC=/vol1/1000/projects/toyresearch
MAINT=/vol1/maint
PKG=/tmp/paperclip-review-20260510
REVIEW_REPO=/path/to/public/review/repo

rm -rf "$PKG"
mkdir -p "$PKG"

# Build by explicit copy list, not broad rsync of the whole repo.
# Use install -D -m 0644 "$src" "$PKG/$dest" for every file.

# After copy:
cd "$PKG"
find . -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
find . -type f -printf '%p\t%s\n' | sort > FILE_SIZES.tsv
rg -n --hidden -S "api[_-]?key|secret|token|authorization|bearer|cookie|session|password|BEGIN (RSA|OPENSSH|PRIVATE)|sk-[A-Za-z0-9]|AKIA|xox[baprs]-|TAVILY|BRAVE|DEEPSEEK|MINIMAX" . > SECRET_SCAN.txt || true

# SECRET_SCAN.txt must contain no real secret values before publish.

mkdir -p "$REVIEW_REPO/paperclip-review-20260510"
rsync -a --delete "$PKG/" "$REVIEW_REPO/paperclip-review-20260510/"
cd "$REVIEW_REPO"
git status --short
git add paperclip-review-20260510
git commit -m "paperclip: add public review package 20260510"
git push
```

## Pro Review Prompt

Put this exact prompt in `REVIEW_PROMPT.md`:

```text
You are reviewing a public GitHub review package for Paperclip, an experimental company/agent operating system.

The user's original intent was not merely to accumulate docs or pass validators. The intent was to build a practical Paperclip operating system where:
- Governance owns company governance, Skill/MCP governance, and memory governance.
- Planning Work Assistant becomes the user's high-frequency work assistant with strategy, HR, and meeting/audio workflows.
- Finbot becomes a supervised personal investment research assistant that can continuously discover high-quality opportunities, but does not give investment advice, targets, trading signals, broker actions, or automatic trading.
- Learning Research studies memory systems, local models, runtime capability, Skill/MCP options, and feeds improved capabilities back into the companies.
- Labebe AI Transformation remains a toy-company AI transformation workstream.
- Codex/controller should orchestrate, validate, and correct drift; company agents should produce their own evidence, closeouts, memory deltas, and status sync.

Please perform a critical architecture and product review. Do not assume that a PASS validator means the product goal is achieved. Use the included code, current truth files, evidence, validators, Finbot outputs, company packets, Pro answers, and original goal docs.

Please answer these open questions:

1. What was the user's original need, stated in product/operating-system terms rather than implementation terms?
2. What has actually been built now? Separate working assets, partial prototypes, local/controller artifacts, and real live company-agent evidence.
3. Where did the work drift from the original goal? Identify over-engineering, false completion, weak validators, role confusion, or artifact production that does not improve the user's real outcome.
4. Does the current Paperclip architecture make sense? Should Controller & Runtime remain separate, or should runtime/fallback/Skill-MCP/memory governance be consolidated under Governance? Recommend a simpler target organization.
5. Is the current Finbot useful? Evaluate output quality, data/source readiness, alpha quality, evidence quality, valuation range quality, and whether the current output could responsibly influence investment research. Do not provide investment advice.
6. What are the highest-leverage next steps? Give a concrete rebuild-or-refocus plan, not small patch suggestions. Prefer a pragmatic MVP path that produces real user value quickly.
7. What should be stopped or deprecated?
8. What should be kept as valuable foundation?
9. What exact acceptance tests would prove the next version is genuinely useful rather than just internally validated?

Please be blunt and constructive. If evidence is insufficient, say so explicitly. If an artifact looks synthetic, templated, or semantically weak, call it out. The desired output is a strategic correction plan and a practical next execution roadmap.
```

## ChatGPT Pro Consultation Loop

After the public review package is committed and pushed, Codex2 must run the Pro consultation and consume the answer. The package is not complete merely because the GitHub repo exists.

Use the ChatgptREST `chatgptrest-call` skill / public advisor-agent MCP path by default. Do not use deprecated bare ChatgptREST tool names in task specs. If using the wrapper directly, call:

```bash
/usr/bin/python3 /vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --question "$(cat REVIEW_PROMPT.md)" \
  --goal-hint "paperclip-public-review" \
  --execution-profile thinking_heavy \
  --out-summary "$PKG/chatgpt_pro_review_summary.json"
```

Preferred inputs to Pro:

- Public GitHub repo URL for the review package, once pushed.
- The exact `REVIEW_PROMPT.md` content above.
- If the advisor-agent supports attachments, attach the local package root or the key manifest files.
- If GitHub push is blocked, attach the local package path and state that public URL is pending.

Required outputs:

- `PRO_CONSULTATION_REQUEST.md`: final prompt sent to Pro, including repo URL or package path.
- `chatgpt_pro_review_summary.json`: machine-readable submission/wait/result summary.
- `PRO_ANSWER.md`: full answer, not a truncated chat summary.
- `PRO_ANSWER_DIGEST.md`: Codex2's structured digest of Pro's answer.
- `CODEX2_INDEPENDENT_ASSESSMENT.md`: Codex2's own assessment, explicitly separating agreement/disagreement with Pro.
- `NEXT_EXECUTION_PLAN.md`: concrete, implementable next-stage plan based on the package evidence plus Pro answer.
- `NEXT_EXECUTION_QUEUE.tsv`: ordered task queue with owner company/agent, objective, inputs, output path, validator, acceptance criteria, and stop condition.

If ChatGPT Pro returns a background/deferred session, Codex2 must wait for the answer using the supported advisor-agent wait/status path. It must not stop after submission unless there is a real external blocker. If the answer is incomplete, too generic, or only says it cannot access the repo, Codex2 must perform one same-session repair/follow-up with the repo URL, manifest summary, and request for concrete review.

## Post-Pro Analysis Requirements

Codex2 must produce a decision-grade analysis, not just paste Pro's answer:

1. Reconstruct the original user goal in plain product terms.
2. Compare current Paperclip state against that goal.
3. Identify which assets are genuinely useful foundation.
4. Identify which assets are false-positive, over-engineered, redundant, or should be deprecated.
5. Make a clear recommendation on company architecture, especially whether Controller & Runtime should remain separate or be folded into Governance as runtime/fallback/skill/memory governance agents.
6. Evaluate Finbot as a supervised research system: source quality, data readiness, alpha quality, valuation/range quality, risk QA, and whether output is fit only for research ideation or can support supervised decisions.
7. Give a next execution plan that is not small patchwork. It must say what to build next, what to stop, and what acceptance tests prove real usefulness.

The final plan should be realistic about the current state:

- Paperclip is not fully autonomous yet.
- Finbot is not allowed to provide investment advice, trade signals, target-price recommendations, broker actions, or automatic trading.
- Quarantined providers remain no-production-use unless separately authorized.
- Connector enablement must be evidence-gated.

## Codex2 Acceptance Criteria

Codex2 is done only when:

- Public review package exists in the selected review repo.
- `README.md`, `REVIEW_PROMPT.md`, `REVIEW_SCOPE.md`, `MANIFEST.tsv`, `SHA256SUMS`, `SECRET_SCAN.txt`, and `EXCLUDED_PRIVATE_MATERIALS.md` exist.
- Secret scan is reviewed and contains no publishable secrets.
- Package includes original goals, current truth, latest 8h run evidence, validators, core code, Finbot history, Finbot Engineering capability platform, company packets, maint docs, and relevant Pro answers.
- Package intentionally excludes caches, credentials, large raw dumps, private session/auth files, and unrelated artifacts.
- Commit and push are complete, or if push is blocked by auth/remote, a local commit and exact blocker are recorded.
- ChatGPT Pro has been asked through ChatgptREST public advisor-agent path, or a precise transport blocker is recorded.
- `PRO_ANSWER.md`, `PRO_ANSWER_DIGEST.md`, `CODEX2_INDEPENDENT_ASSESSMENT.md`, `NEXT_EXECUTION_PLAN.md`, and `NEXT_EXECUTION_QUEUE.tsv` exist.
- Codex2 has analyzed the Pro answer and current evidence before writing the next execution plan.
- The next execution plan is specific enough for another agent to execute without rereading this chat.
