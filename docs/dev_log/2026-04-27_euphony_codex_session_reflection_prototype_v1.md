# 2026-04-27 Euphony Codex Session Reflection Prototype v1

## Scope

Evaluate OpenAI Euphony for local Codex session inspection, install it, and run a small prototype against ChatgptREST-related Codex session JSONL files to see what can feed an LLM wiki, reflection loop, and agent improvement process.

## Euphony install

Installed outside this repository:

- source: `https://github.com/openai/euphony`
- local path: `/vol1/1000/tools/euphony`
- version in `package.json`: `0.1.44`
- built output: `/vol1/1000/tools/euphony/dist`
- local viewer: `http://127.0.0.1:8766/`

Commands used:

```bash
mkdir -p /vol1/1000/tools
NO_PROXY=localhost,127.0.0.1,::1 no_proxy=localhost,127.0.0.1,::1 \
  curl -L --fail https://github.com/openai/euphony/archive/refs/heads/main.tar.gz \
  | tar -xz --strip-components=1 -C /vol1/1000/tools/euphony

cd /vol1/1000/tools/euphony
corepack pnpm install
VITE_EUPHONY_FRONTEND_ONLY=true corepack pnpm run build

nohup python3 -m http.server 8766 --bind 127.0.0.1 \
  -d /vol1/1000/tools/euphony/dist \
  > /tmp/euphony-http-8766.log 2>&1 &
```

Important environment note: shell access to GitHub hung while `NO_PROXY` included `github.com`, because it bypassed the local proxy. The install command temporarily narrowed `NO_PROXY` for that command only.

Verification:

- `curl -sI http://127.0.0.1:8766/` returned `HTTP/1.0 200 OK`.
- Playwright navigation to localhost was blocked by its current browser/client policy with `net::ERR_BLOCKED_BY_CLIENT`, so the verification evidence is the static build output plus curl health check.

## What Euphony is useful for

Euphony is useful as the human inspection layer, not as the memory layer.

It can directly render Codex session JSONL into a structured browser timeline. That makes it good for:

- reviewing long Codex work sessions without hand-written parsers
- seeing user prompts, assistant status updates, tool calls, and tool outputs in sequence
- debugging where a session went wrong, such as a bad command, an interrupted turn, or a transport/proxy issue
- selecting evidence spans before promoting anything into memory or wiki

It does not itself solve:

- durable synthesis
- cross-session deduplication
- confidence scoring
- promotion from raw transcript to stable rule
- project-specific memory routing

So the right architecture is: `Codex JSONL -> Euphony/manual review + extractor -> reviewed wiki/memory candidates -> llmwiki/.omx/wiki/memory writeback`.

## Prototype extractor

Added a repo-local offline prototype:

- [codex_session_reflection_extract.py](/vol1/1000/projects/ChatgptREST/scripts/prototypes/codex_session_reflection_extract.py)

It reads Codex JSONL and emits compact, redacted summaries:

- session metadata
- actual user prompts, excluding the injected `AGENTS.md` bootstrap prompt
- tool call counts
- command failure samples
- assistant/agent status update samples
- heuristic reflection/wiki candidates with category and confidence

Prototype output:

- [summary_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/euphony_codex_session_reflection_20260427/summary_v1.md)
- [summary_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/euphony_codex_session_reflection_20260427/summary_v1.json)

Sampled sessions:

1. `019dc3f6-9059-7732-8efe-36a6d9123194`
   - path: `/vol1/1000/home-yuanhaizhou/.codex1/sessions/2026/04/25/rollout-2026-04-25T17-26-49-019dc3f6-9059-7732-8efe-36a6d9123194.jsonl`
   - cwd: `/vol1/1000/projects/ChatgptREST`
   - topic: ChatgptREST 429 / Pro export completion guard debugging
   - result: high value for reflection and wiki

2. `019dca26-a2fd-7e33-809a-e3fb6d151edd`
   - path: `/vol1/1000/home-yuanhaizhou/.codex1/sessions/2026/04/26/rollout-2026-04-26T22-17-03-019dca26-a2fd-7e33-809a-e3fb6d151edd.jsonl`
   - cwd: `/home/yuanhaizhou/multica_workspaces/6aa0f38c-1f97-4fbb-a4ff-d48eb0d3a580/5492b11a/workdir`
   - topic: ASF-11 read-only proof worker
   - result: low long-term value; mostly a bounded proof run

3. `019dcdcb-bb9f-7b40-8453-7f674b9971d7`
   - path: `/vol1/1000/home-yuanhaizhou/.codex1/sessions/2026/04/27/rollout-2026-04-27T15-16-14-019dcdcb-bb9f-7b40-8453-7f674b9971d7.jsonl`
   - cwd: `/vol1/1000/projects/ChatgptREST`
   - topic: this Euphony prototype task
   - result: useful for environment/tooling lessons, especially proxy and package-source handling

## Extractable signal types

### 1. User correction and preference signals

Examples:

- "上条发错了，请忽略"
- "你要举一反三，深度反省"
- "出问题还是我去告诉你的，难道不是你应该知道的问题"
- "不是浏览器本身造成的"

These should not become raw wiki pages directly. They should feed a reviewed interaction-learning lane. ChatgptREST already has a compatible primitive in [interaction_learning.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/interaction_learning.py), which extracts user correction signals such as brevity, focus, quality bar, executor family, and closure style.

Recommended application:

- auto-detect correction candidates from sessions
- store as `user_correction` candidates with source session id and evidence span
- require either human approval or repeated evidence before promoting to stable agent policy

### 2. Debugging lessons

The 429 session produced the strongest wiki candidates:

- backend export HTTP 429 can coexist with DOM fallback success
- worker must not treat degraded export with backend 429 as ordinary success
- completion/finality must inspect export metadata, not just DOM text length
- Pro "thinking not visible in UI" is not the same as "wrong model selected"

Recommended application:

- promote to `debugging` wiki pages
- link each page to affected files/tests and source session id
- add recurrence checks to closeout or maintainer bootstrap when similar symptoms appear

### 3. Environment and toolchain lessons

This Euphony session produced a clear environment lesson:

- `github.com` in `NO_PROXY` made shell GitHub access hang by bypassing the configured local proxy
- npm registry access worked, but the official Euphony package was not available as `@openai/euphony`; the npm `euphony` package was `0.0.3`, while the official source repo showed `0.1.44`
- direct source tarball install was the correct path

Recommended application:

- store as `environment` wiki page
- add a reusable "GitHub fetch through proxy" note for future tool installs

### 4. Session-quality metrics

Useful metrics from Codex JSONL:

- command failure count
- long-running/hung commands
- interrupted turns
- repeated tool calls
- GitNexus impact/detect discipline
- test/closeout progression
- final answer vs actual committed state

Recommended application:

- use as session review dashboard, not direct memory
- flag sessions for retrospective when failure count, duration, or user correction count crosses threshold

### 5. Low-value session filtering

The ASF-11 worker session shows that not every transcript deserves wiki promotion. A single read-only proof prompt with no correction, no root-cause discovery, and no durable decision should usually remain as a session record only.

Recommended application:

- classify sessions as `archive_only`, `review_candidate`, or `promote_candidate`
- only promote when the session contains root cause, durable rule, repeated user preference, environment fix, or reusable procedure

## Proposed workflow

1. Daily or closeout batch scans recent Codex session files under `$CODEX_HOME/sessions`.
2. The extractor creates compact candidate artifacts under `docs/dev_log/artifacts/...` or an external private queue.
3. Euphony is used to inspect any candidate before promotion, especially when the evidence span is ambiguous.
4. Approved candidates are written to the local wiki layer:
   - `.omx/wiki/debugging/*.md` for root-cause lessons
   - `.omx/wiki/environment/*.md` for machine/tooling facts
   - `.omx/wiki/convention/*.md` for durable agent behavior rules
   - `.omx/wiki/session-log/*.md` for high-value session handoffs
5. Stable user-preference items should additionally route into ChatgptREST's interaction learning/memory path, not only wiki prose.
6. Agent bootstrap should read only compact wiki pages, not raw transcripts.

## Recommendation

Euphony is worth keeping, but as a viewer and evidence reviewer. It should not be the core self-learning system.

The useful self-learning loop is:

```text
Codex session JSONL
  -> Euphony inspection for human-readable transcript review
  -> offline extraction of compact candidates
  -> human/repeated-evidence promotion gate
  -> llmwiki/.omx/wiki + interaction_learning memory
  -> next-session bootstrap reads stable summaries only
```

This avoids the main failure mode: dumping noisy transcripts into memory and making the agent "learn" from one-off mistakes, stale context, or private implementation detail.
