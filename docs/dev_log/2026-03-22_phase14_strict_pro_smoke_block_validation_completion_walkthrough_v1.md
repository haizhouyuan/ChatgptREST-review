# Phase 14 Strict Pro Smoke Block Validation Walkthrough v1

1. Hardened [prompt_policy.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/prompt_policy.py) so Pro smoke/trivial checks execute before generic ChatGPT live-smoke escape hatches.
2. Removed the practical effect of `allow_trivial_pro_prompt` and `allow_pro_smoke_test` for Pro presets.
3. Converted existing tests from "override succeeds" to "override still blocked".
4. Removed stale guidance from active docs and kept only the non-Pro `allow_live_chatgpt_smoke` exception.
5. Added a dedicated validation runner that checks both runtime policy and active-doc cleanliness.
