# Replay Acceptance Contract

Historical replay is allowed only from frozen artifacts. It must not fetch real-time market data.

Each replay fixture must produce:

- `OpportunityCase` draft;
- evidence gate verdict;
- signal rule contract status;
- terminal state: `kill`, `park`, `blocked`, `monitor_only`, or `candidate`;
- reuse decision update.

