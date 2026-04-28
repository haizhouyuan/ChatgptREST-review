# Rejected Generic Patterns

> Worker: WP-D Design Reference Mapping
> Date: 2026-04-27
> Purpose: Document generic and templated design patterns that must NOT be used for Labebe, with explicit rejection conditions.

---

## Rejection Framework

A pattern is rejected if it meets any of these criteria:

1. **Logo-swap test**: If replacing the Labebe logo with any other toy brand logo makes the page still work, the pattern is too generic.
2. **Moodboard-only**: If the pattern describes a feeling ("warm," "premium") without specifying a commerce module, shopper mission, or conversion mechanism, it is a moodboard, not a pattern.
3. **Unverifiable claim carrier**: If the pattern requires fake reviews, fake certifications, fake awards, or unsupported safety claims to work, it is rejected per the Claim Gate.
4. **Template-default**: If the pattern is the default behavior of Shopify, WordPress, or a generic ecommerce starter template without Labebe-specific logic, it is rejected as under-designed.
5. **Asset-unbuildable**: If the pattern requires 3D assets, real video, or AR models that do not exist and have no credible path to existence within the sprint, it is rejected as unbuildable.
6. **Accessibility failure**: If the pattern looks impressive on desktop but breaks on mobile (390px/430px), it is rejected.
7. **AI gimmick**: If the pattern uses AI for decoration rather than decision support, content generation, or governance, it is rejected.

---

## Rejected Pattern Catalog

### R-1. Atmospheric-Only Hero

**What it is**: A full-bleed lifestyle image of a child's room with a headline like "Welcome to Wonder" and a "Shop Now" button. No products visible in the first viewport.

**Why it is rejected**:
- Fails the logo-swap test: could be any children's brand.
- Does not show product breadth. Parents landing from ads/SEO do not know what Labebe sells.
- Current Labebe prototype already fixed this partially, but the background still competes with product identity.

**Rejection Condition**: Reject any hero where the first viewport does not show at least 3 recognizable Labebe SKUs or product silhouettes. Reject if the CTA is generic "Shop Now" instead of a scenario route (age/room/occasion).

**What to use instead**: Product-Family Hero Signal (Pattern D-1) — real SKUs composed as a family with scenario CTAs.

---

### R-2. Rainbow Pastel UI

**What it is**: A color palette of bright primary colors (red, yellow, blue, green), heavy use of cartoon graphics, rounded bubbly shapes, and playful fonts.

**Why it is rejected**:
- Violates Labebe positioning: "Do not make the entire site a rainbow."
- Violates design principle: "Child wonder, adult taste." The site is for parents, not children.
- Fails the logo-swap test: could be any mass-market toy brand.
- Reduces price tolerance. Premium positioning requires muted, editorial tones.

**Rejection Condition**: Reject any design that uses more than 2 bright primary colors in the UI. Reject any cartoon graphic or illustration that is not product photography. Reject any font that reads as child-targeted (comic, rounded display).

**What to use instead**: Warm cream/oak/blush/sage palette with editorial photography and clean sans-serif body type.

---

### R-3. Generic Product Grid

**What it is**: A grid of product cards with image, title, price, and "Add to Cart" on a white background. No scenario context, no labels, no story.

**Why it is rejected**:
- Template-default: this is the unmodified Shopify collection template.
- Does not help parents choose. 46 SKUs in a grid without guidance is overwhelming.
- Fails the logo-swap test: could be any ecommerce store.
- Low conversion: grids without scenario context have lower click-through than story-driven layouts.

**Rejection Condition**: Reject any collection page that opens with a product grid without a scenario hero, "best for" labels, or filter system. Reject if cards are smaller than 280px wide on mobile.

**What to use instead**: Scenario-Before-Category Grid (Pattern D-2) with hero, filters, labels, and story lanes.

---

### R-4. Fake Review Stars

**What it is**: Product cards or PDPs showing 5-star ratings, "4.9 out of 5," or parent quotes that are generated or unsupported.

**Why it is rejected**:
- Violates Labebe Red Lines: "Do not fake reviews."
- Violates Claim Gate: unsupported review claims must be blocked.
- Destroys trust if discovered. Amazon review data is scraped but star averages are unreliable.
- Current prototype correctly removed fake reviews. Reintroducing them is a regression.

**Rejection Condition**: Reject any star rating that is not directly sourced from a verified review API with ASIN match confidence. Reject any parent quote that is not sourced from a real review with link. Reject if review count is shown as a star rating when only count is known.

**What to use instead**: Truth Drawer showing real review count (or null) with source label. Review signals ("18 reviews on Amazon") instead of star averages.

---

### R-5. Generic "Customers Also Bought"

**What it is**: A carousel of products labeled "Customers Also Bought" or "Related Products" with no logic connecting them to the current SKU.

**Why it is rejected**:
- Template-default: most ecommerce platforms show random related products.
- Often illogical: a rocker might show an unrelated puzzle.
- Does not raise AOV because there is no narrative reason to buy together.
- Fails the logo-swap test.

**Rejection Condition**: Reject if recommended products are not logically connected by room, scenario, or bundle logic. Reject if recommendations are the same for all PDPs. Reject if the carousel has more than 4 items.

**What to use instead**: Bundle Strip (Pattern 3.6) with "Complete the Set" logic based on room, world, or gift scenario.

---

### R-6. AI Chatbot Hero

**What it is**: A chatbot widget or conversational UI as the primary homepage interaction. "Ask me anything about Labebe products."

**Why it is rejected**:
- AI gimmick: chatbots in ecommerce have low engagement and high hallucination risk.
- Violates Labebe positioning: "Do not make the AI Growth Demo look like a simple chatbox."
- Adds latency and complexity without proven conversion lift.
- Parents prefer guided selection (age/room/occasion chips) over open-ended chat.

**Rejection Condition**: Reject any open-ended chat interface on the consumer site. Reject if AI interaction requires typing instead of tapping chips. Reject if chatbot claims to give personalized advice without deterministic logic.

**What to use instead**: AI Gift Finder (Pattern 1.3) with deterministic chips and transparent recommendation reasons.

---

### R-7. Decorative WebGL / 3D Objects

**What it is**: Animated 3D spheres, galaxies, abstract tech objects, or particle systems floating in the background.

**Why it is rejected**:
- AI gimmick: unrelated to product, choice, or workflow.
- Violates Labebe positioning: "Do not add meaningless tech animations (e.g., WebGL tech spheres)."
- Performance risk: slows load time, hurts mobile experience.
- Fails the logo-swap test: could be any tech startup.

**Rejection Condition**: Reject any WebGL or 3D element that is not a real product model (GLB/USDZ) or room-builder tool. Reject if the animation does not explain product, choice, or growth workflow.

**What to use instead**: Motion that serves the business: SKU card expansion, finder chip animation, cart drawer slide, room-set assembly.

---

### R-8. Generic SaaS Dashboard

**What it is**: The AI Growth Studio designed as a generic dark-mode dashboard with charts, metrics, and admin panels.

**Why it is rejected**:
- Fails the logo-swap test: could be any SaaS product.
- Violates Labebe positioning: AI Studio must be Labebe-specific (real SKUs, real channels, real product data).
- Abstract metrics ("AI efficiency score," "content velocity") are meaningless without product context.
- Looks like a tool, not a growth operating system.

**Rejection Condition**: Reject if the AI Studio shows generic charts or metrics not tied to real Labebe SKUs. Reject if the studio uses project-management vocabulary instead of creative-operations vocabulary. Reject if placeholders are non-Labebe products.

**What to use instead**: Linear-style workflow timeline + Raycast-style command center + Stripe Atlas-style process explainer, all anchored to real Labebe SKUs and channels.

---

### R-9. Scandinavian Origin Fake

**What it is**: Design that implies Scandinavian origin through copy ("Nordic design," "Danish inspired") or visual cues (minimalist furniture, specific typography).

**Why it is rejected**:
- Violates Labebe positioning: "Do not fake Scandinavian origin."
- Violates Claim Gate: unsupported origin claims are blocked.
- Misleading to consumers who associate Scandinavian origin with specific safety standards.
- Destroys trust if discovered.

**Rejection Condition**: Reject any copy or visual cue that implies Scandinavian origin without verified evidence. Reject if "Montessori" is used without explaining what it means for the product.

**What to use instead**: Honest material and design storytelling. If wood is sourced from a specific region, state it with evidence. If not, focus on function and safety.

---

### R-10. Fake Awards & Certifications

**What it is**: Badges like "Parent's Choice Award," "Safety Certified," "Best Toy 2025" without verified sources.

**Why it is rejected**:
- Violates Labebe Red Lines: "Do not fake awards." "Do not fake safety certifications."
- Violates Claim Gate: all certification claims require evidence.
- Legal risk: fake safety claims on children's products have regulatory consequences.
- Current prototype correctly removed these. Reintroducing them is a regression.

**Rejection Condition**: Reject any award badge without a source URL and verification date. Reject any safety certification without a certificate image and issuing body. Reject if badges are decorative and not clickable to evidence.

**What to use instead**: Truth Drawer showing what certifications are known and which are pending verification. Material transparency panel.

---

### R-11. Overly Dense Mega Menu

**What it is**: A navigation menu with 3+ columns, 20+ links, promotional banners, and imagery crammed into a dropdown.

**Why it is rejected**:
- Template-default: legacy retail sites (Pottery Barn Kids, big-box) use these out of catalog habit.
- Cognitive overload: parents cannot parse 20 links in a dropdown.
- Mobile nightmare: mega menus do not translate to mobile hamburger menus.
- Hides the scenario logic behind category density.

**Rejection Condition**: Reject if the nav dropdown has more than 8 links. Reject if the mobile menu requires more than 2 taps to reach any destination. Reject if promotional content is mixed into primary navigation.

**What to use instead**: Flat scenario navigation (Age, Room, Occasion, Play Goal) with clear sub-pages. Top utility bar for shipping/returns policy.

---

### R-12. Animated Fake ROI Numbers

**What it is**: Counters that animate up to fake metrics: "$1.2M saved," "500% conversion lift," "10x faster."

**Why it is rejected**:
- AI gimmick: decorative numbers that pretend to be real data.
- Violates Labebe positioning: "Avoid false precision. Do not claim saved hours, conversion uplift, or ROI without evidence."
- Fails the logo-swap test: could be any startup landing page.
- Undermines credibility when the real numbers are unknown.

**Rejection Condition**: Reject any animated number without a source and date. Reject any metric that claims improvement without a baseline measurement. Reject if metrics are shown in the consumer site.

**What to use instead**: Product Truth Panel showing real product data. Claim Gate showing blocked claims and safe rewrites.

---

### R-13. Generic "Our Story" Founder Narrative

**What it is**: A long text section about a fictional founder's journey, passion for children, and mission.

**Why it is rejected**:
- Violates Labebe Red Lines: "Do not fake founder story."
- Does not help conversion: founder stories are low-engagement on product sites.
- Fails the logo-swap test: could be any DTC brand.
- Evidence requirement: any founder story must be verifiable.

**Rejection Condition**: Reject any founder story without verifiable evidence. Reject if the story is longer than the product information. Reject if it appears above product content.

**What to use instead**: Product Truth Panel. Materials and safety transparency. Brand positioning through product, not personality.

---

### R-14. Contact Sheet as Video Cover

**What it is**: Using a grid of image thumbnails or a contact sheet as the cover image for a video.

**Why it is rejected**:
- Violates Labebe positioning: "Do not use contact sheets as video covers."
- Looks unprofessional and low-effort.
- Reduces click-through on video content.

**Rejection Condition**: Reject any video thumbnail that is a contact sheet, grid, or collage. Reject if the thumbnail does not show a single compelling frame.

**What to use instead**: Single hero frame from the video, or a storyboard card with clear labeling.

---

### R-15. Generic Testimonial Carousel

**What it is**: A carousel of quotes like "Best purchase ever! — Sarah M." with stock photos.

**Why it is rejected**:
- Violates Labebe Red Lines: "Do not fake reviews."
- Stock photos + first-name-only quotes are universally recognized as fake.
- Fails the logo-swap test.
- No conversion evidence: fake testimonials do not increase trust.

**Rejection Condition**: Reject any testimonial without a verifiable source (Amazon review link, verified purchase badge). Reject if testimonial uses stock photos. Reject if first name only.

**What to use instead**: Real review count with source. Truth Drawer. If real testimonials exist, show them with full attribution and source link.

---

### R-16. Unstructured Big-Best-Seller Grid

**What it is**: A homepage section with 8+ product cards in a grid labeled "Best Sellers" with no criteria, no scenario context, and no story.

**Why it is rejected**:
- Template-default: every ecommerce template has this.
- Without criteria, "Best Sellers" is meaningless. Best by what? Reviews? Revenue? Views?
- Fails the logo-swap test.
- Low engagement: grids without context are scrolled past.

**Rejection Condition**: Reject if "Best Sellers" lacks criteria. Reject if there are more than 6 products in the section. Reject if products are not organized by scenario or collection.

**What to use instead**: Four Worlds Story Lanes (Pattern 1.4) — scenario-driven collections with narrative context.

---

### R-17. Overly Minimalist SKU Hiding

**What it is**: A layout so minimal that only 1-2 products are visible per screen, requiring excessive scrolling to see variety.

**Why it is rejected**:
- Borrowed from Lalo, but Lalo has a narrow catalog. Labebe has 46 SKUs.
- Hides product breadth. Parents need to see variety to understand the brand.
- Low SEO value: minimal content reduces indexable text.
- Mobile friction: excessive scrolling on phone.

**Rejection Condition**: Reject if fewer than 3 products are visible above the fold on mobile. Reject if the homepage requires more than 4 scrolls to see product variety. Reject if collection pages show fewer than 4 products in the first viewport.

**What to use instead**: Clean but information-dense cards. Large product images with visible title, price, and label. Grid of 2 columns on mobile, 3-4 on desktop.

---

## Summary Rejection Matrix

| Pattern | Logo-Swap | Unverifiable | Template-Default | Asset-Unbuildable | Mobile-Break | AI Gimmick |
|---|---|---|---|---|---|---|
| Atmospheric-Only Hero | ✅ | | ✅ | | | |
| Rainbow Pastel UI | ✅ | | ✅ | | | |
| Generic Product Grid | ✅ | | ✅ | | | |
| Fake Review Stars | | ✅ | ✅ | | | |
| Generic "Also Bought" | ✅ | | ✅ | | | |
| AI Chatbot Hero | ✅ | | | | | ✅ |
| Decorative WebGL | ✅ | | | | ✅ | ✅ |
| Generic SaaS Dashboard | ✅ | | ✅ | | | |
| Scandinavian Origin Fake | | ✅ | | | | |
| Fake Awards/Certs | | ✅ | | | | |
| Overly Dense Mega Menu | ✅ | | ✅ | | ✅ | |
| Animated Fake ROI | | ✅ | ✅ | | | ✅ |
| Fake Founder Story | | ✅ | ✅ | | | |
| Contact Sheet Video Cover | | | ✅ | | | |
| Generic Testimonial Carousel | | ✅ | ✅ | | | |
| Unstructured Best-Seller Grid | ✅ | | ✅ | | | |
| Overly Minimalist SKU Hiding | ✅ | | | | ✅ | |

---

## Evidence Checklist

- [x] Every rejected pattern includes why it is rejected.
- [x] Every rejected pattern includes a rejection condition (when to discard).
- [x] Every rejected pattern includes what to use instead.
- [x] Patterns are categorized by rejection type.
- [x] No moodboard entries without business-problem mapping.
- [x] No Pro/Gemini calls made.
