# Microsoft - Harness Engineering for Azure SRE Agent

- source_url: https://techcommunity.microsoft.com/blog/appsonazureblog/the-agent-that-investigates-itself/4500073
- fetched_at: 2026-03-31T12:45:47+08:00
- extract_method: scrapling

Open Side Menu

Skip to content[![Brand Logo](https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/themes/customTheme1/favicon-1730836271365.png?time=1730836274203)](/)

[Tech Community](/)[Community Hubs](/Directory)

[Products](/)

[Topics](/)

[Blogs](/Blogs)[Events](/Events)

[Skills Hub](/category/skills-hub)

[Community](/)

[Register](/t5/s/gxcuf89792/auth/oidcss/sso_login_redirect/provider/default?referer=https%3A%2F%2Ftechcommunity.microsoft.com%2Fblog%2Fappsonazureblog%2Fthe-agent-that-investigates-itself%2F4500073)[Sign In](/t5/s/gxcuf89792/auth/oidcss/sso_login_redirect/provider/default?referer=https%3A%2F%2Ftechcommunity.microsoft.com%2Fblog%2Fappsonazureblog%2Fthe-agent-that-investigates-itself%2F4500073)

  1. [Microsoft Community Hub](/)
  2.   3. [Communities](/category/communities)[Products](/category/products-services)

  4.   5. [Azure](/category/azure)
  6.   7. [Apps on Azure Blog](/category/azure/blog/appsonazureblog)



Report

Find community, meet experts, build skills, and discover the latest in AI. Join us at the Microsoft 365 Community Conference April 21-23. Learn more >

## Blog Post

![](https://techcommunity.microsoft.com/t5/s/gxcuf89792/images/bS00NTAwMDczLTFUdTdDVQ?revision=57&image-dimensions=2000x2000&constrain-image=true)

Apps on Azure Blog 

11 MIN READ

# The Agent that investigates itself

[![sanchitmehta's avatar](https://techcommunity.microsoft.com/t5/s/gxcuf89792/images/dS0yNDc4NDY3LWJJRDhkMA?image-coordinates=39%2C42%2C322%2C326&image-dimensions=50x50)](/users/sanchitmehta/2478467)

[sanchitmehta](/users/sanchitmehta/2478467)

![Icon for Microsoft rank](https://techcommunity.microsoft.com/t5/s/gxcuf89792/images/cmstNC05WEo0blc?image-dimensions=100x16&constrain-image=true)Microsoft

Mar 10, 2026

## The most productive engineer on our team isn't a person. It's the agent we built - investigating itself.

Azure SRE Agent handles tens of thousands of incident investigations each week for internal Microsoft services and external teams running it for their own systems. Last month, one of those incidents was about the agent itself.

Our [KV cache](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) hit rate alert started firing. Cached token percentage was dropping across the fleet. We didn't open dashboards. We simply asked the agent.

It spawned parallel subagents, searched logs, read through its own source code, and produced the analysis. First finding: Claude Haiku at 0% cache hits. The agent checked the input distribution and found that the average call was ~180 tokens, well below Anthropic’s 4,096-token minimum for Haiku prompt caching. Structurally, these requests could never be cached. They were false positives.

The real regression was in Claude Opus: cache hit rate fell from ~70% to ~48% over a week. The agent correlated the drop against the deployment history and traced it to a single PR that restructured prompt ordering, breaking the common prefix that caching relies on. It submitted two fixes: one to exclude all uncacheable requests from the alert, and the other to restore prefix stability in the prompt pipeline.

> That investigation is how we develop now. We rarely start with dashboards or manual log queries. We start by asking the agent.

Three months earlier, it could not have done any of this. The breakthrough was not building better playbooks. It was **harness engineering** : enabling the agent to discover context as the investigation unfolded.

This post is about the architecture decisions that made it possible.

### Where we started

In our last post, [Context Engineering for Reliable AI Agents: Lessons from Building Azure SRE Agent](https://techcommunity.microsoft.com/blog/appsonazureblog/context-engineering-lessons-from-building-azure-sre-agent/4481200), we described how moving to a single generalist agent unlocked more complex investigations. The resolution rates were climbing, and for many internal teams, the agent could now autonomously investigate and mitigate roughly 50% of incidents. We were moving in the right direction.

But the scores weren't uniform, and when we dug into why, the pattern was uncomfortable. The high-performing scenarios shared a trait: they'd been built with heavy human scaffolding. They relied on custom response plans for specific incident types, hand-built subagents for known failure modes, and pre-written log queries exposed as opaque tools. We weren’t measuring the agent’s reasoning – we were measuring how much engineering had gone into the scenario beforehand. On anything new, the agent had nowhere to start.

We found these gaps through manual review. Every week, engineers read through lower-scored investigation threads and pushed fixes: tighten a prompt, fix a tool schema, add a guardrail. Each fix was real. But we could only review fifty threads a week. The agent was handling ten thousand. We were debugging at human speed. The gap between those two numbers was where our blind spots lived.

> We needed an agent powerful enough to take this toil off us. An agent which could investigate itself. Dogfooding wasn't a philosophy - it was the only way to scale.

### The Inversion: Three bets

The problem we faced was structural - and the KV cache investigation shows it clearly. The cache rate drop was visible in telemetry, but the cause was not. The agent had to correlate telemetry with deployment history, inspect the relevant code, and reason over the diff that broke prefix stability. We kept hitting the same gap in different forms: logs pointing in multiple directions, failure modes in uninstrumented paths, regressions that only made sense at the commit level. Telemetry showed symptoms, but not what actually changed. 

> We'd been building the agent to reason over telemetry. We needed it to reason over the system itself.

The instinct when agents fail is to restrict them: pre-write the queries, pre-fetch the context, pre-curate the tools. It feels like control. In practice, it creates a ceiling. The agent can only handle what engineers anticipated in advance.

The answer is an agent that can discover what it needs as the investigation unfolds. In the KV cache incident, each step, from metric anomaly to deployment history to a specific diff, followed from what the previous step revealed. It was not a pre-scripted path. Navigating towards the right context with progressive discovery is key to creating deep agents which can handle novel scenarios.

![](https://techcommunity.microsoft.com/t5/s/gxcuf89792/images/bS00NTAwMDczLWcwR0pUaw?image-dimensions=999x543&revision=57)

Three architectural decisions made this possible – and each one compounded on the last.

### Bet 1: The Filesystem as the Agent's World

Our first bet was to give the agent a filesystem as its workspace instead of a custom API layer.

![](https://techcommunity.microsoft.com/t5/s/gxcuf89792/images/bS00NTAwMDczLTNKVk55WA?image-dimensions=770x471&revision=57)

Everything it reasons over – source code, runbooks, query schemas, past investigation notes – is exposed as files. It interacts with that world using  _read_file_ , _grep_ , _find_ , and  _shell_. No _SearchCodebase_ API. No  _RetrieveMemory_ endpoint.

This is an old Unix idea: reduce heterogeneous resources to a single interface. Coding agents already work this way. It turns out the same pattern works for an SRE agent.

Frontier models are trained on developer workflows: navigating repositories, grepping logs, patching files, running commands. The filesystem is not an abstraction layered on top of that prior. It matches it.

> When we materialized the agent’s world as a repo-like workspace, our human "Intent Met" score - whether the agent's investigation addressed the actual root cause as judged by the on-call engineer - rose from 45% to 75% on novel incidents.

But interface design is only half the story. The other half is what you put inside it.

#### Code Repositories: the highest-leverage context

Teams had prewritten log queries because they did not trust the agent to generate correct ones. That distrust was justified. Models hallucinate table names, guess column schemas, and write queries against the wrong cluster. But the answer was not tighter restriction. It was better grounding.

> The repo is the schema. Everything else is derived from it.

When the agent reads the code that produces the logs, query construction stops being guesswork. It knows the exact exceptions thrown, and the conditions under which each path executes. Stack traces start making sense, and logs become legible. But beyond query grounding, code access unlocked three new capabilities that telemetry alone could not provide:

  * **Ground truth over documentation.** Docs drift and dashboards show symptoms. The code is what the service actually does. In practice, most investigations only made sense when logs were read alongside implementation.
  * **Point-in-time investigation.** The agent checks out the exact commit at incident time, not current HEAD, so it can correlate the failure against the actual diffs. That's what cracked the KV cache investigation: a PR broke prefix stability, and the diff was the only place this was visible. Without commit history, you can't distinguish a code regression from external factors.
  * **Reasoning even where telemetry is absent.** Some code paths are not well instrumented. The agent can still trace logic through source and explain behavior even when logs do not exist. This is especially valuable in novel failure modes – the ones most likely to be missed precisely because no one thought to instrument them.



#### Memory as a filesystem, not a vector store

Our first memory system used RAG over past session learnings. It had a circular dependency: a limited agent learned from limited sessions and produced limited knowledge. Garbage in, garbage out.

But the deeper problem was retrieval. In SRE Context, embedding similarity is a weak proxy for relevance. “KV cache regression” and “prompt prefix instability” may be distant in embedding space yet still describe the same causal chain. We tried re-ranking, query expansion, and hybrid search. None fixed the core mismatch between semantic similarity and diagnostic relevance.

![](https://techcommunity.microsoft.com/t5/s/gxcuf89792/images/bS00NTAwMDczLWlQb3FPeg?image-dimensions=840x495&revision=57)

We replaced RAG with structured Markdown files that the agent reads and writes through its standard tool interface. The model names each file semantically:_overview.md_ for a service summary, _team.md_ for ownership and escalation paths, _logs.md_ for cluster access and query patterns, _debugging.md_ for failure modes and prior learnings. Each carry just enough context to orient the agent, with links to deeper files when needed.

> The key design choice was to let the model _navigate_ memory, not retrieve it through query matching. The agent starts from a structured entry point and follows the evidence toward what matters.

RAG assumes you know the right query before you know what you need. File traversal lets relevance emerge as context accumulates. This removed chunking, overlap tuning, and re-ranking entirely. It also proved more accurate, because frontier models are better at following context than embeddings are at guessing relevance. As a side benefit, memory state can be snapshotted periodically.

One problem remains unsolved: staleness. When two sessions write conflicting patterns to debugging.md, the model must reconcile them. When a service changes behavior, old entries can become misleading. We rely on timestamps and explicit deprecation notes, but we do not have a systemic solution yet. This is an active area of work, and anyone building memory at scale will run into it. 

#### The sandbox as epistemic boundary

The filesystem also defines what the agent can see. If something is not in the sandbox, the agent cannot reason about it. We treat that as a feature, not a limitation. Security boundaries and epistemic boundaries are enforced by the same mechanism.

Inside that boundary, the agent has full execution: arbitrary _bash_ , _python_ , _jq_ , and package installs through _pip_ or _apt_. That scope unlocks capabilities we never would have built as custom tools. It opens PRs with _gh cli_ , like the prompt-ordering fix from KV cache incident. It pushes Grafana dashboards, like a cache-hit-rate dashboard we now track by model. It installs domain-specific CLI tools mid-investigation when needed. No bespoke integration required, just a shell.

> The recurring lesson was simple: a generally capable agent in the right execution environment outperforms a specialized agent with bespoke tooling. Custom tools accumulate maintenance costs. Shell commands compose for free.

### Bet 2: Context Layering

![](https://techcommunity.microsoft.com/t5/s/gxcuf89792/images/bS00NTAwMDczLTNCc2VvTQ?image-dimensions=612x999&revision=57)

Code access tells the agent what a service does. It does not tell the agent what it can access, which resources its tools are scoped to, or where an investigation should begin.

This gap surfaced immediately. Users would ask "which team do you handle incidents for?" and the agent had no answer. Tools alone are not enough. An integration also needs _ambient context_ so the model knows what exists, how it is configured, and when to use it.

We fixed this with **context hooks** : structured context injected at prompt construction time to orient the agent before it takes action.

  * **Connectors -**_what can I access?_ A manifest of wired systems such as Log Analytics, Outlook, and Grafana, along with their configuration.
  * **Repositories** \- _what does this system do?_ Serialized repo trees, plus files like AGENTS.md, Copilot.md, and CLAUDE.md with team-specific instructions.
  * **Knowledge map** _\- what have I learned before?_ A two-tier memory index with a top-level file linking to deeper scenario-specific files, so the model can drill down only when needed.
  * **Azure resource topology** _\- where do things live?_ A serialized map of relationships across subscriptions, resource groups, and regions, so investigations start in the right scope.



Together, these _context hooks_ turn a cold start into an informed one. That matters because a bad early choice does not just waste tokens. It sends the investigation down the wrong trajectory.

> A capable agent still needs to know what exists, what matters, and where to start.

### Bet 3: Frugal Context Management

![](https://techcommunity.microsoft.com/t5/s/gxcuf89792/images/bS00NTAwMDczLURHTXhNMA?image-dimensions=719x458&revision=57)

##### 

Layered context creates a new problem: budget. Serialized repo trees, resource topology, connector manifests, and a memory index fill context fast. Once the agent starts reading source files and logs, complex incidents hit context limits. We needed our context usage to be deliberately frugal.

##### Tool result compression via the filesystem

Large tool outputs are expensive because they consume context before the agent has extracted any value from them. In many cases, only a small slice or a derived summary of that output is actually useful. Our framework exposes these results as files to the agent. The agent can then use tools like _grep_ , _jq_ , or _python_ to process them outside the model interface, so that only the final result enters context.

The filesystem isn't just a capability abstraction - it's also a budget management primitive.

##### Context Pruning and Auto Compact

Long investigations accumulate dead weight. As hypotheses narrow, earlier context becomes noise. We handle this with two compaction strategies.

Context Pruning runs mid-session. When context usage crosses a threshold, we trim or drop stale tool calls and outputs - keeping the window focused on what still matters.

Auto-Compact kicks in when a session approaches its context limit. The framework summarizes findings and working hypotheses, then resumes from that summary. From the user's perspective, there's no visible limit. Long investigations just work.

##### Parallel subagents

The KV cache investigation required reasoning along two independent hypotheses: whether the alert definition was sound, and whether cache behavior had actually regressed. The agent spawned parallel subagents for each task, each operating in its own context window. Once both finished, it merged their conclusions.

This pattern generalizes to any task with independent components. It speeds up the search, keeps intermediate work from consuming the main context window, and prevents one hypothesis from biasing another.

### The Feedback loop

These architectural bets have enabled us to close the original scaling gap. Instead of debugging the agent at human speed, we could finally start using it to fix itself.

As an example, we were hitting various LLM errors: timeouts, 429s (too many requests), failures in the middle of response streaming, 400s from code bugs that produced malformed payloads. These paper cuts would cause investigations to stall midway and some conversations broke entirely.

So, we set up a daily monitoring task for these failures. The agent searches for the last 24 hours of errors, clusters the top hitters, traces each to its root cause in the codebase, and submits a PR. We review it manually before merging. Over two weeks, the errors were reduced by more than 80%.

Over the last month, we have successfully used our agent across a wide range of scenarios:

  * Analyzed our user churn rate and built dashboards we now review weekly.
  * Correlated which builds needed the most hotfixes, surfacing flaky areas of the codebase.
  * Ran security analysis and found vulnerabilities in the read path.
  * Helped fill out parts of its own Responsible AI review, with strict human review.
  * Handles customer-reported issues and LiveSite alerts end to end.



Whenever it gets stuck, we talk to it and teach it, ask it to update its memory, and it doesn't fail that class of problem again.

> The title of this post is literal. The agent investigating itself is not a metaphor. It is a real workflow, driven by scheduled tasks, incident triggers, and direct conversations with users.

### What We Learned

We spent months building scaffolding to compensate for what the agent could not do. The breakthrough was removing it. Every prewritten query was a place we told the model not to think. Every curated tool was a decision made on its behalf. Every pre-fetched context was a guess about what would matter before we understood the problem.

The inversion was simple but hard to accept: stop pre-computing the answer space. Give the model a structured starting point, a filesystem it knows how to navigate, context hooks that tell it what it can access, and budget management that keeps it sharp through long investigations.

The agent that investigates itself is both the proof and the product of this approach. It finds its own bugs, traces them to root causes in its own code, and submits its own fixes. Not because we designed it to. Because we designed it to reason over systems, and it happens to be one.

We are still learning. Staleness is unsolved, budget tuning remains largely empirical, and we regularly discover assumptions baked into context that quietly constrain the agent. 

But we have crossed a new threshold: from an agent that follows your playbook to one that writes the next one.

Thanks to [visagarwal​](/users/visagarwal/1888041) for co-authoring this post.

Updated Mar 14, 2026

Version 11.0

[azure paas](/tag/azure%20paas?nodeId=board%3AAppsonAzureBlog)

[azure sre agent](/tag/azure%20sre%20agent?nodeId=board%3AAppsonAzureBlog)

[best practices](/tag/best%20practices?nodeId=board%3AAppsonAzureBlog)

[cloud native](/tag/cloud%20native?nodeId=board%3AAppsonAzureBlog)

[devops](/tag/devops?nodeId=board%3AAppsonAzureBlog)

[serverless](/tag/serverless?nodeId=board%3AAppsonAzureBlog)

[updates](/tag/updates?nodeId=board%3AAppsonAzureBlog)

LikeLike

6

CommentComment

[![sanchitmehta's avatar](https://techcommunity.microsoft.com/t5/s/gxcuf89792/images/dS0yNDc4NDY3LWJJRDhkMA?image-coordinates=39%2C42%2C322%2C326&image-dimensions=80x80)](/users/sanchitmehta/2478467)

[sanchitmehta](/users/sanchitmehta/2478467)

![Icon for Microsoft rank](https://techcommunity.microsoft.com/t5/s/gxcuf89792/images/cmstNC05WEo0blc?image-dimensions=100x16&constrain-image=true)Microsoft

Joined May 17, 2024

Send Message

[View Profile](/users/sanchitmehta/2478467)

[](/category/azure/blog/appsonazureblog)

[Apps on Azure Blog ](/category/azure/blog/appsonazureblog)

Follow this blog board to get notified when there's new activity

Enjoying the article? Sign in to share your thoughts.

Sign in

###  Share this page 

  * [](https://www.linkedin.com/sharing/share-offsite/?url=https%3A%2F%2Ftechcommunity.microsoft.com%2Fblog%2Fappsonazureblog%2Fthe-agent-that-investigates-itself%2F4500073)
  * [](https://www.facebook.com/share.php?u=https%3A%2F%2Ftechcommunity.microsoft.com%2Fblog%2Fappsonazureblog%2Fthe-agent-that-investigates-itself%2F4500073&t=Harness%20Engineering%20for%20Azure%20SRE%20Agent%3A%20Building%20the%20Agent%20Self-Improvement%20Loop)
  * [](https://twitter.com/share?text=Harness%20Engineering%20for%20Azure%20SRE%20Agent%3A%20Building%20the%20Agent%20Self-Improvement%20Loop&url=https%3A%2F%2Ftechcommunity.microsoft.com%2Fblog%2Fappsonazureblog%2Fthe-agent-that-investigates-itself%2F4500073)
  * [](https://www.reddit.com/submit?url=https%3A%2F%2Ftechcommunity.microsoft.com%2Fblog%2Fappsonazureblog%2Fthe-agent-that-investigates-itself%2F4500073&title=Harness%20Engineering%20for%20Azure%20SRE%20Agent%3A%20Building%20the%20Agent%20Self-Improvement%20Loop)
  * [](https://bsky.app/intent/compose?text=Harness%20Engineering%20for%20Azure%20SRE%20Agent%3A%20Building%20the%20Agent%20Self-Improvement%20Loop%21%20%F0%9F%A6%8B%0Ahttps%3A%2F%2Ftechcommunity.microsoft.com%2Fblog%2Fappsonazureblog%2Fthe-agent-that-investigates-itself%2F4500073)
  * [](/t5/s/gxcuf89792/rss/Community)
  * [](mailto:?body=https%3A%2F%2Ftechcommunity.microsoft.com%2Fblog%2Fappsonazureblog%2Fthe-agent-that-investigates-itself%2F4500073)



What's new

  * [Surface Pro](https://www.microsoft.com/surface/devices/surface-pro)
  * [Surface Laptop](https://www.microsoft.com/surface/devices/surface-laptop)
  * [Surface Laptop Studio 2](https://www.microsoft.com/d/Surface-Laptop-Studio-2/8rqr54krf1dz)
  * [Copilot for organizations](https://www.microsoft.com/microsoft-copilot/organizations?icid=DSM_Footer_CopilotOrganizations)
  * [Copilot for personal use](https://www.microsoft.com/microsoft-copilot/for-individuals?form=MY02PT&OCID=GE_web_Copilot_Free_868g3t5nj)
  * [AI in Windows](https://www.microsoft.com/windows/ai-features?icid=DSM_Footer_WhatsNew_AIinWindows)
  * [Explore Microsoft products](https://www.microsoft.com/microsoft-products-and-apps)
  * [Windows 11 apps](https://www.microsoft.com/windows/apps-for-windows?icid=DSM_Footer_WhatsNew_Windows11apps)



Microsoft Store

  * [Account profile](https://account.microsoft.com/)
  * [Download Center](https://www.microsoft.com/download)
  * [Microsoft Store support](https://go.microsoft.com/fwlink/?linkid=2139749)
  * [Returns](https://go.microsoft.com/fwlink/p/?LinkID=824764&clcid=0x809)
  * [Order tracking](https://www.microsoft.com/store/b/order-tracking)
  * [Certified Refurbished](https://www.microsoft.com/store/b/certified-refurbished-products)
  * [Microsoft Store Promise](https://www.microsoft.com/store/b/why-microsoft-store?icid=footer_why-msft-store_7102020)
  * [Flexible Payments](https://www.microsoft.com/store/b/payment-financing-options?icid=footer_financing_vcc)



Education

  * [Microsoft in education](https://www.microsoft.com/education)
  * [Devices for education](https://www.microsoft.com/education/devices/overview)
  * [Microsoft Teams for Education](https://www.microsoft.com/education/products/teams)
  * [Microsoft 365 Education](https://www.microsoft.com/education/products/microsoft-365)
  * [How to buy for your school](https://www.microsoft.com/education/how-to-buy)
  * [Educator training and development](https://education.microsoft.com/)
  * [Deals for students and parents](https://www.microsoft.com/store/b/education)
  * [AI for education](https://www.microsoft.com/education/ai-in-education)



Business

  * [Microsoft AI](https://www.microsoft.com/ai?icid=DSM_Footer_AI)
  * [Microsoft Security](https://www.microsoft.com/security)
  * [Dynamics 365](https://www.microsoft.com/dynamics-365)
  * [Microsoft 365](https://www.microsoft.com/microsoft-365/business)
  * [Microsoft Power Platform](https://www.microsoft.com/power-platform)
  * [Microsoft Teams](https://www.microsoft.com/microsoft-teams/group-chat-software)
  * [Microsoft 365 Copilot](https://www.microsoft.com/microsoft-365-copilot?icid=DSM_Footer_Microsoft365Copilot)
  * [Small Business](https://www.microsoft.com/store/b/business?icid=CNavBusinessStore)



Developer & IT

  * [Azure](https://azure.microsoft.com/)
  * [Microsoft Developer](https://developer.microsoft.com/)
  * [Microsoft Learn](https://learn.microsoft.com/)
  * [Support for AI marketplace apps](https://www.microsoft.com/software-development-companies/offers-benefits/isv-success?icid=DSM_Footer_SupportAIMarketplace&ocid=cmm3atxvn98)
  * [Microsoft Tech Community](https://techcommunity.microsoft.com/)
  * [Microsoft Marketplace](https://marketplace.microsoft.com/?icid=DSM_Footer_Marketplace&ocid=cmm3atxvn98)
  * [Marketplace Rewards](https://www.microsoft.com/software-development-companies/offers-benefits/marketplace-rewards?icid=DSM_Footer_MarketplaceRewards&ocid=cmm3atxvn98)
  * [Visual Studio](https://visualstudio.microsoft.com/)



Company

  * [Careers](https://careers.microsoft.com/)
  * [About Microsoft](https://www.microsoft.com/about)
  * [Company news](https://news.microsoft.com/source/?icid=DSM_Footer_Company_CompanyNews)
  * [Privacy at Microsoft](https://www.microsoft.com/privacy?icid=DSM_Footer_Company_Privacy)
  * [Investors](https://www.microsoft.com/investor/default.aspx)
  * [Diversity and inclusion](https://www.microsoft.com/diversity/default?icid=DSM_Footer_Company_Diversity)
  * [Accessibility](https://www.microsoft.com/accessibility)
  * [Sustainability](https://www.microsoft.com/sustainability/)



[California Consumer Privacy Act (CCPA) Opt-Out IconYour Privacy Choices](https://aka.ms/yourcaliforniaprivacychoices)[Consumer Health Privacy](https://go.microsoft.com/fwlink/?linkid=2259814)

  * [Sitemap](https://www.microsoft.com/en-us/sitemap1.aspx)
  * [Contact Microsoft](https://support.microsoft.com/contactus)
  * [Privacy](https://go.microsoft.com/fwlink/?LinkId=521839)
  * [Manage cookies](javascript:manageConsent\(\);)
  * [Terms of use](https://go.microsoft.com/fwlink/?LinkID=206977)
  * [Trademarks](https://go.microsoft.com/fwlink/?linkid=2196228)
  * [Safety & eco](https://go.microsoft.com/fwlink/?linkid=2196227)
  * [Recycling](https://www.microsoft.com/legal/compliance/recycling)
  * [About our ads](https://choice.microsoft.com)
  * © Microsoft 2026



  * [![Share to LinkedIn](https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/components/MicrosoftFooter/assets/social-share-linkedin.svg?time=1743177821000)Share on LinkedIn](https://www.linkedin.com/sharing/share-offsite/?url=https%3A%2F%2Ftechcommunity.microsoft.com%2Fblog%2Fappsonazureblog%2Fthe-agent-that-investigates-itself%2F4500073)
  * [![Share to Facebook](https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/components/MicrosoftFooter/assets/social-share-facebook.svg?time=1743177821000)Share on Facebook](https://www.facebook.com/share.php?u=https%3A%2F%2Ftechcommunity.microsoft.com%2Fblog%2Fappsonazureblog%2Fthe-agent-that-investigates-itself%2F4500073&t=Harness%20Engineering%20for%20Azure%20SRE%20Agent%3A%20Building%20the%20Agent%20Self-Improvement%20Loop)
  * [![Share to X](https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/components/MicrosoftFooter/assets/social-share-x.svg?time=1743177821000)Share on X](https://twitter.com/share?text=Harness%20Engineering%20for%20Azure%20SRE%20Agent%3A%20Building%20the%20Agent%20Self-Improvement%20Loop&url=https%3A%2F%2Ftechcommunity.microsoft.com%2Fblog%2Fappsonazureblog%2Fthe-agent-that-investigates-itself%2F4500073)
  * [![Share to Reddit](https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/components/MicrosoftFooter/assets/social-share-reddit.svg?time=1743177821000)Share on Reddit](https://www.reddit.com/submit?url=https%3A%2F%2Ftechcommunity.microsoft.com%2Fblog%2Fappsonazureblog%2Fthe-agent-that-investigates-itself%2F4500073&title=Harness%20Engineering%20for%20Azure%20SRE%20Agent%3A%20Building%20the%20Agent%20Self-Improvement%20Loop)
  * [![Share to Blue Sky](https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/components/MicrosoftFooter/assets/bluesky-brands.svg?time=1743697028000)Share on Bluesky](https://bsky.app/intent/compose?text=Harness%20Engineering%20for%20Azure%20SRE%20Agent%3A%20Building%20the%20Agent%20Self-Improvement%20Loop%21%20%F0%9F%A6%8B%0Ahttps%3A%2F%2Ftechcommunity.microsoft.com%2Fblog%2Fappsonazureblog%2Fthe-agent-that-investigates-itself%2F4500073)
  * [![Subscribe to RSS](https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/components/MicrosoftFooter/assets/rss.svg?time=1743177821000)Share on RSS](/t5/s/gxcuf89792/rss/Community)
  * [![Share to Email](https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/components/MicrosoftFooter/assets/social-share-email.svg?time=1743177821000)Share on Email](mailto:?body=https%3A%2F%2Ftechcommunity.microsoft.com%2Fblog%2Fappsonazureblog%2Fthe-agent-that-investigates-itself%2F4500073)



"}},"componentScriptGroups({\"componentId\":\"custom.widget.SocialSharing\"})":{"__typename":"ComponentScriptGroups","scriptGroups":{"__typename":"ComponentScriptGroupsDefinition","afterInteractive":{"__typename":"PageScriptGroupDefinition","group":"AFTER_INTERACTIVE","scriptIds":[]},"lazyOnLoad":{"__typename":"PageScriptGroupDefinition","group":"LAZY_ON_LOAD","scriptIds":[]}},"componentScripts":[]},"component({\"componentId\":\"custom.widget.MicrosoftFooter\"})":{"__typename":"Component","render({\"context\":{\"component\":{\"entities\":[],\"props\":{}},\"page\":{\"entities\":[\"message:4500073\"],\"name\":\"BlogMessagePage\",\"props\":{},\"url\":\"https://techcommunity.microsoft.com/blog/appsonazureblog/the-agent-that-investigates-itself/4500073\"}}})":{"__typename":"ComponentRenderResult","html":"

  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/surface/devices/surface-pro\" data-m=\"{"cN":"Footer_WhatsNew_SurfacePro_nav","id":"n1c1c1c1m1r1a2","sN":1,"aN":"c1c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/surface/devices/surface-laptop\" data-m=\"{"cN":"Footer_WhatsNew_SurfaceLaptop_nav","id":"n2c1c1c1m1r1a2","sN":2,"aN":"c1c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/d/Surface-Laptop-Studio-2/8rqr54krf1dz\" data-m=\"{"cN":"Footer_WhatsNew_SurfaceLaptopStudio2_nav","id":"n3c1c1c1m1r1a2","sN":3,"aN":"c1c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/microsoft-copilot/organizations?icid=DSM_Footer_CopilotOrganizations\" data-m=\"{"cN":"Footer_WhatsNew_CopilotOrganizations_nav","id":"n4c1c1c1m1r1a2","sN":4,"aN":"c1c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/microsoft-copilot/for-individuals?form=MY02PT&OCID=GE_web_Copilot_Free_868g3t5nj\" data-m=\"{"cN":"Footer_WhatsNew_CopilotPersonal_nav","id":"n5c1c1c1m1r1a2","sN":5,"aN":"c1c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/windows/ai-features?icid=DSM_Footer_WhatsNew_AIinWindows\" data-m=\"{"cN":"Footer_WhatsNew_AIinWindows_nav","id":"n6c1c1c1m1r1a2","sN":6,"aN":"c1c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/microsoft-products-and-apps\" data-m=\"{"cN":"Footer_WhatsNew_ExploreMicrosoftProducts_nav","id":"n7c1c1c1m1r1a2","sN":7,"aN":"c1c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/windows/apps-for-windows?icid=DSM_Footer_WhatsNew_Windows11apps\" data-m=\"{"cN":"Footer_WhatsNew_Windows11Apps_nav","id":"n8c1c1c1m1r1a2","sN":8,"aN":"c1c1c1m1r1a2"}\">



  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://account.microsoft.com/\" data-m=\"{"cN":"Footer_StoreandSupport_AccountProfile_nav","id":"n1c2c1c1m1r1a2","sN":1,"aN":"c2c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/download\" data-m=\"{"cN":"Footer_StoreandSupport_DownloadCenter_nav","id":"n2c2c1c1m1r1a2","sN":2,"aN":"c2c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://go.microsoft.com/fwlink/?linkid=2139749\" data-m=\"{"cN":"Footer_StoreandSupport_SalesAndSupport_nav","id":"n3c2c1c1m1r1a2","sN":3,"aN":"c2c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" id=\"footer-returns\" href=\"https://go.microsoft.com/fwlink/p/?LinkID=824764&clcid=0x809\" data-m=\"{"cN":"Footer_StoreandSupport_Returns_nav","id":"n4c2c1c1m1r1a2","sN":4,"aN":"c2c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/store/b/order-tracking\" data-m=\"{"cN":"Footer_StoreandSupport_OrderTracking_nav","id":"n5c2c1c1m1r1a2","sN":5,"aN":"c2c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/store/b/certified-refurbished-products\" data-m=\"{"cN":"Footer_StoreandSupport_CertifiedRefurbished_nav","id":"n6c2c1c1m1r1a2","sN":6,"aN":"c2c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/store/b/why-microsoft-store?icid=footer_why-msft-store_7102020\" data-m=\"{"cN":"Footer_StoreandSupport_MicrosoftPromise_nav","id":"n7c2c1c1m1r1a2","sN":7,"aN":"c2c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/store/b/payment-financing-options?icid=footer_financing_vcc\" data-m=\"{"cN":"Footer_StoreandSupport_Financing_nav","id":"n8c2c1c1m1r1a2","sN":8,"aN":"c2c1c1m1r1a2"}\">



  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/education\" data-m=\"{"cN":"Footer_Education_MicrosoftInEducation_nav","id":"n1c3c1c1m1r1a2","sN":1,"aN":"c3c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/education/devices/overview\" data-m=\"{"cN":"Footer_Education_DevicesforEducation_nav","id":"n2c3c1c1m1r1a2","sN":2,"aN":"c3c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/education/products/teams\" data-m=\"{"cN":"Footer_Education_MicrosoftTeamsforEducation_nav","id":"n3c3c1c1m1r1a2","sN":3,"aN":"c3c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/education/products/microsoft-365\" data-m=\"{"cN":"Footer_Education_Microsoft365Education_nav","id":"n4c3c1c1m1r1a2","sN":4,"aN":"c3c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/education/how-to-buy\" data-m=\"{"cN":"Footer_Education_HowToBuy_nav","id":"n5c3c1c1m1r1a2","sN":5,"aN":"c3c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://education.microsoft.com/\" data-m=\"{"cN":"Footer_Education_EducatorTrainingDevelopment_nav","id":"n6c3c1c1m1r1a2","sN":6,"aN":"c3c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/store/b/education\" data-m=\"{"cN":"Footer_Education_DealsForStudentsandParents_nav","id":"n7c3c1c1m1r1a2","sN":7,"aN":"c3c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/education/ai-in-education\" data-m=\"{"cN":"Footer_Education_AIinEducation_nav","id":"n8c3c1c1m1r1a2","sN":8,"aN":"c3c1c1m1r1a2"}\">



  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/ai?icid=DSM_Footer_AI\" data-m=\"{"cN":"Footer_Business_MicrosoftAI_nav","id":"n1c4c1c1m1r1a2","sN":1,"aN":"c4c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/security\" data-m=\"{"cN":"Footer_Business_MicrosoftSecurity_nav","id":"n2c4c1c1m1r1a2","sN":2,"aN":"c4c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/dynamics-365\" data-m=\"{"cN":"Footer_Business_MicrosoftDynamics365_nav","id":"n3c4c1c1m1r1a2","sN":3,"aN":"c4c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/microsoft-365/business\" data-m=\"{"cN":"Footer_Business_Microsoft365_nav","id":"n4c4c1c1m1r1a2","sN":4,"aN":"c4c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/power-platform\" data-m=\"{"cN":"Footer_Business_MicrosoftPowerPlatform_nav","id":"n5c4c1c1m1r1a2","sN":5,"aN":"c4c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/microsoft-teams/group-chat-software\" data-m=\"{"cN":"Footer_Business_MicrosoftTeams_nav","id":"n6c4c1c1m1r1a2","sN":6,"aN":"c4c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/microsoft-365-copilot?icid=DSM_Footer_Microsoft365Copilot\" data-m=\"{"cN":"Footer_Business_Microsoft365Copilot_nav","id":"n7c4c1c1m1r1a2","sN":7,"aN":"c4c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/store/b/business?icid=CNavBusinessStore\" data-m=\"{"cN":"Footer_Business_SmallBusiness_nav","id":"n8c4c1c1m1r1a2","sN":8,"aN":"c4c1c1m1r1a2"}\">



  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://azure.microsoft.com/\" data-m=\"{"cN":"Footer_Enterprise_MicrosoftAzure_nav","id":"n1c5c1c1m1r1a2","sN":1,"aN":"c5c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://developer.microsoft.com/\" data-m=\"{"cN":"Footer_Developer_DeveloperCenter_nav","id":"n2c5c1c1m1r1a2","sN":2,"aN":"c5c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://learn.microsoft.com/\" data-m=\"{"cN":"Footer_DeveloperAndIT_MicrosoftLearn_nav","id":"n3c5c1c1m1r1a2","sN":3,"aN":"c5c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/software-development-companies/offers-benefits/isv-success?icid=DSM_Footer_SupportAIMarketplace&ocid=cmm3atxvn98\" data-m=\"{"cN":"Footer_DeveloperAndIT_SupportAIMarketplace_nav","id":"n4c5c1c1m1r1a2","sN":4,"aN":"c5c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://techcommunity.microsoft.com/\" data-m=\"{"cN":"Footer_DeveloperAndIT_MicrosoftTechCommunity_nav","id":"n5c5c1c1m1r1a2","sN":5,"aN":"c5c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://marketplace.microsoft.com/?icid=DSM_Footer_Marketplace&ocid=cmm3atxvn98\" data-m=\"{"cN":"Footer_DeveloperAndIT_Marketplace_nav","id":"n6c5c1c1m1r1a2","sN":6,"aN":"c5c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/software-development-companies/offers-benefits/marketplace-rewards?icid=DSM_Footer_MarketplaceRewards&ocid=cmm3atxvn98\" data-m=\"{"cN":"Footer_DeveloperAndIT_MarketplaceRewards_nav","id":"n7c5c1c1m1r1a2","sN":7,"aN":"c5c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://visualstudio.microsoft.com/\" data-m=\"{"cN":"Footer_Developer_MicrosoftVisualStudio_nav","id":"n8c5c1c1m1r1a2","sN":8,"aN":"c5c1c1m1r1a2"}\">



  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://careers.microsoft.com/\" data-m=\"{"cN":"Footer_Company_Careers_nav","id":"n1c6c1c1m1r1a2","sN":1,"aN":"c6c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/about\" data-m=\"{"cN":"Footer_Company_AboutMicrosoft_nav","id":"n2c6c1c1m1r1a2","sN":2,"aN":"c6c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://news.microsoft.com/source/?icid=DSM_Footer_Company_CompanyNews\" data-m=\"{"cN":"Footer_Company_CompanyNews_nav","id":"n3c6c1c1m1r1a2","sN":3,"aN":"c6c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/privacy?icid=DSM_Footer_Company_Privacy\" data-m=\"{"cN":"Footer_Company_PrivacyAtMicrosoft_nav","id":"n4c6c1c1m1r1a2","sN":4,"aN":"c6c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/investor/default.aspx\" data-m=\"{"cN":"Footer_Company_Investors_nav","id":"n5c6c1c1m1r1a2","sN":5,"aN":"c6c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/diversity/default?icid=DSM_Footer_Company_Diversity\" data-m=\"{"cN":"Footer_Company_DiversityAndInclusion_nav","id":"n6c6c1c1m1r1a2","sN":6,"aN":"c6c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/accessibility\" data-m=\"{"cN":"Footer_Company_Accessibility_nav","id":"n7c6c1c1m1r1a2","sN":7,"aN":"c6c1c1m1r1a2"}\">
  * </li:i18n>\" class=\"c-uhff-link\" href=\"https://www.microsoft.com/sustainability/\" data-m=\"{"cN":"Footer_Company_Sustainability_nav","id":"n8c6c1c1m1r1a2","sN":8,"aN":"c6c1c1m1r1a2"}\">



[ California Consumer Privacy Act (CCPA) Opt-Out Icon ](\\"https://aka.ms/yourcaliforniaprivacychoices\\") [ ](\\"https://go.microsoft.com/fwlink/?linkid=2259814\\")

  * [](\\"https://www.microsoft.com/en-us/sitemap1.aspx\\")
  * [](\\"https://support.microsoft.com/contactus\\")
  * [](\\"https://go.microsoft.com/fwlink/?LinkId=521839\\")
  * [ ](\\"javascript:manageConsent\(\);\\")
  * [](\\"https://go.microsoft.com/fwlink/?LinkID=206977\\")
  * [](\\"https://go.microsoft.com/fwlink/?linkid=2196228\\")
  * [](\\"https://go.microsoft.com/fwlink/?linkid=2196227\\")
  * [](\\"https://www.microsoft.com/legal/compliance/recycling\\")
  * [](\\"https://choice.microsoft.com\\")
  * © 



  * [ </li:i18n>\" src=\"https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/components/MicrosoftFooter/assets/social-share-linkedin.svg?time=1743177821000\"> ](\\"https://www.linkedin.com/sharing/share-offsite/?url=page.url\\")
  * [ </li:i18n>\" src=\"https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/components/MicrosoftFooter/assets/social-share-facebook.svg?time=1743177821000\"> ](\\"https://www.facebook.com/share.php?u=page.url&t=page-name\\")
  * [ </li:i18n>\" src=\"https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/components/MicrosoftFooter/assets/social-share-x.svg?time=1743177821000\"> ](\\"https://twitter.com/share?text=page-name&url=page.url\\")
  * [ </li:i18n>\" src=\"https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/components/MicrosoftFooter/assets/social-share-reddit.svg?time=1743177821000\"> ](\\"https://www.reddit.com/submit?url=page.url&title=page-name\\")
  * [ </li:i18n>\" src=\"https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/components/MicrosoftFooter/assets/bluesky-brands.svg?time=1743697028000\"> ](\\"https://bsky.app/intent/compose?text=page-name%21%20%F0%9F%A6%8B%0Apage.url\\")
  * [ </li:i18n>\" src=\"https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/components/MicrosoftFooter/assets/rss.svg?time=1743177821000\"> ](\\"/t5/s/gxcuf89792/rss/Community\\")
  * [ </li:i18n>\" src=\"https://techcommunity.microsoft.com/t5/s/gxcuf89792/m_assets/components/MicrosoftFooter/assets/social-share-email.svg?time=1743177821000\"> ](\\"mailto:?body=page.url\\")



"}},"componentScriptGroups({\"componentId\":\"custom.widget.MicrosoftFooter\"})":{"__typename":"ComponentScriptGroups","scriptGroups":{"__typename":"ComponentScriptGroupsDefinition","afterInteractive":{"__typename":"PageScriptGroupDefinition","group":"AFTER_INTERACTIVE","scriptIds":[]},"lazyOnLoad":{"__typename":"PageScriptGroupDefinition","group":"LAZY_ON_LOAD","scriptIds":[]}},"componentScripts":[]},"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"components/community/NavbarDropdownToggle\"]})":[{"__ref":"CachedAsset:text:en_US-components/community/NavbarDropdownToggle-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"components/messages/MessageCoverImage\"]})":[{"__ref":"CachedAsset:text:en_US-components/messages/MessageCoverImage-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"shared/client/components/nodes/NodeTitle\"]})":[{"__ref":"CachedAsset:text:en_US-shared/client/components/nodes/NodeTitle-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"components/messages/MessageTimeToRead\"]})":[{"__ref":"CachedAsset:text:en_US-components/messages/MessageTimeToRead-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"components/messages/MessageSubject\"]})":[{"__ref":"CachedAsset:text:en_US-components/messages/MessageSubject-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"components/users/UserLink\"]})":[{"__ref":"CachedAsset:text:en_US-components/users/UserLink-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"shared/client/components/users/UserRank\"]})":[{"__ref":"CachedAsset:text:en_US-shared/client/components/users/UserRank-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"components/messages/MessageTime\"]})":[{"__ref":"CachedAsset:text:en_US-components/messages/MessageTime-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"components/messages/MessageBody\"]})":[{"__ref":"CachedAsset:text:en_US-components/messages/MessageBody-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"components/messages/MessageCustomFields\"]})":[{"__ref":"CachedAsset:text:en_US-components/messages/MessageCustomFields-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"components/messages/MessageRevision\"]})":[{"__ref":"CachedAsset:text:en_US-components/messages/MessageRevision-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"shared/client/components/common/QueryHandler\"]})":[{"__ref":"CachedAsset:text:en_US-shared/client/components/common/QueryHandler-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"components/tags/TagList\"]})":[{"__ref":"CachedAsset:text:en_US-components/tags/TagList-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"components/messages/MessageReplyButton\"]})":[{"__ref":"CachedAsset:text:en_US-components/messages/MessageReplyButton-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"components/messages/MessageAuthorBio\"]})":[{"__ref":"CachedAsset:text:en_US-components/messages/MessageAuthorBio-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"shared/client/components/users/UserAvatar\"]})":[{"__ref":"CachedAsset:text:en_US-shared/client/components/users/UserAvatar-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"shared/client/components/ranks/UserRankLabel\"]})":[{"__ref":"CachedAsset:text:en_US-shared/client/components/ranks/UserRankLabel-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"components/tags/TagView/TagViewChip\"]})":[{"__ref":"CachedAsset:text:en_US-components/tags/TagView/TagViewChip-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"components/users/UserRegistrationDate\"]})":[{"__ref":"CachedAsset:text:en_US-components/users/UserRegistrationDate-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"shared/client/components/nodes/NodeAvatar\"]})":[{"__ref":"CachedAsset:text:en_US-shared/client/components/nodes/NodeAvatar-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"shared/client/components/nodes/NodeDescription\"]})":[{"__ref":"CachedAsset:text:en_US-shared/client/components/nodes/NodeDescription-1774688898688"}],"cachedText({\"lastModified\":\"1774688898688\",\"locale\":\"en-US\",\"namespaces\":[\"shared/client/components/nodes/NodeIcon\"]})":[{"__ref":"CachedAsset:text:en_US-shared/client/components/nodes/NodeIcon-1774688898688"}]},"Theme:customTheme1":{"__typename":"Theme","id":"customTheme1"},"User:user:-1":{"__typename":"User","id":"user:-1","entityType":"USER","eventPath":"community:gxcuf89792/user:-1","uid":-1,"login":"Deleted","email":"","avatar":null,"rank":null,"kudosWeight":1,"registrationData":{"__typename":"RegistrationData","status":"ANONYMOUS","registrationTime":null,"confirmEmailStatus":false,"registrationAccessLevel":"VIEW","ssoRegistrationFields":[]},"ssoId":null,"profileSettings":{"__typename":"ProfileSettings","dateDisplayStyle":{"__typename":"InheritableStringSettingWithPossibleValues","key":"layout.friendly_dates_enabled","value":"false","localValue":"true","possibleValues":["true","false"]},"dateDisplayFormat":{"__typename":"InheritableStringSetting","key":"layout.format_pattern_date","value":"MMM dd yyyy","localValue":"MM-dd-yyyy"},"language":{"__typename":"InheritableStringSettingWithPossibleValues","key":"profile.language","value":"en-US","localValue":null,"possibleValues":["en-US","es-ES"]},"repliesSortOrder":{"__typename":"InheritableStringSettingWithPossibleValues","key":"config.user_replies_sort_order","value":"DEFAULT","localValue":"DEFAULT","possibleValues":["DEFAULT","LIKES","PUBLISH_TIME","REVERSE_PUBLISH_TIME"]}},"deleted":false},"CachedAsset:pages-1774688885990":{"__typename":"CachedAsset","id":"pages-1774688885990","value":[{"lastUpdatedTime":1774688885990,"localOverride":null,"page":{"id":"BlogViewAllPostsPage","type":"BLOG","urlPath":"/category/:categoryId/blog/:boardId/all-posts/(/:af

... [truncated]
