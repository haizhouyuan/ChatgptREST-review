# 2026-04-04 codex 5.4 xhigh redteam Gemini CDP new_page retry narrowing v1

## Review Record

Two codex 5.4 xhigh red-team reviews were launched for this batch.

### First review

The first red-team verdict rejected the broader implementation and identified a correct high-severity issue:

- the original retry had been wrapped around the whole `_open_over_cdp()` path, which still included navigation
- that made the retry broader than the intended `new_page()` bootstrap recovery

I accepted that critique and rewrote the batch accordingly.

### Second review

A follow-up codex 5.4 xhigh re-review was launched after narrowing the code and adding the missing regression tests.

At the time this document was frozen, the follow-up review had not returned a terminal verdict within the working window.

## My independent judgment

I did not treat the missing second verdict as approval.

Instead, I only kept the narrowed code after:

- constraining the retry site to explicit `BrowserContext.new_page/context.new_page` only
- making the local retry spend-once across the whole `_open_gemini_page()` call
- re-checking reuse-enabled Gemini tabs after the retry attach
- adding tests for:
  - local retry success without restart
  - local retry failure then restart once
  - retry budget spent only once across pre-restart and post-restart paths
  - generic `*.new_page` closed-target strings not taking the local retry
  - `goto`-side `TargetClosedError` not taking the local retry
- rerunning neighboring CDP/page-reuse/infra tests

## Status

- first red-team critique: `accepted`
- second red-team verdict: `pending / no terminal response in-window`
- code kept only after manual narrowing + expanded regression coverage
