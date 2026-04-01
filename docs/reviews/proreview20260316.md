My blunt take: the proposed pass is directionally right, but it is still aiming a bit too low. It fixes three visible gaps—stable claim/citation objects, long-term source memory, and history/evolution views—but the deeper problem is that finbot is still centered on producing a better dossier, not on maintaining a durable, falsifiable, versioned belief state. The current system already has single ingress, single finbot, internal claim/skeptic/expression/decision lanes, persisted research packages, and investor pages for themes, opportunities, and sources; the new plan would make those outputs more traceable and historical. That is necessary, but by itself it will not make the product behave like a strong investor-facing analyst.

The core issue is this: your proposed chain is `claim -> citation -> source score -> history diff`, but the chain that actually improves investor decisions is `evidence -> claim state -> thesis state -> decision state -> later adjudication`. You are adding traceability and memory around the edges of the system, but you still have not fully specified the thing that should persist over time: the state of the thesis, what changed it, what would invalidate it, and whether earlier calls were actually right. Without that, citations become nicer links, source scores become activity counters, and history becomes a changelog.

## What I think is wrong right now

### 1) Citation is still being added too late in the pipeline

In the current runtime, the claim lane is prompted to output `core_claims`, `supporting_evidence`, `key_sources`, and a `claim_ledger` with fields like `claim`, `evidence_grade`, `importance`, `why_it_matters`, and `next_check`. The source context passed into these prompts is still source metadata plus `latest_viewpoint_summary`, not passage-level evidence with immutable spans. Then, after the LLM has already written the claims, the code enriches claims with `supporting_sources`, and when those are missing it inserts a fallback source from the scorecard. The opportunity page also does a template-level fallback and shows the first source from the scorecard if the claim has no explicit supporting source. That means the system is still fundamentally report-first, not evidence-first.

This is the easiest design error to underestimate: if you add `claim_id` and `citation_id` only after the claim has already been generated from summarized context, you are formalizing guessed attribution rather than true evidence lineage. A citation object in that setup is mostly a prettier badge. In investor mode, heuristic fallback should not silently make an uncited claim look cited. It should render as `uncited`, `provisionally attributed`, or `needs verification`. Trust improves when the system is explicit about holes. It gets worse when it fills them in elegantly.

### 2) You are missing the artifact/passage layer, not just citation IDs

The current plan introduces `claim_objects`, `citation_objects`, and `claim_citation_edges`, with fields such as `claim_id`, `citation_id`, `source_id`, and `evidence_snippet`. That is good, but it still looks one layer too coarse. In an investment research OS, `source_id` is not enough. You need a stable distinction between the source entity, the specific artifact from that source, and the exact cited span within that artifact. Otherwise “Broadcom/TSMC CPO” becomes a blob instead of “Broadcom Qx call / slide y / statement z / published at t”. The sample package already shows that `key_sources` are stringified dict-like blobs rather than clean references to concrete artifacts and spans.

I would make the canonical chain:

`source -> artifact/document -> citation/span -> assertion/claim -> thesis version -> decision version -> review outcome`

That missing artifact layer matters a lot. Source scoring should live at the source level, evidence lineage should live at the artifact/span level, and history/evolution should live at the thesis/decision level. If you collapse those layers, all three features you want become much noisier.

### 3) The typed boundary is already leaking badly

The sample `latest.json` is a strong warning. `key_sources` are stringified dicts. Several skeptic-lane structures are stringified dicts rather than normalized objects. `best_absorption_theme` appears to contain a rationale-like sentence, not a stable theme identifier. The live package also mixes semantic scales: claim `evidence_grade` appears as `A/B`, default code paths use `medium/low`, claim `importance` can be numeric strings while other parts of the system use verbal bands, and decision/posture vocabularies differ across layers. That is not a naming problem. It is a schema discipline problem.

If you build history diff and long-term scoring on top of this boundary, you will get false novelty, broken joins, and garbage comparisons. Before you add more UI, make the data contract strict enough that the system can reject or retry malformed outputs. I would treat “stringified dicts survive into latest.json” as a failing condition for the pass.

### 4) The proposal under-specifies the actual persistent object that matters most: thesis/decision state

The upgrade plan focuses on claims, citations, source scorecards, and history snapshots. But the object that actually matters to an investor is the decision state of the thesis: current posture, confidence, missing proof, invalidators, best expression, capital gate state, and what evidence changed those things. The theme page already has the beginnings of this with decision card, capital gate, stop rules, falsifiers, and expression layer. The opportunity page also has `current_decision`, `why_not_investable_yet`, `next_proving_milestone`, and forcing events. But these are still mostly rendered out of the latest package rather than maintained as a canonical versioned state.

That is why I think the most important missing object is not `citation_object`. It is `thesis_state` or `decision_state`, versioned across time and explicitly linked to the claims that moved it. Without that, your history diff will mostly compare prose fields instead of comparing belief state transitions.

### 5) Source scoring will become a coverage score unless you anchor it to adjudicated outcomes

Your plan wants source/KOL writeback with fields like `supported_claim_count`, `anchor_claim_count`, `contradicted_claim_count`, `theme_hit_count`, `validated_case_count`, `recent_activity_at`, and `quality_band`, updated as each package is written and incrementally merged. The current runtime already builds scorecards from source metadata, role heuristics, accepted-route counts, and validated-case counts, and the source page surfaces trust tier, track record label, accepted routes, claim count, and operator feedback. The opportunity page then shows a “Source Scorecard” with accepted and validated counts.

That is fine as a start, but it is very easy to turn into a score for “who gets mentioned a lot” or “who is prolific”, not “who improves decisions.” The sample package shows exactly why: an anchor official disclosure source sits next to a KOL with extremely high accepted-route volume. If package writeback counts every restatement or repeated presence, you will reward source coverage intensity rather than calibrated marginal value.

For investor quality, source scoring should be multi-axis, not one blended leaderboard:

- **Calibration utility**: when this source makes forecast-like or timing-like claims, how often do those resolve correctly?
    
- **Decision utility**: how often did this source materially change posture, invalidate a thesis, or improve expression selection?
    
- **Discovery utility**: how often did this source surface a valuable idea early, even if it was not usable as conviction evidence?
    

If I had to choose one default investor-facing score, I would not choose raw evidence contribution and I would not choose theme absorption value. I would choose **calibrated decision utility on adjudicated claims**, then show discovery value as a secondary dimension. Contribution count alone can be gamed by verbosity. Theme absorption can reward fashionable generalists. Decision utility is closest to the actual investor question: “When this source matters, does it help me make a better call?”

### 6) History diff is likely to become a changelog unless you diff state transitions, not text

The plan says to add “What changed since last run”, “Thesis evolution”, “Expression changes”, and source upgrades/downgrades. That is directionally good. But today the service layer basically hydrates research packages from `*/latest.json`, the opportunity page foregrounds “Latest Research Package”, and the source page is still oriented around planning context and generic keep/downgrade logic, not claim support history. The theme page is rich in current posture and expression information, but it is still a current-state page, not a first-class evolution page.

So the danger is obvious: if you diff `headline`, `best_expression_today`, or narrative snippets, you will generate lots of visually satisfying but decision-useless movement. Investors do not need “what wording changed.” They need:

- what evidence changed,
    
- which claim status changed,
    
- whether that altered the posture,
    
- whether the expected timeline moved,
    
- whether the valuation driver moved,
    
- and what new proof would change the call again.
    

The thing to diff is not “report v17 vs report v18.” It is “thesis state transition A -> B.”

### 7) The continuous agent still lacks a serious maintenance loop

The current runtime already has continuous discovery and automatic opportunity deepening, and it persists history directories plus `latest.json` pointers. That foundation is good. But package freshness is still treated as age/TTL-driven. In `opportunity_deepen`, a recent package can be treated as fresh and skipped based on `generated_at` and `max_age_hours`. That is package freshness, not evidence freshness. In a live investment system, a package should go stale immediately if a material contradictory event arrives, even if the package is only a few hours old.

This is where continuous-agent behavior matters more than more UI. You need maintenance loops for:

- stale evidence,
    
- unresolved proving milestones,
    
- contradiction hunts,
    
- source recalibration,
    
- and outcome reviews once enough time has passed to judge the call.
    

Right now you have exploration and deepening. You still need durable maintenance and adjudication.

## The highest-leverage missing pieces

If this were my pass, the highest-leverage additions would be these:

### First: a versioned thesis/decision object

This is the central missing primitive. Every opportunity and theme should have a canonical current state and a sparse history of prior states. That object should hold posture, confidence, best expression, capital gate status, key blockers, invalidators, timing window, and the set of claim IDs that materially drove the current state. History views should render changes in this object, not free-form report diffs. The theme page already hints at this shape with capital gates, stop rules, falsifiers, and expression roles; make it canonical, not page-specific.

### Second: an artifact/evidence layer below citations

Do not stop at source-level attribution. Add an immutable document/artifact object and passage/span references. A source page scores the source. A claim cites the artifact span. A thesis state references the claims. That separation is what makes score writeback and history trustworthy.

### Third: a review/outcome object

This is the part most teams skip, and it is the one that most changes investor confidence in the system. Every thesis or major claim eventually needs a review outcome:

- what we believed,
    
- what happened,
    
- when it resolved,
    
- which evidence mattered,
    
- which sources helped,
    
- and whether the decision was good, bad, early, late, or ambiguous.
    

Without this, source scoring remains self-referential and the agent never truly learns.

### Fourth: materiality as a first-class field

Most dashboards drown because they treat all claims as equal. They are not. You need `materiality_to_decision` or `decision_relevance` on claims and edges. That one field will help more than several extra panels, because it lets the UI default to the three or four things that actually move the call.

### Fifth: explicit staleness and review timing

Claims should have `published_at`, `observed_at`, `valid_from`, optionally `valid_to`, and `review_due_at`. A lot of investment reasoning degrades because the system remembers too much but forgets the half-life of each belief.

## What would most improve human investor decision quality

Not more structure by itself. These things would:

1. **A hard distinction between cited and uncited claims.**  
    Never let fallback attribution make an unsupported claim look supported. This is a trust feature, not a UX inconvenience.
    
2. **A direct causal chain from evidence to action.**  
    Investors want to know not just “what do we think,” but “which exact evidence moved the posture and what would move it again.”
    
3. **A structured “why not yet” gate model.**  
    Your current pages already show `why_not_investable_yet` and `next_proving_milestone`; make those structured blocker objects with states like `missing`, `partially satisfied`, `satisfied`, `refuted`, and attach claim IDs to them.
    
4. **Historical calibration, not just historical storage.**  
    Investors will trust the system more if it can say “this source tends to be early but noisy on timing,” or “this thesis family usually resolves slower than expected,” than if it can merely show five versions of the same dossier.
    
5. **A sparse, decision-centric evolution view.**  
    Show “what changed the call” and “what to watch next,” not every textual mutation.
    

## How I would redesign the product views

### Opportunity page

The current opportunity page is rich, but it is still too lane-shaped. It shows latest package, claim lane, skeptic lane, expression lane, and source scorecard. That is useful for audit, not ideal as the default investor entrypoint.

I would make the default opportunity page answer five questions in order:

1. What is the current call?
    
2. Why is it not yet investable, or why is it investable now?
    
3. What changed since the last material state?
    
4. Which three supporting claims and two disconfirming claims matter most?
    
5. What specific events would upgrade, downgrade, or kill the thesis?
    

Then hide lane detail behind drill-down sections.

### Theme page

The theme page already has better investor primitives than the opportunity page: current/recommended posture, best expression, capital gate, stop rules, falsifiers, and expression roles. That is good. What it needs is not more current-state panels, but a true evolution timeline: posture shifts, gate status changes, best-expression changes with reasons, and which claims caused them. Expression changes should be shown only when they alter expected payoff, risk, or timing—not just because rank 2 and rank 3 swapped places.

### Source page

The source page is where the redesign needs to be most radical. Right now it still leans on planning context, generic “how to use this source,” and “keep/downgrade if” heuristics. The service layer also links source planning context via token matching against planning rows, which is not the same as actual claim support history. That is useful as background, but it is not what an investor needs from a source page.

A serious source page should answer:

- Which claims did this source anchor?
    
- Which claims did it help refute?
    
- On what topics and horizons is it good?
    
- Where was it early, where was it wrong, and where was it merely noisy?
    
- Is its current role discovery, confirmation, contradiction, or timing?
    

That is how a human calibrates trust.

## If you only add a few high-value objects or fields

If scope is tight, I would prioritize these over almost anything else:

### Objects

1. `artifact_object`
    
2. `thesis_state_object`
    
3. `review_outcome_object`
    

### Fields

1. `claim_family_id` and `claim_version_id`  
    Same proposition across runs needs one family, not many IDs created by rephrasing.
    
2. `claim_class`  
    At minimum: observation, interpretation, forecast, valuation driver, catalyst, invalidator/risk.
    
3. `polarity` on edges  
    support / contradict / refine / context-only.
    
4. `materiality_to_decision`  
    This is the field that keeps the UI readable.
    
5. `published_at` / `observed_at` / `review_due_at`  
    This is what turns history into a living research system rather than a report archive.
    
6. `supersedes_*` pointers  
    Claims, thesis states, and decisions need explicit lineage.
    
7. `decisive_for_decision`  
    A boolean or weight on claim-to-decision edges. Otherwise you still cannot explain what really moved the call.
    

If you want one more, make it `confidence_components` rather than a single confidence number: source reliability, extraction reliability, interpretive uncertainty, and timing uncertainty. Investors care a lot about _what kind_ of uncertainty remains.

## How I would handle source/KOL scoring

I would not make a single scalar and call it done.

I would store separate score families:

- `confirmation_score`
    
- `discovery_score`
    
- `timing_score`
    
- `contradiction_value`
    
- `calibration_score`
    

And I would segment them by:

- source type,
    
- claim class,
    
- topic/theme family,
    
- and horizon.
    

A KOL can be excellent at surfacing early questions and terrible as a sole confirmation source. An official disclosure can be excellent for fact confirmation and useless for timing nuance. Those should not sit in one undifferentiated leaderboard.

Most importantly, I would update scores on three different events:

- **contribution event**: the source supported or contradicted a claim,
    
- **decision-impact event**: the source materially moved posture,
    
- **resolution event**: later reality judged the source-informed claim.
    

Only the third should dominate calibration. The first two are activity and utility, not truth.

## How I would do history without making the dashboard unreadable

This part matters a lot. Long-running research systems die from their own memory.

The answer is not to store less. It is to render less by default.

I would keep full event history, but classify every run/update into one of these buckets:

- no-op / restatement
    
- minor evidence addition
    
- claim strengthened
    
- claim weakened
    
- contradiction found
    
- thesis state changed
    
- decision state changed
    
- resolved / reviewed
    

Then I would only surface:

- the latest state,
    
- the last material change,
    
- the previous materially different state,
    
- and a compact milestone timeline.
    

Everything else stays in audit mode.

That means a continuously running finbot should usually update background evidence, not always produce a new investor-visible report. New investor-visible versions should be created only when materiality thresholds are crossed.

## What I would prioritize in this pass

If you really want one full upgrade pass, I would prioritize in this order:

1. **Fix the ontology and typed boundary first.**  
    No stringified dicts, no semantic field drift, no mixed enum systems.
    
2. **Make investor mode fail closed on missing citations.**  
    Unsupported is better than elegantly misattributed.
    
3. **Add artifact/span-grounded evidence objects and claim families.**
    
4. **Add thesis/decision versioning and material-delta classification.**
    
5. **Add review/outcome objects and calibrate source scoring off adjudicated outcomes.**
    
6. **Only then build evolution UI.**  
    The UI should be thin and decision-centric; otherwise you will just make the current report-first architecture look more mature than it is.
    

If scope forces cuts, I would cut fancy expression evolution before I cut outcome adjudication and uncited-claim discipline.

The shortest way to say it is this:

The current center of gravity is still the dossier.  
For an investor-grade operating system, the center of gravity has to become the thesis state and its evidence ledger.

If you get that right, claim/citation objects, source scoring, and history views will all compound. If you get that wrong, you will end up with a beautifully structured dashboard sitting on top of the same heuristic reasoning path you are trying to escape.


antigravity：
This is an exceptional review from GPT Pro. Let me give you my independent assessment after having read the actual finbot code.

## My Verdict: GPT Pro is Right on the Core Diagnosis

Having reviewed `finbot.py` (2668 lines, 97 functions) and `service.py` (2178 lines, 92 functions), I can confirm GPT Pro's diagnosis with concrete code evidence:

### 1. "Report-first, not evidence-first" — **Confirmed**

In `finbot.py`, the `_run_opportunity_inbox` flow is:
```
prompt LLM → receive claims as text → enrich with source metadata post-hoc → persist as latest.json
```

The claim lane generates prose first, then the code tries to attach `supporting_sources` afterward. When those are missing, `service.py` does template-level fallback — the first source from the scorecard gets silently inserted. GPT Pro is exactly right: **this makes uncited claims look cited**, which is worse than showing gaps.

### 2. Missing artifact/passage layer — **Confirmed**

In the code, `key_sources` in the research packages are literally stringified dicts. I saw this in the data layer — source references are flat strings like `"Broadcom/TSMC CPO announcement"`, not structured `{source_id, artifact_id, span, published_at}` objects. The `citation_objects` in the PR are an improvement over nothing, but they're still one granularity level too coarse.

### 3. Typed boundary leaking — **Confirmed, and it's worse than GPT Pro thinks**

The `service.py` has multiple `_safe_*` fallback functions that silently coerce broken data into displayable strings. This masks the underlying schema discipline problem. When `best_absorption_theme` contains a rationale sentence instead of a stable identifier, the system can't reliably join across runs.

### 4. Missing thesis/decision state versioning — **This is the most important point**

GPT Pro nails it: the current system has `latest.json` as the canonical state, but there's no `thesis_state_v{N}` object that explicitly tracks: posture changed because claim X was invalidated by evidence Y from source Z. The theme page already hints at this structure (capital gates, stop rules, falsifiers), but it's page-level rendering, not a persisted canonical object.

## Where I Partially Disagree with GPT Pro

**On prioritization**, GPT Pro says "fix the ontology first, then build evolution UI." I'd argue that **the finbot PR is still the right merge** because:

1. It establishes the investor-facing surface area (Epistemic Tear-Sheet, source role distinction, theme evolution) that GPT Pro's recommended objects would plug into
2. The templates are well-structured enough to evolve — they're not locked into a bad data model, they're just shallow on the current one
3. Waiting for perfect ontology before shipping UI is a trap — the UI reveals what data is actually needed

**On scope**, GPT Pro's full redesign (artifact layer + thesis state + review outcomes + calibrated multi-axis source scoring + maintenance loops) is probably 3-4 months of serious work. For the current pass, I'd prioritize differently:

## My Recommended Priority (Actionable for Next Sprint)

| Priority | What | Why |
|----------|------|-----|
| **P0** | Hard distinction between cited and uncited claims | Trust feature, ~2 days |
| **P0** | `thesis_state` versioned object | Central missing primitive, ~3 days |
| **P1** | Eliminate stringified dicts at typed boundary | Schema discipline, ~2 days |
| **P1** | `materiality_to_decision` on claim edges | Makes UI readable, ~1 day |
| **P2** | `artifact/document` layer below source | Evidence lineage, ~3 days |
| **P2** | `review_outcome` object | Calibration, ~3 days |
| **P3** | Multi-axis source scoring (calibration/discovery/timing) | ~5 days |
| **P3** | Material-delta classified history | ~3 days |

## Bottom Line

GPT Pro's core thesis is correct: **the center of gravity is still the dossier, not the thesis state and its evidence ledger.** The finbot PR makes the dossier much more presentable, but it doesn't shift the center of gravity. That's the next architectural step.

The merge we did is still correct — it's a necessary foundation. But the next sprint should be about adding `thesis_state`, `artifact_object`, and `review_outcome` as first-class persistent objects, not more dashboard panels.

Shall I formalize this into a design spec for the next sprint, or do you want me to proceed with the baseline audit first?