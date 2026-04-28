## 1. Overall judgment

结论很直接：**这是正确的 reset，但还不是足够锋利的执行方案。**

正确之处是边界终于清楚了：Labebe 网站应是纯消费者 DTC replacement site；AI Product Matrix、Boss Demo、Paperclip、AI Studio 属于另一个项目，最多作为内部演示或方案呈现辅助，不应默认进入消费者网站。这个边界在 `04_WEBSITE_DESIGN_RESEARCH_BRIEF.md` 已经写清楚：网站项目被定义为 pure Labebe DTC replacement，AI demo / product matrix / Paperclip / boss-showroom 是 separate projects（`04_WEBSITE_DESIGN_RESEARCH_BRIEF.md:5`）。`01_SOURCE_REGISTRY.yaml` 也把“把消费者 DTC 网站和 AI demo 混在一起”列为不可接受证据/错误边界（`01_SOURCE_REGISTRY.yaml:14-19`）。

但概念上仍然弱在三点：

第一，**计划知道“要从产品出发”，但还没有定义“产品证据如何转化成设计决策”。** 现在字段很多、crawl 很多、option 很多，但缺少一个明确的 decision model：什么证据决定 hero SKU？什么证据决定导航按年龄、房间、礼物还是产品线？什么证据决定 PDP 需要尺寸优先、故事优先、评论优先还是套装优先？如果没有这个中间层，下一轮仍可能把数据当 appendix，把设计继续做成漂亮模板。

第二，**设计选项看似 5 个，实际有重叠风险。** Growth-Space Home Brand、Room Builder / Playroom Reset、Pretend Play Editorial Worlds 都可能落回“温暖儿童房 + 产品卡片 + 圆角模块”的同一种页面语法。Gift/Milestone 更像一个强 landing strategy，不一定是完整网站架构。Product Theater 如果不严格约束，会重新滑回“老板演示感”，而不是消费者 DTC。

第三，**Amazon intelligence 被放对了位置，但危险也被低估了。** 计划已经承认 Amazon 目前只有 1 个 ASIN 样本、13 条去重 review，且没有 SKU-to-ASIN map、listing facts、rank、competitor set（`02_CURRENT_ARTIFACT_AUDIT.md:48-63`）。这意味着 Amazon 现在只能作为方法种子，不能作为任何产品优先级或网站定位依据。尤其本地 Amazon review CSV 里可见 US marketplace 字段下混入 Japan review 日期/内容，这说明 actor 输出需要市场、语言、review pool 严格拆分，不能直接做 VOC 结论。

整体判断：**先做产品/channel intelligence，再做产品驱动的多方案设计，是对的；但现在要把“计划型文档”升级成“证据—判断—设计—验收”的硬流程。**

---

## 2. Product intelligence methodology critique

### 2.1 目标字段：方向对，但不够

`00_MASTER_PLAN.md` 里的 schema 已覆盖 identity、pricing、onsite signal、Amazon identity、Amazon demand、reviews/VOC、PDP detail、media、design relevance、evidence（`00_MASTER_PLAN.md:186-201`）。这是合格骨架，但还不是高标准 DTC / Amazon intelligence schema。

必须新增或细化这些字段：

**DTC / 独立站侧：**

- `product_id` / Shopify 或站点内部 ID，如果可提取。
- `variant_id`、`variant_sku`、颜色/尺寸/款式选项、variant price。
- `availability`、库存状态、backorder / sold out 状态。
- `seo_title`、`meta_description`、canonical URL、structured data / JSON-LD。
- `breadcrumb`、collection membership，不只是首个 collection。
- `shipping_policy_signal`、return/warranty copy、free-shipping threshold。
- `package_dimensions`、product weight、assembled dimensions、included parts。
- `assembly_time`、assembly difficulty、care/cleaning。
- `manual_pdf`、instruction image/video，如果存在。
- `age_min`、`age_max`、warning label、certification claim source。
- `onsite_review_text`，不能只拿 review count。
- `pdp_module_order`：PDP 上每段内容出现顺序，这会直接影响设计。
- `cta_state`、payment options、promo bar、trust badges。
- `image_alt_text`、image filename、image role、是否重复图、是否尺寸图/场景图/包装图/信息图/儿童使用图。

**Amazon 侧：**

- `parent_asin` / `child_asin`，并标明 review 是否 parent-level 混合。
- `variation_theme`，例如颜色、样式、尺寸。
- `model_number`、UPC/GTIN/EAN，如果 listing 或 product details 可见。
- `brand_byline`、brand store link、seller、ships_from、sold_by、buy_box_owner。
- `FBA/Prime`、delivery promise、stock/availability。
- `list_price`、deal price、coupon、promotion text，且全部标注抓取时间。
- `rating_distribution`，不是只有平均 rating。
- `review_velocity`：近 30/90/180 天 review 数，哪怕只是弱 proxy。
- `review_media_count`：带图/视频 review 数。
- `Q&A`：问题数量、核心问题主题。
- `A+ content_modules`：是否有品牌故事、对比表、场景图、尺寸图。
- `product_details`：dimensions、weight、date first available、manufacturer。
- `BSR_category_path`，不能只保留 rank 数字。
- `competitor_asins_by_category`，每个类别至少定义对标组。
- `content_quality_score`：Amazon listing 图片、标题、bullet、A+ 的强弱。

**设计侧字段：**

现在的 `hero_candidate_score`、`visual_distinctiveness`、`room_scene_potential`、`gift_scene_potential` 是好方向，但太主观。要拆成可审计的 scoring：

- `demand_signal_score`
- `asset_readiness_score`
- `category_anchor_score`
- `pdp_fact_completeness_score`
- `review_voc_usefulness_score`
- `bundle_potential_score`
- `risk_score`
- `hero_eligibility_reason`
- `hero_disqualification_reason`

否则“Pink Unicorn Plush Rocker review count 18”很容易被误解成“它一定是首页 hero”。本地数据只能说明它在独立站 scrape 里 review count 最高，不能自动说明它是商业最强 SKU。

### 2.2 Sample-first crawl plan：方向正确，但样本选择偏乐观

Sample-first 是对的。`03_SAMPLE_CRAWL_BRIEF.md` 要求先做 3–5 个 dossier，不允许直接 crawl 全部 46 个产品（`03_SAMPLE_CRAWL_BRIEF.md:5-9`），这是正确的纪律。

但当前样本过于偏“设计想用的好产品”：Unicorn、Play Kitchen、Learning Tower、Montessori Shelf、Activity Cube/ASIN sample。它们适合做设计，但不一定适合暴露抓取和 mapping 难题。

样本应调整为 **6–8 个 stratified sample**，不要只做漂亮样本：

1. 一个高 onsite review 的视觉 hero 候选：Pink Unicorn Plush Rocker。
2. 一个 pretend-play 高图量产品：Cream 或 Midnight play kitchen。
3. 一个 learning tower 变体族：log / white / gray / unicorn 至少选一个，并检查是否属于同一 Amazon variation family。
4. 一个近似重复家具 SKU：两个 desk/chair set 名称高度相似，必须验证是否重复、变体、还是不同产品。
5. 一个低/无 onsite review 但价格和功能重要的产品：例如某个 activity 或 furniture item。
6. 一个 Amazon 样本 ASIN `B087P9SXZQ`，但前提是先验证它到底对应哪个 Labebe 独立站 SKU；本地 Amazon productName 看起来像 baby push walker / doll stroller / shopping cart，不应默认等同于 `activity-cube-baby-push-walker`。
7. 一个可能没有 Amazon 官方匹配的产品，用来测试 no-match 流程。
8. 一个数据异常样本：例如 CSV 与 image JSON slug 不一致的 `children-s-writing...` / `childrens-writing...` 问题。

本地数据里已经暴露了几个 sample 必须覆盖的技术问题：

- `labebe_products.csv` 的 `image_url` 全部为空，但 `local_image_path` 有绝对路径。
- `labebe_products_with_images.csv` 反而 `local_image_path` 全部为空。
- `all_product_images.json` 与 CSV 至少有一个高评论家具产品 slug 不一致：`children-s-writing...` vs `childrens-writing...`。
- `original_price` 大量缺失，尽管 raw title 里常含第二个价格。
- title 中混入 `NEW!`、`HOT`、折扣、价格、review count、`labebe®`。

这些不是小问题。它们说明 full crawl 前必须先做 **data integrity repair**，不是直接进入 Amazon。

### 2.3 Amazon data 优先级

Amazon 侧不应一上来抓大量 review。正确顺序是：

1. **ASIN identity / ownership verification first**  
   先确认产品是不是同一产品、是否官方 Labebe、是否 seller/brand 合理、是否 parent/child variation 混合。没有这个，review 和 rank 都可能污染。

2. **Current listing facts**  
   title、brand、seller、fulfilled_by、price、availability、rating、review count、image、bullets、A+、variation。这个决定它能否被用于网站 copy、PDP reassurance、竞品对比。

3. **Demand proxies**  
   BSR、category path、rank history、bought-past-month、review velocity。全部必须标注“proxy”，不能当 sales。

4. **Review / VOC**  
   先按 marketplace、language、date、star rating、verified purchase 拆分，再提炼主题。不要把日本评论和美国评论混成一个美国 VOC。

5. **Competitor context**  
   每个 Labebe category 至少建立 5–10 个 competitor ASIN seed，但要先定义对标口径：同价位、同功能、同年龄段、同材质/视觉、同 channel 位置。否则 competitor set 会变成搜索噪音。

6. **Amazon content gap**  
   看 Labebe listing 在 title、image、A+、review reassurance、尺寸图、assembly 方面输给谁。这比单纯 BSR 更能指导 DTC PDP 设计。

### 2.4 最可能的技术陷阱与错误结论

**陷阱一：把 review count 当 demand。**  
Onsite review count 很小，最高也只是本地 scrape 中的 18。Amazon review count 也可能跨变体、跨时间、跨 marketplace。只能作为弱信号。

**陷阱二：把 BSR 当绝对销量。**  
BSR 只在 category 内相对有效，跨类目不可直接比较。learning tower、plush rocker、play kitchen、storage shelf 的 rank 不能放在同一条轴上比较。

**陷阱三：ASIN 误匹配。**  
Labebe 产品名称和 Amazon 标题可能不一致；同款可能有老 ASIN、变体 ASIN、reseller listing、下架 listing、非官方 listing。必须有 accepted / probable / candidate / rejected / no-match 五种状态，而不是 binary match。

**陷阱四：Amazon review actor 输出污染。**  
本地 `amazon_reviews_US_B087P9SXZQ.csv` 显示 marketplace 字段为 US，但包含 Japan review 内容。说明 actor 结果必须拆分 review region/language/source，不然 VOC 会被污染。

**陷阱五：图片数量不等于图片质量。**  
`all_product_images.json` 有 459 个 image URL，本地 scrape report 说下载了 460 张图片（`labebe-scrape-report-2026-04-24.md:8-13`），但这些图片没有 role classification。28 张图也可能全是重复角度或信息图；7 张图也可能足够强。必须分类。

**陷阱六：当前 scrape script 不是 PDP intelligence script。**  
`scrape_labebe.py` 主要靠 collection 页面中的 `Quick add` anchor 提取产品，title/price/review 都从列表文本里 regex 解析。它没有系统提取 PDP 描述、规格、FAQ、JSON-LD、variant、media role。因此它只能做 inventory seed，不是产品事实源。

**陷阱七：本地“完成”报告容易误导。**  
报告里的完成是“46 产品 + 图片下载完成”（`labebe-scrape-report-2026-04-24.md:58-60`），不是“产品 intelligence 完成”。这一点计划已指出，但 acceptance criteria 还要更硬。

### 2.5 应删除、增加、重排

**删除或降级：**

- 删除 Phase 1/2 里过早的时间承诺。Amazon method、anti-bot、SP-API/Keepa/Apify 可用性未验证前，时间目标会制造假确定性。
- 删除 consumer site 里的 AI teaser、AI Growth Studio、one-SKU matrix 作为默认网站模块。它们可以进入另一个 demo 或 presentation appendix。
- 不要把 Product Theater 默认列为“网站方向”，除非它被重新定义为纯产品/场景/购物 theater，而不是 AI matrix theater。

**增加：**

- `data_integrity_qa.md`：字段缺失、slug mismatch、CSV mismatch、image join failure、parse failure。
- `asin_match_scoring.md`：匹配规则和阈值。
- `source_snapshot`：关键 listing/PDP 的文本快照或截图/HTML 摘要。
- `review_market_language_split.csv`。
- `demand_proxy_policy.md`：哪些 signal 可以说，哪些不能说。
- `design_decision_matrix.csv`：每个设计决策对应哪条产品证据。
- `asset_readiness_audit.csv`：哪些产品能上首页，哪些需要补拍/重制图。

**重排：**

1. 先修 product master 和 image gallery join。
2. 再做 DTC PDP sample enrichment。
3. 再做 ASIN discovery / confidence model。
4. 再抓 Amazon listing facts。
5. 再抓 review / BSR / competitor。
6. 再做 design implication。
7. 最后做 visual design options。

现在的计划把这些都列了，但顺序上还不够“防错”。

---

## 3. Website design research critique

### 3.1 是否正确分离 pure DTC 和 AI demo？

方向正确，但文档内部仍有旧污染。

`04_WEBSITE_DESIGN_RESEARCH_BRIEF.md` 已经明确分离（`04_WEBSITE_DESIGN_RESEARCH_BRIEF.md:5`）。但 prior research 仍大量围绕 AI Growth Studio、SKU Expansion Wall、Claim Gate、Channel Preview、Boss Presentation Mode。这些材料可以保留给 AI demo 项目，但不应继续作为 consumer site 的默认设计语法。

消费者网站可以有：

- gift finder；
- room finder；
- comparison guide；
- PDP reassurance；
- bundle builder；
- product story modules；
- video / usage story；
- structured product truth behind copy。

消费者网站不应默认有：

- AI Studio；
- claim gate theater；
- channel asset matrix；
- boss mode；
- Paperclip runtime；
- internal source drawer；
- “one SKU expands into TikTok/Amazon/Google/email”的工作流展示。

这些东西对老板演示有价值，但会破坏消费者购买路径。

### 3.2 提出的 design options 是否足够不同？

不够。现在的 A/B/C/D/E 是不同“主题”，还不是不同“网站架构”。

`04_WEBSITE_DESIGN_RESEARCH_BRIEF.md` 要求至少四个不同方向，且不能只是换色（`04_WEBSITE_DESIGN_RESEARCH_BRIEF.md:47-50`）。但 A、C、D 仍可能共用同一套：

- warm cream background；
- room scene hero；
- product cards；
- age/room/gift chips；
- editorial section；
- PDP story module。

要真正不同，每个 option 至少要在这些维度上不同：

- primary shopper intent；
- information architecture；
- first viewport grammar；
- PDP persuasion model；
- collection page logic；
- mobile path；
- visual density；
- product merchandising priority；
- conversion mechanism；
- asset requirements。

现在的 options 更像“同一个 Labebe DTC 站的五个 landing modes”。这不够。

### 3.3 缺失的产品驱动设计方向

至少缺五个方向：

**方向一：Spec-confidence furniture site**  
Labebe 很多产品不是纯玩具，而是家具/learning tower/desk/storage。家长需要知道尺寸、稳定性、年龄、材料、组装、清洁、房间适配。这个方向不是“温暖”，而是“买得放心”。PDP 应像 furniture decision page：尺寸图、房间比例、assembly clarity、what fits where。

**方向二：Choice-clarity / comparison-led site**  
本地目录里有多个 plush rocker、多个 learning tower、多个 desk/storage 近似产品。顶级网站必须帮用户做选择：为什么买 unicorn 而不是 llama？为什么选 foldable tower 而不是 white/gray/unicorn tower？为什么两个 desk/chair set 都存在？如果不解决这个，产品越多越像杂货铺。

**方向三：Bundle / set merchandising site**  
Play kitchen + bakery food；shelf + storage bins；desk + stool；room reset set；gift bundle。计划提到了 bundle，但低估了它作为 DTC 区别于 Amazon 的核心价值。Amazon 卖单品，DTC 应该卖场景、套装、房间和礼物解决方案。

**方向四：Trust-after-Amazon site**  
很多用户可能先在 Amazon 看过 Labebe，再回 DTC。DTC 网站必须回答：为什么不在 Amazon 买？这里有什么更完整的信息、更好的套装、更清楚的尺寸、更好的品牌故事、更好的售后/礼物体验？计划目前偏“设计美感”，不够“渠道反击”。

**方向五：Product-world taxonomy site**  
不是泛泛的 Montessori，而是 Labebe 自己的 product worlds：Giftable Rockers、Kitchen Helpers、Pretend Play Worlds、Playroom Reset、Study & Art Corners、Outdoor Mud/Garden Play。每个 world 应有不同页面节奏、不同 PDP emphasis、不同 cross-sell。

### 3.4 顶级 DTC Labebe 网站目前被低估的部分

**PDP 比 homepage 更重要。**  
之前设计失败可能表现在 homepage，但消费者买不买主要死在 PDP：尺寸不清、年龄不清、材料/安全不敢写、组装不清、产品差异不清、图片不够真实、移动端 CTA 不顺。计划列了 PDP，但没有把它放到足够核心的位置。

**导航不是菜单，是品牌战略。**  
如果导航只是 “Shop / Furniture / Rockers / Pretend Play”，那还是 catalog。Labebe 需要让用户按真实购买意图进入：Age、Room、Gift、Play Goal、Product Type、Problem。最终选择哪一个作为第一层导航，必须由产品 intelligence 决定。

**DTC 不能只比 Amazon 好看。**  
它要比 Amazon 更会解释产品、更会组合、更会讲场景、更会处理礼物、更会回答家长担忧。

**视觉高级感来自产品 specificity，不来自暖色。**  
产品的真实比例、木材/布料质感、儿童使用场景、家庭空间尺度、收纳前后对比、组装细节，才是 Labebe 的高级感。再多 cream/sage/blush 都不能替代这些。

**移动端不能只是缩小。**  
Gift path、quick comparison、sticky buy box、尺寸图、review/VOC reassurance、bundle add-on 都要单独设计。`04_WEBSITE_DESIGN_RESEARCH_BRIEF.md` 已把 mobile purchase path 列入验收（`04_WEBSITE_DESIGN_RESEARCH_BRIEF.md:147-148`），但后续要变成具体交互，不只是截图。

---

## 4. Presentation / video critique

### 4.1 视频 walkthrough 有用，但只能用于决策，不应变成炫技

视频有用。原因是之前的问题不只是页面静态不好看，而是老板/决策者看不出“为什么这样设计、比普通 DTC 强在哪里”。视频可以把 product intelligence → design decision → shopper journey 串起来。

但视频最容易犯三个错：

1. 用生成视觉掩盖产品证据不足。
2. 用电影感掩盖购买路径弱。
3. 把 AI demo 又塞回消费者网站。

所以视频必须是 **business decision walkthrough**，不是 mood film。

### 4.2 应展示什么，才能说服业务决策者？

必须展示这些：

- **当前问题：** 不是“旧站丑”，而是产品层级、购买路径、PDP 证据、渠道差异不清。
- **产品 intelligence wall：** 46 个产品按真实 category / price / review / image readiness / Amazon match status 聚类。
- **hero SKU 选择逻辑：** 为什么某产品能上 first viewport，为什么某产品不能。
- **三条真实 shopper path：**
  - gift buyer：first birthday / grandparent gift → gift guide → PDP → cart；
  - parent utility buyer：learning tower / desk / storage → comparison → PDP dimensions → cart；
  - room/play buyer：playroom reset / pretend play world → set/bundle → PDP → cart。
- **desktop scale：** 证明不是窄窄的 warm Shopify theme。
- **mobile speed：** 证明手机上能快速选、看尺寸、加购。
- **PDP before/after：** Amazon VOC 或 DTC PDP gap 如何转化成 FAQ、尺寸、assembly、gift reassurance。
- **asset requirement：** 哪些产品可用现有图，哪些必须补拍，哪些只能用 AI concept 做 presentation。
- **推荐方向与 fallback：** 不要只展示五个漂亮方向，要明确建议选哪个，为什么。

### 4.3 不应展示什么？

不要展示：

- AI Studio、Paperclip、Boss Demo、Product Matrix 作为消费者网站模块。
- 未验证的 safety、certification、developmental claims。
- 假 review、假 star rating、假 sales number、假 ROI。
- 大量 raw crawl 表格。
- 过多工具名：Apify、Keepa、SP-API、Playwright、FFmpeg 不应该成为老板视频主体。
- 与真实产品不一致的 AI 生成儿童/家庭场景。
- 过长的 cinematic opening。
- 五个方向都做成完整视频。最多 1 个推荐方向做完整 walkthrough，1 个 fallback 做短 walkthrough，其余用 concept board。

---

## 5. Acceptance criteria critique

当前 acceptance criteria 方向正确，但不够硬。`00_MASTER_PLAN.md` 的验收要求包括 sample dossier、ASIN confidence、method comparison、source tagging、4 个设计概念、desktop/mobile、reference mapping、recommended direction（`00_MASTER_PLAN.md:389-419`）。这还不够。

### 5.1 Product intelligence 必须新增的验收

**Data integrity gate：**

- 46 个产品必须全部存在于 `product_master.csv`。
- 每个产品必须有唯一 `canonical_product_id`。
- CSV slug、image JSON slug、PDP URL 必须 100% join，不能有静默丢失。
- dirty title 必须拆成 `raw_title`、`canonical_title`、`badges`、`price_text`、`review_count_text`。
- 每个字段必须有 `source_id`、`source_type`、`last_seen_at`、`confidence`。
- `unknown` 必须显式保留，不能空白或自动填充。

**PDP enrichment gate：**

- 每个样本 PDP 至少提取：description、bullets、dimensions、age、materials、assembly/care、FAQ、warnings、variant、images、structured data；没有就标 unknown。
- 所有 safety / material / certification claims 必须有原文 source snippet。
- 图片必须分类，不能只计数。

**ASIN match gate：**

- 必须有 scoring model，例如：
  - title similarity；
  - image similarity；
  - brand evidence；
  - seller/brand store；
  - model/variant match；
  - price/category plausibility；
  - conflict flags。
- `verified` 才能进入 design/business claims。
- `probable` 只能进入 research，不可进入消费者 copy。
- `candidate` 不可用于 VOC 或 demand conclusion。
- `rejected` 必须保留原因。

**Review/VOC gate：**

- review 必须按 marketplace、language、star、date、verified purchase 拆分。
- 主题必须带 sample size。
- quote 必须带 review ID / URL。
- 不允许只摘漂亮 quote。
- 负面主题必须进入 PDP reassurance 或 product risk，不可只做 marketing。

**Demand proxy gate：**

- BSR、review count、bought-past-month、rating、rank history 都必须标注 proxy level。
- 不允许跨 category 直接排序。
- 不允许从 review count 推 sales volume。
- 不允许把 Amazon signal 直接映射成 DTC priority，除非有清楚解释。

### 5.2 Design acceptance 必须新增的验收

每个设计 option 必须通过以下硬测试：

- **Replaceability test：** 把 Logo 换成任意儿童品牌后还成立吗？如果成立，失败。
- **Product specificity test：** 首屏是否能看出 Labebe 真实产品结构，而不是儿童房氛围？
- **Decision logic test：** 为什么这个 hero、这个 nav、这个 PDP module 排序？必须能追溯到 product intelligence。
- **PDP usefulness test：** 用户能否判断年龄、尺寸、材料/安全、组装、使用场景、价格价值、配套产品？
- **Mobile conversion test：** 手机上从进入页面到 PDP 到加购是否少摩擦？
- **Desktop authority test：** 大屏是否有尺度、节奏、产品墙/场景/编辑感，而不是窄卡片堆叠？
- **Claim safety test：** 任何 safety/material/developmental copy 是否有 source？
- **Asset realism test：** 方案需要的图/视频是否真实可得？AI concept 是否被标注为 concept？
- **Implementation test：** 是否能落地到当前 commerce stack，而不是只适合 Figma/视频？

### 5.3 即使视觉好看，我也会拒绝下一版的情况

我会直接拒绝以下设计：

- 看起来像高级版 warm Montessori template，但没有 Labebe-specific product hierarchy。
- 首页漂亮，但 PDP 仍然不能回答尺寸、年龄、组装、材料、安全、差异。
- hero 用了“最漂亮产品”，但没有证据说明它应当占首屏。
- 产品卡片统一漂亮，却没有解决多个相似 SKU 的选择困难。
- 移动端只是 desktop 缩小。
- 桌面端仍然窄、空、软，没有商业权威感。
- 使用 AI 生成场景让产品看起来像拥有不存在的摄影资产。
- 把 AI Studio / Matrix / claim gate 放进消费者网站。
- 依赖假 review、假 sales、假认证、假儿童发展 claims。
- 方案只讲视觉 mood，不讲 conversion mechanism。

---

## 6. Revised recommended plan

### Phase 0：Scope purge + data QA baseline

**目标：** 先把项目边界和现有数据质量清理干净。

**Deliverables：**

- `scope_boundary.md`  
  明确 pure DTC website 与 AI demo / Boss Demo / Paperclip 的边界。
- `current_data_qa.md`  
  记录 CSV mismatch、slug mismatch、image_url 空值、dirty title、PDP 缺失、Amazon 样本污染。
- `product_master_v0.csv`  
  只收录可靠字段：slug、raw title、canonical title、collection、price、onsite review count、PDP URL、gallery count、data issues。
- `do_not_use_fields.md`  
  标出现在不能用于设计或 copy 的字段，例如未验证材料、安全、年龄、认证、Amazon match。

**Gate：**

- 46 个产品必须全部可唯一识别。
- product rows 与 image gallery 必须能 join。
- 明确哪些字段是 inventory seed，哪些字段是 factual evidence。

---

### Phase 1：DTC PDP sample enrichment

**目标：** 先证明 Labebe 官方 PDP 事实能被可靠提取。

**Sample：** 6–8 个，覆盖 hero、高图量、低/无 review、变体、重复/近似 SKU、数据异常、Amazon 样本。

**Deliverables：**

- `sample_product_dossiers/*.md`
- `pdp_facts_sample.csv`
- `image_role_sample.csv`
- `pdp_extraction_errors.csv`
- `field_coverage_report.md`

**必须包含：**

- PDP copy；
- bullets；
- dimensions；
- materials；
- age；
- assembly/care；
- FAQ；
- warnings；
- variants；
- JSON-LD；
- image roles；
- unknown fields。

**Gate：**

- 每个 factual claim 有 source snippet。
- 每个 unknown 被显式标出。
- 图片 role classification 可复用到 full run。

---

### Phase 2：Amazon identity and listing sample

**目标：** 先解决“是不是同一个产品”的问题，再谈 review/rank。

**Deliverables：**

- `asin_candidates_sample.csv`
- `asin_match_scoring.md`
- `amazon_listing_facts_sample.csv`
- `method_comparison.md`
- `amazon_source_limitations.md`

**必须比较：**

- Amazon direct/manual validation；
- Apify listing/review actor；
- Keepa 或 rank/history path，如果可用；
- SP-API，如果有 credentials；
- search discovery 只能做 lead，不能做 final evidence。

**Gate：**

- 每个 accepted ASIN 有 confidence label。
- parent/child variation 状态明确。
- seller/brand/officialness 不清楚的 listing 不进入 design-facing conclusions。
- 明确默认 full-run 方法与 fallback 方法。

---

### Phase 3：Full product/channel intelligence run

**目标：** 把 46 个 DTC 产品全部变成 design-ready product intelligence，不只是 crawl 表。

**Deliverables：**

- `product_master_v1.csv`
- `pdp_facts_full.csv`
- `image_roles_full.csv`
- `asin_match_full.csv`
- `amazon_listing_facts_full.csv`
- `reviews_voc_full.csv`
- `demand_proxy_full.csv`
- `competitor_asins_by_category.csv`
- `crawl_errors.csv`
- `source_cards_updated.tsv`

**Gate：**

- 每个产品有 Amazon status：verified / probable / candidate / rejected / no-match / unavailable。
- 每个 Amazon-matched product 至少有 listing fact + one demand proxy 或明确 unavailable。
- 所有 design-facing claims source-tagged。
- review/VOC 不混 marketplace/language。

---

### Phase 4：Insight synthesis before design

**目标：** 把数据转成网站战略，而不是把数据放进 appendix。

**Deliverables：**

- `category_portfolio_map.md`  
  哪些 category 是核心、辅助、弱势、待补证。
- `hero_candidate_matrix.csv`  
  每个 hero candidate 的证据、风险、所需资产。
- `navigation_decision_matrix.md`  
  是否按 age / room / gift / play goal / product type 做主导航。
- `pdp_module_strategy_by_category.md`  
  不同品类的 PDP 顺序和重点。
- `bundle_and_cross_sell_map.csv`
- `voc_to_pdp_reassurance.md`
- `asset_gap_list.md`

**Gate：**

- 先批准 IA / hero strategy / PDP strategy，再做视觉。
- 不能直接从 moodboard 跳到 homepage mockup。

---

### Phase 5：Divergent design concepts

**目标：** 做真正不同的网站方案，而不是同一模板换主题。

建议改成这些更清晰的方向：

1. **Gift-first Labebe**  
   首屏就是 gift decision，服务 birthday / grandparent / holiday / baby shower。强 rockers、push walker、giftable items。

2. **Home-fit Furniture Labebe**  
   规格、尺寸、房间适配、组装、家长信任优先。强 learning tower、desk、shelf、storage。

3. **Child-sized Worlds Labebe**  
   Pretend play、kitchen、shop、laundry、garden，以 story worlds 和视频/场景为核心。

4. **Playroom Reset Labebe**  
   收纳、秩序、房间组合、bundle、before/after。强 storage、shelf、desk、room sets。

5. **Object-led Product Theater Labebe**  
   更大胆，但必须是纯 DTC：真实产品大尺度、scroll choreography、产品世界切换、清晰购买路径。不能出现 AI Matrix。

**每个 option deliverables：**

- positioning；
- target shopper；
- IA；
- homepage wire；
- collection wire；
- PDP wire；
- mobile journey；
- hero SKU rationale；
- conversion mechanism；
- required assets；
- risk；
- why this is not generic；
- what evidence supports it。

**Gate：**

- 选 1 个 primary，1 个 fallback。
- 不要同时推进 5 个完整 implementation。

---

### Phase 6：Prototype + decision video

**目标：** 让业务决策者看到“这不是漂亮主题，而是有证据的商业网站”。

**Deliverables：**

- desktop key screens；
- mobile key screens；
- clickable prototype；
- 60–90 秒推荐方向 walkthrough；
- 30 秒 fallback walkthrough；
- evidence appendix；
- asset procurement list；
- implementation backlog。

**Video structure：**

1. Current problem。
2. Product intelligence wall。
3. Chosen design strategy。
4. Shopper path 1：gift。
5. Shopper path 2：furniture/spec。
6. Shopper path 3：room/bundle。
7. PDP proof。
8. Mobile proof。
9. Decision：recommendation、risk、next build scope。

**Gate：**

- 视频不得比原型更强。也就是说，不能靠剪辑掩盖页面本身弱。
- AI-generated media 必须标 concept，不可伪装成真实产品照片。

---

### Phase 7：Implementation backlog

**目标：** 把设计转成可上线任务，而不是停留在 mockup。

**Deliverables：**

- P0 launch scope；
- P1 content/asset scope；
- PDP component spec；
- collection/filter spec；
- mobile sticky buy box spec；
- SEO/schema/Merchant Center task list；
- analytics event map；
- QA checklist；
- copy claims approval list；
- photography / video / AI concept asset plan。

**Gate：**

- P0 必须能上线为真实 DTC replacement，不依赖 AI demo。
- AI demo 另建路线、另建验收。

---

## 7. Follow-up questions

1. 下一步执行 sample crawl 时，Amazon 侧可用哪些来源：Apify token、Keepa、SP-API、还是只能 manual/direct validation？

2. Labebe 真实上线目标是 Shopify/现有独立站改造，还是先做 React/Vite 高保真原型？这会影响设计 component、PDP、cart、checkout 的边界。

3. 本轮 pure DTC 网站优先优化哪一个商业目标：gift conversion、家具/learning tower 信任转化、room/bundle AOV，还是品牌高级感重建？

4. 产品图片/视频资产是否只有当前 scrape 的 gallery，还是还有未打包的真实摄影、UGC、Amazon A+、说明书、包装图可用？
