# 2026-03-23 Phase27 Premium Default Path Validation Walkthrough v1

## Why This Existed

The remaining blueprint DoD item was not another feature.
It was a regression guarantee:

- do not let the new public-agent control plane accidentally move normal premium asks into `cc-sessiond` / team-style execution paths

## Implementation

Added:

- [premium_default_path_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/premium_default_path_validation.py)
- [phase27_premium_default_path_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase27_premium_default_path_samples_v1.json)
- [run_premium_default_path_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_premium_default_path_validation.py)
- [test_premium_default_path_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_premium_default_path_validation.py)

The pack:

- rebuilds canonical `task_intake`
- applies `scenario_pack`
- normalizes `AskContract`
- builds strategist output
- runs `ControllerEngine.ask(...)` against a temp DB/artifacts sandbox
- asserts the resulting provider/preset/job-kind remain on the expected LLM default lane

## Notes

One sample worth noting:

- the current `code_review` sample still stays on the normal ChatGPT LLM lane
- but its selected route is `deep_research`, not `quick_ask`

That is not a failure for this pack, because the pack is only proving the default execution plane stayed LLM-backed and did not drift into team / execution-cabin paths.
