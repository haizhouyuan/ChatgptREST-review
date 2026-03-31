# Phase 3 Planning Scenario Pack Completion Walkthrough v2

## Why v2 exists

`v1` completed the main integration, but review surfaced four quality-policy gaps:

1. summary-style planning asks could skip clarify
2. business planning had no light branch
3. short Chinese meeting-summary phrases were under-covered
4. `watch_policy` / `funnel_profile` were mostly declarative

## Implementation path

### Scenario pack policy

- expanded meeting-summary keyword coverage
- added a lightweight business-planning branch keyed off concise / outline-style language
- kept heavy planning packs on the original `funnel + job` path

Primary file:

- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py`

### Strategist quality gate

- tightened clarify behavior for summary-style planning asks
- used `watch_policy.checkpoint=delivery_only` as a real behavioral signal
- avoided forcing clarify when grounding files are already present

Primary file:

- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py`

### Funnel runtime policy

- made `funnel_profile` affect Gate A thresholding
- kept the change intentionally small and local to avoid destabilizing the planning lane

Primary file:

- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/funnel_graph.py`

### Test coverage

Added / extended tests for:

- shortform meeting-summary detection
- lightweight business-planning routing
- summary clarify gating with and without grounding inputs
- funnel-profile Gate A behavior
- ingress-level route alignment for both `/v3/agent/turn` and `/v2/advisor/advise`

## Outcome

Phase 3 is now ready to hand over for review as a completed stage.

The remaining work is no longer “finish planning packs”, but “decide whether later phases should generalize these policy levers into broader execution/watch architecture”.
