# Gemini Review Packet v3

Review the current `Public Agent deliberation + maintenance unification` direction strictly.

Deliver:

1. findings first, ordered by severity
2. architecture verdict
3. open risks
4. recommended changes

Use these current repo facts as ground truth:

- Public Agent is supposed to remain the only general northbound entry.
- The blueprint also proposes a separate deliberation MCP family and a deterministic work-package MCP family.
- Current public MCP is still minimal and centered on advisor agent turn, status, and cancel.
- Current app composition still loads a separate consult router alongside agent v3.
- Current consult routing still keeps a separate consultation state universe.
- Current agent v3 still bridges consult and dual-review asks through consult semantics instead of a unified deliberation ledger.
- Guardian is still live and still carries policy behavior beyond simple patrol and notify.
- Maintagent is still configured more like a watchdog lane than a real maintenance brain.
- The maint repository is already shared into maint memory bootstrap for maint daemon and SRE lanes.
- Review pack and review repo sync tooling exist, but they are still CLI/manual and not yet a hard server-enforced deterministic compiler plane.

Please judge these questions:

1. Is it correct to keep review as an internal mode under Public Agent instead of a peer controller?
2. Is it a contradiction to add new top-level deliberation and work-package MCP families while also claiming a single northbound entry?
3. Is removing guardian now premature?
4. Is maintagent ready to become the maintenance brain yet?
5. Is the rollout order safe?

Be explicit if the direction is right but the current repo has not actually achieved the unification yet.
