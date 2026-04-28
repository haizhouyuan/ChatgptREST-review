# AI Show-Off Pattern Library

Scoring:

- Board impact: how likely this makes a decision maker feel AI is powerful.
- Commerce usefulness: how much it helps shopping, merchandising, or conversion.
- Feasibility: how realistic it is in the current React/Vite prototype.
- Risk: claim, trust, performance, or fake-demo risk.

## P0: Build First

| Rank | Pattern | What The Viewer Sees | Business Value | AI Capability Shown | Feasibility | Risk Control |
|---:|---|---|---|---|---|---|
| 1 | SKU Expansion Wall | Pink Unicorn card expands into PDP, TikTok, Amazon A+, Google, Email, Pinterest, Claim Gate cards | Shows one SKU becomes multi-channel growth assets | product-to-asset generation and workflow | High | all outputs labeled draft/review-ready |
| 2 | AI Gift Finder v2 | age + room + occasion produces three real SKUs with reasons and source labels | guided discovery and gift conversion | guided selling | High | deterministic rules first |
| 3 | Product Truth Drawer | any product card reveals price, review count, image source, unknown fields | trust and governance | grounded AI | High | source labels and unknown fields |
| 4 | Claim Gate Theater | unsafe draft claim is blocked, explained, and rewritten | prevents risky child/safety claims | AI review and governance | High | no fake approvals |
| 5 | PDP Storyboard Lens | PDP toggles from shopper mode to 15s video storyboard mode | turns PDP into content engine | product storytelling and video ideation | High | scripted/still storyboard, not fake final video |
| 6 | Boss Presentation Mode | 15-minute route with checkpoints, evidence, and transitions | executive storytelling | AI as operating system | High | fact/assumption labels |
| 7 | Channel Preview Simulator | same SKU shown as TikTok, Amazon, Google, Site, Email variants | clarifies platform adaptation | channel-specific creative | High | no fake performance metrics |
| 8 | Design Director Panel | reference cards show borrow/avoid/Labebe mapping | proves design thinking | AI-assisted design reasoning | High | cite references and avoid copying |
| 9 | Room Set Builder 2D | choose nursery/playroom/kitchen, products assemble into a room set | raises AOV and room-brand positioning | AI merchandising | Medium | product cutouts + static backgrounds |
| 10 | Product Data to SEO/FAQ Preview | product facts become FAQ/schema/content blocks | SEO and long-tail traffic | content automation from truth layer | High | only output supported fields |

## P1: Strong Upgrade

| Pattern | What The Viewer Sees | Business Value | AI Capability Shown | Feasibility | Risk Control |
|---|---|---|---|---|---|
| Scene Studio | product image -> three lifestyle scene prompts -> selected scene -> claim review | scalable product media ideation | image prompt generation | Medium | generated images labeled concept |
| Review/VOC to Product Concept | Learning Tower pain clusters -> concept card -> testing assets | product innovation loop | VOC synthesis | Medium | use sample/demo data labels |
| Playroom Reset Before/After | messy room scenario becomes room plan and product set | room-based merchandising | scene planning and bundle logic | Medium | avoid unrealistic render claims |
| Dynamic Gift Guide Builder | select recipient/occasion and build a shareable gift guide block | email/social/gift conversion | content assembly | High | deterministic data first |
| A+ Module Composer | product facts become Amazon A+ section wireframes | marketplace content leverage | channel adaptation | High | concept only unless Amazon approved |
| UGC Hook Lab | generate 5 hooks, rate risk, choose safe hook | short-video ideation | creative testing | High | no fake UGC identity |
| Product Comparison Advisor | compare two learning towers or rockers by real fields | decision confidence | structured comparison | High | hide unknown fields |
| Bundle Logic Map | one product suggests complementary SKU and reason | AOV and room set building | merchandising AI | High | source-backed products only |
| Search Intent Map | SEO cluster links to products and content pages | acquisition planning | search-to-content strategy | Medium | sources and volume labeled if estimated |
| Mobile Demo Path | swipeable executive demo on phone | board demo usability | storytelling UX | High | no heavy animations |

## P2: Wow But Higher Cost

| Pattern | Why It Is Attractive | Why It Is Risky | When To Build |
|---|---|---|---|
| 3D Product Viewer | impressive product inspection | needs real 3D assets; fake 3D weakens trust | after GLB/USDZ assets exist |
| AR Room Placement | high confidence for furniture fit | asset-heavy and mobile support burden | after P0/P1 and real dimensions |
| Three.js Interactive Room | strong visual wow | performance and asset workload | only with dedicated asset budget |
| Rive Workflow Animation | premium motion for claim/studio states | requires animation authoring | good for one small hero interaction |
| Real AI Backend Personalization | more authentic than static demo | privacy, hallucination, latency | only with product truth and guardrails |
| Live Image Generation in Site | dramatic | latency/cost/policy/product-consistency risk | behind internal demo mode |
| Auto Video Generation Preview | strong board wow | generated children/product consistency risk | use storyboard first |
| Voice Shopping Assistant | futuristic | consumer trust, accessibility, noisy demo | not for current sprint |

## The One Killer Interaction

Build:

> `SkuGrowthLens`

Route:

> `/ai-growth-demo/one-sku` and homepage overlay

Interaction:

1. Viewer clicks Pink Unicorn Plush Rocker in hero.
2. Product facts slide in: price $109.99, 18 reviews, collection, image source.
3. The SKU card enlarges and the page darkens into studio mode.
4. Seven channel cards fan out:
   - PDP story module;
   - TikTok 15s hook;
   - Amazon A+ hero;
   - Google Shopping lifestyle image prompt;
   - email gift guide block;
   - Pinterest pin;
   - claim gate.
5. Each card includes a real preview snippet and a status:
   - Draft;
   - Needs review;
   - Review-ready;
   - Blocked.
6. Toggling "Show governance" draws lines from product facts to asset claims.

Why this is the right memorable moment:

- it is visible in 10 seconds;
- it uses a real SKU;
- it shows AI power without fake metrics;
- it connects design, commerce, content, and governance;
- it can be built with current data and generated/static images.

## Homepage v3 Modules

1. Product-family hero with `SkuGrowthLens` overlay.
2. AI Gift Finder v2 with recommendation reasons.
3. Four product worlds as story lanes, not plain cards.
4. One SKU Expansion Wall.
5. Room Set Builder teaser.
6. PDP Storyboard teaser.
7. Design Director proof strip.
8. Claim Gate proof strip.

## Things To Avoid

- AI chatbot as hero.
- Abstract "AI magic" without a product.
- Fake animated ROI numbers.
- Fake reviews or star ratings.
- Unverified safety/certification claims.
- Overly decorative 3D.
- Generic SaaS dashboard language.
- Too much text in the first viewport.
- Making AI Studio the "About" page.
- Designing for desktop only.
