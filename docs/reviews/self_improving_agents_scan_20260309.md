# Self-Improving Agents Scan

Date: 2026-03-09

## Why this note exists

During the OpenClaw/OpenMind topology review loop, I used spare time to look up the open-source "self improving agents" projects that are currently active enough to matter. The goal here is not to build from hype. The goal is to decide which patterns are worth borrowing into the current stack and which ones would be architectural regressions.

## Most relevant projects found

### 1. `iggyswelt/SIAS`

- URL: `https://github.com/iggyswelt/SIAS`
- Description: `Self-Improving Agent System for openclaw`
- Current signal:
  - very directly relevant to OpenClaw
  - low maturity / small community signal
  - last pushed `2026-02-18`

What it is:

- an OpenClaw-native memory and learning framework
- no external service
- no database
- uses markdown files, WAL-style logging, promotion rules, and a persistent workspace memory layout

What is actually useful:

- `write-ahead logging before response`
- explicit separation of:
  - transient learnings
  - promoted durable memory
  - user corrections / preferences
- the discipline that corrections should be recorded before the agent says "understood"

Why it should **not** become the new foundation here:

- it is intentionally file-based and lightweight, while this stack already has:
  - OpenMind memory
  - EvoMap governance
  - KB artifact layers
  - event / audit infrastructure
- replacing OpenMind with markdown memory would be a regression
- the right use is to borrow **behavioral protocol ideas**, not the storage model

Bottom line:

- **Best pattern source for OpenClaw-specific agent behavior**
- **Not** a substrate replacement

### 2. `jennyzzt/dgm`

- URL: `https://github.com/jennyzzt/dgm`
- Description: `Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents`
- Current signal:
  - strongest research credibility of the set
  - `1884` stars at lookup time
  - paper-backed

What it is:

- a research system that lets an agent iteratively modify its own code
- evaluates each change against coding benchmarks
- designed around empirical improvement loops, not day-to-day assistant memory

What is useful here:

- benchmark-gated self-modification
- explicit validation before accepting agent-written code changes
- strong reminder that "self-improving" without objective evaluation quickly turns into self-delusion

Why it is not a direct fit:

- it is a research harness, not an operational OpenClaw/OpenMind integration pattern
- it assumes a much heavier evaluation loop than this stack needs for daily assistant use

Bottom line:

- **Best reference for evaluation discipline**
- **Not** the right operational blueprint

### 3. `VibeCodingWithPhil/agentwise`

- URL: `https://github.com/VibeCodingWithPhil/agentwise`
- Description: `Multi-agent orchestration for Claude Code with ... self-improving agents`
- Current signal:
  - moderate activity
  - orchestration-heavy
  - explicitly Claude-oriented

What it is:

- a multi-agent orchestration layer with dashboards, routing, monitoring, and token optimization

What is useful here:

- on-demand specialist execution
- verification loops
- explicit orchestration ergonomics

Why it is not the right mainline here:

- the current OpenClaw/OpenMind direction just removed an overgrown persistent multi-agent mesh
- re-importing a large standing specialist topology would be the same design mistake in a new wrapper

Bottom line:

- **Useful reference for on-demand orchestration ergonomics**
- **Wrong direction** if interpreted as "bring back many persistent role agents"

## Strategic recommendation

For this stack, the right interpretation of "self improving agents" is:

- **borrow SIAS's WAL / correction-capture discipline**
- **borrow DGM's evaluation-before-promotion discipline**
- **borrow Agentwise's on-demand orchestration ergonomics**

Do **not** adopt:

- markdown-only memory as the core substrate
- self-modifying code loops without hard evaluation gates
- a new persistent multi-agent mesh inside OpenClaw

## Recommendation for the current roadmap

If this line is pursued later, the safest next step is:

1. Add a strict `capture-before-ack` rule for user corrections and preferences.
2. Keep OpenMind as the substrate of record.
3. Treat self-improvement as:
   - better memory capture
   - better promotion rules
   - better evaluation contracts
4. Keep specialist agents on-demand rather than persistent by default.

## Final judgment

The most relevant repo is `SIAS`, because it is explicitly built for OpenClaw and shares the same problem statement. But the correct action is **pattern extraction**, not adoption.

The current ChatgptREST/OpenMind stack is already beyond "markdown memory for one shell". The real opportunity is to import SIAS-style behavioral discipline into the richer substrate that already exists, not to replace that substrate with a lighter one.
