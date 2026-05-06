# 2026-04-03 Gemini Wait Thread Reopen Walkthrough v2

## What I Changed

1. tightened compact normalization so it only trusts runtime scenario-pack data
2. added a consult regression test that exercises the real consult path without clarify-gate false negatives
3. tightened Gemini wait tests to pin the exact current recovery envelope

## Why

The prior redteam review downgraded from `reject` to `approve-with-fixes` and identified two remaining tightening opportunities:

1. compact normalization still trusted caller-provided context too much
2. wait-budget tests were too loose and could allow silent widening later

This batch closes both without broadening product scope.

## Validation

1. py_compile on the four touched files passed
2. targeted `routes_agent_v3` compact/consult pytest selection passed
3. targeted Gemini wait/sidebar/url/hint pytest selection passed
4. Codex 5.4-xhigh redteam follow-up returned `approve`
