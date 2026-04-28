---
title: "Labebe运营系统设计"
source: "https://chatgpt.com/c/69ef1df6-38b8-83e8-8dea-5e8348d05d9a"
author:
published:
created: 2026-04-27
description: "ChatGPT conversation with 2 messages"
tags:
  - "clippings"
---
**You said**

\# External Advisor Prompt You are an external advisor for a single-user AI work operating system and Labebe business demo program. Please answer in Chinese. Do not act as a narrow auditor. The user wants constructive, critical, open-ended thinking. You may disagree with the current plan and propose a better one. ## Context The user is building a Paperclip-managed execution system for AI work. The first major case is Labebe, a children's toy / furniture / playroom brand. There are two frontstage deliverables: 1. \*\*Pure Labebe DTC Website Prototype\*\* - A consumer-facing replacement independent-site prototype. - No AI Studio inside it. - No Paperclip board inside it. - No internal product matrix inside it. - Goal: stronger shopping experience, trust, brand, bundles, mobile, PDP and conversion. 2. \*\*Labebe AI Application Wow / Boss Gallery\*\* - A decision-maker-facing demo. - Shows how AI can turn product facts/VOC/assets into concepts, short-video ideas, marketing assets, claim gates and evidence-backed workflows. - Paperclip is backstage evidence/governance, not the frontstage story. There is also a shared evidence layer: - Labebe product catalog and DTC crawl. - Amazon / marketplace product intelligence. - public brand image/video/ad asset library. - VOC / claim / source ledger. - design decision matrices. The user has repeatedly rejected shallow website iterations. The problem is not merely style polish. The website designs felt generic because product facts, portfolio judgment, design references, channel intelligence and IA/PDP decisions were not strong enough. ## Current Hypothesis Paperclip should be the control plane: - orgs; - projects; - issues; - agents; - evidence artifacts; - approval gates; - claim/risk gates; - runtime governance. Possible first-level orgs: 1. Labebe Growth Studio. 2. AI Runtime Governance. 3. Multica Archive. Possible later projects: - Skill Foundry. - Browser and Vision Lab. - Product Intelligence. - Website Design Lab. - Boss Gallery. GStack should be mined for lightweight gate patterns: - CEO / wow review; - design review; - browser QA; - CSO / MCP policy; - ship / checkpoint. AgencyAgents should be mined only for role-card structure. Multica should be archived for lessons, not revived as the main control plane. ## Your Task Give a practical decision memo. Please cover: 1. \*\*Reframe the real job.\*\* Beneath the tool names, what is the user actually trying to build? 2. \*\*Challenge the current plan.\*\* What is overbuilt, underbuilt, slow, vague or likely to drift? 3. \*\*Redesign the operating model.\*\* What should the Paperclip org/project/issue tree be now? What should be cut or delayed? 4. \*\*Protect Labebe execution speed.\*\* How should product intelligence, Amazon crawling, media asset acquisition, design research, website prototyping and AI Wow demos run without blocking each other? 5. \*\*Define the missing middle layer.\*\* What exactly must connect product facts to website design decisions? 6. \*\*Define the evidence model.\*\* What artifacts prove progress? What should never count as done? 7. \*\*Define essential gates.\*\* Which gates are mandatory, advisory, or overhead right now? 8. \*\*Use GStack / AgencyAgents / Multica correctly.\*\* What should be extracted, ignored, or forbidden? 9. \*\*Plan the first two weeks.\*\* Give an exact sequence of work, with visible artifacts. 10. \*\*Propose the next 10 Paperclip issues.\*\* Include title, owner/role, acceptance criteria and evidence artifacts. 11. \*\*Decision points for the user.\*\* What must the human decide now, and what can wait until after prototypes? 12. \*\*Final recommendation.\*\* Give a direct recommendation, including what not to do next. ## Response Requirements - Be concrete. - Avoid generic advice like "improve governance" unless you define the artifact/gate/owner. - Separate facts from the packet, your inferences and any external knowledge you use. - If you think the plan is too complex, say so plainly and give a simpler alternative. - If you think the current org structure is wrong, redraw it. - If you think Labebe should move faster with less governance, say exactly what governance to defer. - Do not answer with acknowledgement only. - Target answer length: at least 5,000 Chinese characters if possible.

---

**ChatGPT said**

我会先把上传包作为事实来源快速拆解，再把问题重构为“执行系统 + Labebe 首案交付”的决策备忘录，重点落到组织树、证据层、关卡、两周节奏和下一批 Paperclip issues。

## 先给一句不客气的总判断

这套计划现在最大的问题不是 Paperclip 组织不够完整，也不是 Labebe 网站还不够漂亮，而是你正在同时证明三件事：**Labebe 商业判断能力、AI 执行系统能力、运行时治理能力**。如果不强行降维，前两周会再次滑向“做了很多看起来正确的治理与页面”，但没有形成一个能让人相信的商业作品。

我的建议很直接：

**Paperclip 现在要建，但只能建成一个轻量执行控制核；Labebe 要快跑；Runtime Governance 只能服务 Labebe，不能反过来把 Labebe 拖进平台建设。**

---

# 0. 信息边界：哪些是包内事实，哪些是我的判断

## 来自 packet 的事实

这些是我从你提供的材料中采用为事实的内容：

| 类别                              | 包内事实                                                                                                                                                                   |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 前台交付物                           | 有两个前台交付物：纯 Labebe DTC 网站原型；Labebe AI Application Wow / Boss Gallery。两者必须分开。                                                                                            |
| 共享证据层                           | 共享层包括 Labebe 产品目录、DTC crawl、Amazon / marketplace intelligence、公共品牌图片/视频/广告资产、VOC / claim / source ledger、design decision matrices。                                     |
| DTC 网站边界                        | DTC 原型里不能放 AI Studio、Paperclip board、内部产品矩阵。目标是购物体验、信任、品牌、bundle、移动端、PDP、转化。                                                                                           |
| AI Wow 边界                       | AI Wow 面向决策者，展示 AI 如何把产品事实、VOC、资产转成概念、短视频想法、营销资产、claim gates 和 evidence-backed workflows。Paperclip 是后台证据与治理。                                                           |
| 现有 Labebe 数据                    | 当前本地 DTC crawl 有 46 个产品、46 个 product galleries、459 个 indexed image URLs、460 张本地下载图片；分类包括 furniture、rockers / ride-ons、pretend-play、activity / educational toys、new-in。 |
| 数据缺口                            | 存在 dirty titles、CSV/image join mismatch、PDP fields 不完整、没有完整产品详情、没有媒体角色分类、没有视频资产库、没有 verified SKU-to-ASIN map、Amazon sample review 可能混合 marketplace/language。           |
| 当前 Wow Demo                     | 已有 `labebe_wow` baseline，包括 `index.html`、`boss_video.html`、MP4、contact sheet，并且 HTTP 检查通过；它应作为 AI 应用 outcome demo baseline，而不是 DTC 网站。                                 |
| 关键修正                            | 之前 Pro 反馈中最重要的修正是：不能只 crawl 更多数据和做更多设计选项，必须建立硬中间层：`product facts -> portfolio judgment -> design decision matrix -> IA/PDP/homepage choices -> design options`。        |
| GStack / AgencyAgents / Multica | GStack 只应抽 gate / QA / checkpoint / security pattern；AgencyAgents 只应抽 role-card 结构；Multica 应归档经验，不应复活为主控制平面。                                                           |

## 我的推断

这些是基于 packet 的顾问判断，不是 packet 原文事实：

1. 当前计划仍然偏重“系统完整性”，不够偏重“Labebe 首案的决策速度”。
2. 现在建 5 个 org 会增加协调噪音，不会提高产出质量。
3. Skill Foundry、Browser and Vision Lab、Multica Archive 如果现在都作为一等 org，会制造平台感，而不是商业结果。
4. 真正缺的不是更多爬虫字段，而是一个可以把字段翻译成网站结构、PDP 模块、bundle 逻辑、claim 权限、视觉方向的 **Commerce Decision Layer**。
5. 两周内最有价值的成果不是“完整治理体系”，而是一个 evidence-backed Labebe decision wall、一个纯 DTC primary/fallback prototype、一个 claim-gated Boss Gallery v0。
6. AI Runtime Governance 现在只能有“阻断重大风险”的权力，不能因为文档、skill lifecycle、browser architecture 还没完就阻止 Labebe 继续。

## 外部知识

本备忘没有引入新的外部网页事实。所有具体事实来自你提供的 packet；其余是产品、增长、AI workflow、DTC 原型和治理设计方面的推理。

---

# 1. 重新定义真正的工作

不要把这件事理解成：

> “用 Paperclip 管一些 AI agent，然后做 Labebe 网站和 demo。”

更准确的定义是：

> **你在建立一个单人可控的 AI 商业执行系统。它必须证明：AI 不只是生成页面和报告，而是能在证据、判断、设计、原型、QA、claim gate 和交付叙事之间形成可靠闭环。Labebe 是第一个校准样本。**

这件事下面其实有三层：

## 第一层：商业结果层

Labebe 必须产出两类前台作品：

1. **纯 DTC 网站原型**
   给消费者看，像一个真正可以替代现网站的品牌购物体验。

2. **AI Boss Gallery**
   给老板、客户、决策者看，证明 AI 可以帮助品牌做产品机会识别、概念生成、营销资产、短视频脚本、claim gate、证据链。

这里的成败标准不是“有没有页面”，而是：

* 是否看起来不像泛泛儿童品牌模板；
* 是否能解释为什么这个 hero、这个导航、这个 PDP 顺序、这个 bundle 逻辑合理；
* 是否能让决策者相信 AI 提升了商业判断和产出速度；
* 是否没有把未证实的安全、材料、销量、review、certification claim 写进成品。

## 第二层：证据到设计的决策层

这才是目前最缺的层。

你已经知道要收集：

* 产品 facts；
* Amazon / marketplace intelligence；
* 图片视频资产；
* VOC；
* claim/source ledger；
* design decision matrices。

但真正要解决的是：

> 哪些 facts 改变网站架构？
> 哪些 VOC 改变 PDP 模块顺序？
> 哪些资产决定 hero SKU？
> 哪些 risk 让一个漂亮方向被淘汰？
> 哪些 category roles 决定 navigation？
> 哪些产品适合 gift、trust、bundle、room、premium brand rebuilding？

没有这个层，后面的设计仍然会变成“更精致的温暖儿童品牌模板”。

## 第三层：Paperclip 执行控制层

Paperclip 的角色不是让前台显得智能，也不是把 GStack、AgencyAgents、Multica 都接起来。

Paperclip 现在应该做四件事：

1. **定义 work tree**：谁在做什么，属于哪个 frontstage 或 shared evidence。
2. **绑定 evidence**：每个完成声明必须指向 artifact。
3. **管理 gates**：哪些 work 可以继续，哪些必须停。
4. **保持 handoff**：下一个 agent 不用读完整聊天记录也能继续。

Paperclip 此刻不是“完整 AI 操作系统”。它是 Labebe 首案的 **evidence-backed execution kernel**。

---

# 2. 挑战当前计划：哪里过建、欠建、变慢、容易漂移

## 2.1 过建的地方

| 过建点                                    | 为什么危险                                            | 建议                                      |
| -------------------------------------- | ------------------------------------------------ | --------------------------------------- |
| 现在就建 5 个 org                           | 会把注意力分散到平台治理、skill、browser、Multica，而不是 Labebe 结果 | 现在只建 2 个 active org；Archive 只读          |
| Skill Foundry 独立 org                   | skill governance 会变成写日志和生命周期分类游戏                 | 先作为 Runtime 里的一个 lightweight project    |
| Browser and Vision Lab 独立 org          | browser / vision R&D 很容易占满两周，但不会直接改善 Labebe 网站判断 | 只保留 Visual QA / Browser QA gate，不做大架构对比 |
| Multica Archive and Migration 独立活跃 org | 会把旧系统的 backlog 重量搬到 Paperclip                    | 只做 read-only archive，最多一个 issue         |
| GStack gate 全部正式化                      | gate 太早变成流程，会压慢 Labebe                           | 先抽 5 个 gate template；只有少数 mandatory     |
| Boss Gallery A-F 全量扩张                  | 六个 demo 很容易每个都浅                                  | 前两周做 A-F skeleton，但重点打磨 2-3 个最强 demo    |

## 2.2 欠建的地方

| 欠建点                       | 后果                                | 必须补的 artifact                        |
| ------------------------- | --------------------------------- | ------------------------------------ |
| 产品组合判断                    | 46 个产品只是列表，不是商业组合                 | `category_portfolio_map.md`          |
| hero SKU 选择机制             | hero 仍靠直觉或美图                      | `hero_candidate_matrix.csv`          |
| PDP 结构策略                  | 网站会只重 homepage，不重转化               | `pdp_module_strategy_by_category.md` |
| shopper mission           | 礼物买家、家具信任买家、playroom 规划买家的路径会混在一起 | `shopper_mission_map.md`             |
| claim 权限                  | AI 生成 copy 会不小心写出未证实 claim        | `claim_permission_matrix.csv`        |
| asset readiness           | 视觉方向可能依赖不存在的视频/照片                 | `asset_gap_list.md`                  |
| design reference 到商业问题的映射 | moodboard 会泛化                     | `reference_pattern_mapping.md`       |
| rejected options 记录       | 设计会反复走回老路                         | `rejected_direction_log.md`          |

## 2.3 变慢的地方

当前计划可能在这些地方变慢：

1. **Amazon 工作被 review scraping 诱惑拖走**
   正确顺序应该是：ASIN identity → listing facts → demand proxies → review/VOC。
   没有 SKU-to-ASIN confidence，就不要把 review 当 VOC 证据。

2. **媒体资产获取变成无边 crawl**
   前两周只需要 sample asset readiness，不需要完整资产库。
   每个资产必须记录 source URL、capture time、hash、context、usage caveat。

3. **Runtime Governance 把 Labebe 当试验田**
   Runtime 只能提供必要 gates；不能要求 Labebe 等完整 MCP matrix、machine topology、skill lifecycle。

4. **五个网站方向被做成五个完整页面**
   五个 architecture options 应该先是决策级 concept boards，不是五个完整站点。最后只做一个 primary、一个 fallback。

5. **Boss Gallery 过早做视频包装**
   视频不能比原型强。先让 demo card 有内容、有证据、有 claim gate，再做 walkthrough。

## 2.4 最危险的漂移点

| 漂移点                        | 早期信号                                                               | 阻断动作                               | 证据要求                                                                 |
| -------------------------- | ------------------------------------------------------------------ | ---------------------------------- | -------------------------------------------------------------------- |
| 1. DTC 网站又做回 AI Studio     | 页面里出现 Paperclip board、AI matrix、agent process、internal evidence UI | 立即触发 Scope Separation Gate         | `scope_boundary.md` + 页面截图确认无 AI/Paperclip 模块                        |
| 2. Paperclip 变成前台故事        | Boss Gallery 第一屏讲 workflow，而不是 Labebe outcome                      | CEO/Wow gate 要求重写 first 30 seconds | `ceo_wow_review.md` 写明 first 30s business result                     |
| 3. 网站仍然泛化                  | 替换 logo 后可以变成任何儿童品牌                                                | Design Decision Gate 不通过           | 每个页面模块必须绑定 product/category/VOC/asset evidence                       |
| 4. Amazon VOC 污染           | reviews 混 marketplace、language、date、verified status                | ASIN Identity Gate 阻断 VOC 使用       | `asin_match_scoring.md` + `reviews_voc_split_report.csv`             |
| 5. Visual QA 变成截图归档        | 有截图但没人判断 hierarchy、premium feel、mobile friction                    | Design Review Gate 要求评分和 top fixes | `design_review_report.md` + desktop/mobile screenshots               |
| 6. Skill governance 变成日志游戏 | agent 记录很多 skill usage，但没有 skill 修正、废弃或复用                          | Skill ledger 暂停扩展                  | 只有 repeated failure 才开 skill update issue                            |
| 7. Multica 复活成新控制面         | 开始迁移大量历史 issue、讨论旧 assistant blueprints                            | Archive Gate 阻断                    | 只允许 `lessons.md`、`do_not_count_as_success.md`、classification summary |

---

# 3. 重画 operating model：现在应该怎么建 Paperclip

## 3.1 现在不要建 5 个活跃 org

我建议现在只建：

```text
Active Org 1: Labebe Commercial Studio
Active Org 2: Paperclip Runtime & Evidence Kernel
Read-only Area: Multica Archive / Pattern Library
```

如果 Paperclip 技术上必须用 org 承载 Archive，可以建第三个 org，但它必须是 read-only / archive，不进入两周 sprint 的 active lane。

## 3.2 新 org / project / issue tree

### Org 1：Labebe Commercial Studio

这是业务产出 org，不叫 Growth Studio 也可以，关键是它要覆盖 product intelligence、commerce strategy、website、Boss Gallery。

| Project                           | 目标                                                              | 两周内是否 active           |
| --------------------------------- | --------------------------------------------------------------- | ---------------------- |
| `00_scope_and_source_registry`    | 固定 DTC / Boss Gallery / evidence layer 边界；登记来源                  | 是                      |
| `01_product_channel_intelligence` | 产品 master、PDP facts、ASIN identity、marketplace sample、VOC sample | 是                      |
| `02_public_media_asset_library`   | 公共图片/视频/广告资产 sample、asset role、scene index、usage caveat         | 是                      |
| `03_commerce_decision_layer`      | 把 facts 转成 portfolio、IA、PDP、bundle、hero、claim decisions         | 是，核心                   |
| `04_pure_dtc_prototype`           | primary + fallback 高保真 DTC 原型                                   | 是，但等 decision layer v0 |
| `05_ai_boss_gallery`              | AI Application Wow / Boss Gallery A-F                           | 是，但用 claim gate 控制     |
| `06_executive_pack`               | 最终给老板看的 one-pager、walkthrough、evidence appendix                 | 第 2 周末 active          |

### Org 2：Paperclip Runtime & Evidence Kernel

这是轻量平台 org，不是完整 governance 大项目。

| Project                       | 目标                                                                  | 两周内范围        |
| ----------------------------- | ------------------------------------------------------------------- | ------------ |
| `00_issue_evidence_contract`  | 定义 closeout、checkpoint、evidence manifest                            | 必做，1 天内完成 v0 |
| `01_gate_kernel`              | 抽 GStack-derived gates：scope、evidence、claim、design、browser、closeout | 必做 v0，不完美也能用 |
| `02_runtime_policy_thin_gate` | 只处理 secrets、browser profile、MCP/CLI/skill 权限风险                      | 必做最小版        |
| `03_visual_browser_qa`        | 截图集、mobile QA、console / link / flow check                           | 必做可执行模板      |
| `04_skill_stewardship_lite`   | 只记录 blocking skill failures，不做完整 lifecycle                          | 延迟或轻量        |
| `05_fresh_agent_review`       | 对关键 artifact 做新鲜 agent review                                       | 第二周后半启用      |

### Read-only Area：Multica Archive / Pattern Library

| Project                       | 目标                                                                 | 规则           |
| ----------------------------- | ------------------------------------------------------------------ | ------------ |
| `multica_lessons_only`        | 保存 read-only、no-write、proof ledger、issue-done-not-product-done 等经验 | 不迁移大量 issue  |
| `failed_fixtures_archive`     | 标注 cancelled smoke fixtures 不算成功证据                                 | 只读           |
| `future_assistant_blueprints` | Finbot / Education / specialist contracts 等未来再说                    | 不进入当前 sprint |

## 3.3 哪些东西现在不要进入 Paperclip

| 不进入项                                 | 原因                                                                     |
| ------------------------------------ | ---------------------------------------------------------------------- |
| 全部 GStack runtime                    | 会模糊 Paperclip 控制权，并带来 telemetry / update / routing / state mutation 风险 |
| AgencyAgents 大量 persona files        | 会制造角色幻觉，不会提高 Labebe 结果                                                 |
| Multica 117 个历史 issue                | 会把旧 backlog 噪音搬进新系统                                                    |
| 完整 machine topology program          | 重要但不是 Labebe 两周成果前置条件                                                  |
| conversation-wide skill usage mining | 噪音大，不影响 Labebe 首案                                                      |
| 完整 browser architecture comparison   | 除非当前 crawl / QA 被 blocker 卡住                                           |
| 五个完整 DTC 站点实现                        | 应先做五个 architecture boards，再做 primary/fallback                          |
| Amazon full review crawl             | 没有 ASIN identity 前会污染 VOC                                              |

---

# 4. 如何保护 Labebe 执行速度

核心原则：

> **Labebe 可以绕过大部分平台治理，但不能绕过 scope、evidence、claim、browser/visual QA 和 closeout。**

## 4.1 并行工作协议

| Lane                    | 可立即开始                                                                 | 依赖                                      | 不能阻塞谁                             |
| ----------------------- | --------------------------------------------------------------------- | --------------------------------------- | --------------------------------- |
| Product Intelligence    | tool/method probe、product master QA、6-8 SKU sample                    | 只依赖 source registry 和 evidence contract | 不等 Runtime 完整治理                   |
| Amazon / Marketplace    | ASIN candidate、identity scoring、listing facts sample                  | 依赖 product master v0 和 SKU sample       | 不等 full crawl                     |
| Media Asset             | public media probe、video scene index、asset manifest                   | 依赖 source registry                      | 不等 PDP sample 完成                  |
| Design Research         | reference pattern mapping、commerce pattern library                    | 可与 product sample 并行                    | 不能直接进入 final visual design        |
| Commerce Decision Layer | portfolio、hero、navigation、PDP、bundle、claim matrices                   | 依赖 sample facts + asset readiness       | 是 high-fi DTC 前置                  |
| DTC Prototype           | wire-level skeleton 可早做；high-fi primary/fallback 要等 decision layer v0 | 依赖 Design Decision Gate                 | 不等 full product intelligence      |
| AI Boss Gallery         | 可基于现有 `labebe_wow` baseline 做 A-F skeleton                            | 依赖 claim ledger 和 evidence labels       | 不等 DTC 网站完成                       |
| Runtime Governance      | gate templates、evidence contract、thin runtime policy                  | 1 天内给 v0                                | 不能因为未完成 skill lifecycle 阻塞 Labebe |

## 4.2 Runtime Governance 什么时候可以阻止 Labebe

只能在以下情况阻止：

1. DTC 网站混入 AI Studio / Paperclip / internal product matrix。
2. 页面或 demo 使用未证实安全、材料、certification、销量、review、market demand claim。
3. Amazon VOC 还没有 ASIN identity confidence。
4. 原型要展示给用户/老板，但没有 desktop/mobile screenshot、browser QA、claim scan。
5. 工具变更涉及 secrets、browser cookie/session、写权限、外部 API key 暴露风险。
6. issue 要标记 done，但没有 evidence manifest 和 known limitations。

其他情况都不能阻止，只能 advisory。

## 4.3 什么 governance 可以绕过

Labebe 前两周可以绕过：

* 完整 skill lifecycle registry；
* AgencyAgents role-card extraction；
* full MCP/CLI/skill architecture matrix；
* machine topology inventory；
* full no-write smoke；
* historical conversation skill mining；
* complete browser harness comparison；
* Pro review before every step；
* full Multica migration。

这些都可以在 prototype 之后补。

---

# 5. 缺失的中间层：Commerce Decision Layer

我建议正式命名为：

```text
Labebe Commerce Decision Layer
```

它是共享 evidence layer 和前台设计之间的翻译器。

## 5.1 输入

| 输入                    | 来源                                                                                     |
| --------------------- | -------------------------------------------------------------------------------------- |
| Product facts         | DTC PDP、JSON-LD、collection、product images、manuals if found                             |
| Category membership   | 当前 crawl + collection mapping                                                          |
| Images / video assets | product galleries、public pages、social/ad surfaces if accessible                        |
| Amazon identity       | ASIN candidates、match scoring、listing facts                                            |
| Marketplace signals   | price、availability、rating、review velocity、A+ content、competitor context where feasible |
| VOC                   | only after ASIN confidence and marketplace/language split                              |
| Claim source          | PDP text、official source、marketplace listing、review text、unknown                       |
| Design references     | DTC / furniture / toy / playroom / gift / premium brand reference patterns             |
| Existing gaps         | dirty title、join mismatch、missing field、unknown facts、asset gaps                       |

## 5.2 输出 artifact

| Artifact                             | 作用                                                                                                |
| ------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `category_portfolio_map.md`          | 定义每个类别的商业角色：giftable、trust furniture、play world、room reset、bundle anchor、premium object           |
| `shopper_mission_map.md`             | 定义主要 shopper：gift buyer、parent trust buyer、room planner、premium browsing parent、grandparent buyer |
| `hero_candidate_matrix.csv`          | 选择 hero SKU，不靠审美直觉                                                                                |
| `sku_role_matrix.csv`                | 给每个 sample SKU 标注 role：hero、proof、bundle attach、risk sample、asset-rich、data-poor                  |
| `navigation_decision_matrix.md`      | 为什么 nav 是 gift-first、room-first、category-first 或 hybrid                                           |
| `pdp_module_strategy_by_category.md` | 不同类别 PDP 模块顺序：尺寸、年龄、材料、assembly、care、reviews、bundles、video、comparison                             |
| `bundle_and_cross_sell_map.csv`      | 哪些产品能组成 room / gift / pretend-play / learning bundle                                              |
| `claim_permission_matrix.csv`        | 哪些 copy 可用、哪些必须降级、哪些禁止                                                                            |
| `asset_readiness_matrix.csv`         | 哪些 SKU 有足够图/视频做 hero、PDP、short video、A+ module                                                    |
| `reference_pattern_mapping.md`       | 每个设计 reference 解决什么商业问题，不只是 mood                                                                  |
| `design_decision_matrix.csv`         | 最终桥梁：evidence → decision → page/module → risk → fallback                                          |
| `rejected_direction_log.md`          | 记录为什么淘汰某个漂亮但不成立的方向                                                                                |

## 5.3 Design Decision Matrix 的行结构

建议 `design_decision_matrix.csv` 至少有这些字段：

```text
decision_id
business_goal
shopper_mission
evidence_inputs
source_confidence
product_or_category_scope
decision_type
page_or_module
chosen_decision
rejected_alternatives
reasoning
claim_permissions
asset_requirements
risk
fallback_if_evidence_weak
owner
gate_status
```

例子：

| 字段                        | 示例                                                                       |
| ------------------------- | ------------------------------------------------------------------------ |
| business_goal             | furniture / learning tower trust conversion                              |
| shopper_mission           | parent trust buyer                                                       |
| evidence_inputs           | PDP dimensions, assembly notes, image role, Amazon listing fact          |
| decision_type             | PDP module order                                                         |
| chosen_decision           | 把 dimensions / age / assembly / safety copy 放在 media gallery 后、reviews 前 |
| rejected_alternatives     | 先讲 brand story                                                           |
| reasoning                 | trust buyer 先要确认 fit、stability、use case，不是氛围                             |
| claim_permissions         | 只能写 source-backed dimensions；不能写 unsupported safety certification        |
| asset_requirements        | room-context image、detail shot、dimension diagram                         |
| fallback_if_evidence_weak | 使用 “designed for...” 而不是 certified claim；标注 dimension unknown            |

这就是“产品事实如何变成网站决策”的中间层。

---

# 6. Evidence model：什么算进度，什么绝不算 done

## 6.1 Evidence artifact 分类

| 类型                   | Artifact                                                                                                | 说明                                      |
| -------------------- | ------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| Raw source evidence  | `source_cards.tsv`、HTML snapshots、media source snapshots、URL list                                       | 证明信息从哪里来                                |
| Parsed data          | `product_master_v0.csv`、`pdp_facts_sample.csv`、`asin_candidates_sample.csv`                             | 证明 extraction 结果                        |
| Data QA              | `current_data_qa.md`、`slug_image_join_report.csv`、`dirty_title_parse_report.csv`、`do_not_use_fields.md` | 证明数据没有静默污染                              |
| Product dossier      | `sample_product_dossiers/*.md`                                                                          | 证明每个 SKU 的 facts、unknowns、images、claims |
| Marketplace evidence | `asin_match_scoring.md`、`amazon_listing_facts_sample.csv`、`amazon_source_limitations.md`                | 证明 Amazon 信号可用程度                        |
| Media evidence       | `brand_video_assets.csv`、`downloaded_media_manifest.csv`、`video_scene_index.csv`、hashes                 | 证明资产来源和用途限制                             |
| Decision evidence    | `category_portfolio_map.md`、`hero_candidate_matrix.csv`、`design_decision_matrix.csv`                    | 证明不是凭空设计                                |
| Prototype evidence   | prototype URL、route map、screenshots、component notes                                                     | 证明原型真实存在                                |
| QA evidence          | `browser_qa_report.md`、`design_review_report.md`、console logs、mobile screenshots                        | 证明看过、点过、测过                              |
| Claim evidence       | `claim_ledger.csv`、`claim_permission_matrix.csv`、`blocked_claims.md`                                    | 证明没有乱写                                  |
| Closeout evidence    | `closeout.md`、`checkpoint.md`、`evidence_manifest.json`                                                  | 证明 issue 可交接                            |

## 6.2 `evidence_manifest.json` 最小结构

```json
{
  "issue_id": "LAB-004",
  "artifact_set": "stratified_sku_dossiers_v0",
  "created_at": "2026-04-27",
  "owner_role": "Product Intelligence Analyst",
  "artifacts": [
    {
      "path": "sample_product_dossiers/pink_unicorn_plush_rocker.md",
      "type": "product_dossier",
      "source_refs": ["source_cards.tsv#labebe_pdp_001"],
      "confidence": "medium",
      "known_limitations": ["Amazon ASIN not verified yet"]
    }
  ],
  "claims_supported": [],
  "claims_blocked": [],
  "qa_status": "sample_complete_not_full_crawl",
  "next_handoff": "Use this for Commerce Decision Layer, not final website copy without claim review."
}
```

## 6.3 绝不能算 done 的东西

| 不算 done                  | 为什么                                       |
| ------------------------ | ----------------------------------------- |
| “Agent says completed”   | 没有 artifact                               |
| “Issue created”          | 创建 issue 不是进度                             |
| “页面能打开”                  | 不代表 UX、mobile、claim、视觉过关                  |
| “有截图”                    | 截图归档不等于 visual judgment                   |
| “有 Amazon reviews”       | 未验证 ASIN / marketplace / language 可能是污染数据 |
| “有漂亮 moodboard”          | 没有 evidence-to-decision bridge            |
| “有 AI-generated copy”    | 没有 claim permission 就不能用                  |
| “GStack-style review 已跑” | 如果没有 Paperclip evidence capture，不算正式证据    |
| “Multica 旧 issue done”   | 旧 done 不代表当前产品 ready                      |
| “视频很酷”                   | 视频不能强于原型和证据本身                             |

---

# 7. Essential gates：哪些 mandatory，哪些 advisory，哪些现在是 overhead

## 7.1 Mandatory gates

| Gate                     | 触发条件                                    | 产物                                                           | 通过标准                                                                 |
| ------------------------ | --------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------- |
| Scope Separation Gate    | DTC 或 Boss Gallery 进入实现前                | `scope_boundary.md`                                          | DTC 无 AI Studio / Paperclip / internal matrix；Boss Gallery 不伪装成消费者网站 |
| Evidence Integrity Gate  | product facts 进入 design decision 前      | `current_data_qa.md`、`do_not_use_fields.md`                  | 46 products 唯一识别；join mismatch 明确；unknown 显式                         |
| ASIN Identity Gate       | 使用 Amazon listing / VOC 前               | `asin_match_scoring.md`                                      | 每个 ASIN 有 accepted/probable/candidate/rejected/no-match 状态           |
| Claim Gate               | 任何 copy、demo、asset matrix、PDP claim 发布前 | `claim_permission_matrix.csv`、`blocked_claims.md`            | unsupported safety/material/certification/demand claim 被阻断           |
| Design Decision Gate     | high-fi DTC prototype 前                 | `design_decision_matrix.csv`                                 | hero、nav、PDP、bundle、asset choices 有证据和 rejected alternatives         |
| Browser / Visual QA Gate | 给用户/老板/Pro 看前                           | `browser_qa_report.md`、`design_review_report.md`、screenshots | HTTP、mobile、console、core flow、视觉层级无 P0/P1                            |
| Closeout Gate            | issue 标 done 前                          | `closeout.md`、`checkpoint.md`、`evidence_manifest.json`       | 每条 acceptance criteria 指向证据                                          |

## 7.2 Advisory gates

| Gate                       | 什么时候用                                            | 为什么 advisory                        |
| -------------------------- | ------------------------------------------------ | ----------------------------------- |
| CEO / Wow Review           | DTC 方向选择、Boss Gallery first 30s、executive pack 前 | 很有价值，但不能每天阻塞                        |
| Full Design Review Scoring | concept boards 和 prototype 后                     | 用于提升质量，不应用来阻塞早期探索                   |
| Fresh Agent Review         | primary/fallback prototype 后                     | 防 builder-context bias，但不是 Day 1 前置 |
| Pro Review Packet          | design decision matrix 后、prototype 后             | 只在 artifact 足够时问，不要裸问               |
| Skill Curator Review       | repeated skill failure 后                         | 不要为了每次工具使用都写治理                      |

## 7.3 现在属于 overhead 的 gate / work

| 现在不要做                             | 理由                             |
| --------------------------------- | ------------------------------ |
| 全量 MCP/CLI/Skill Decision Matrix  | 不是 Labebe prototype 前置         |
| 全量 machine topology policy        | 除非当前 execution 被机器限制卡住         |
| 完整 no-write smoke program         | Runtime 未来需要，但不是 DTC sample 前置 |
| 历史 conversation skill mining      | 噪音太大                           |
| AgencyAgents bulk role extraction | 容易变成 persona 管理                |
| GStack wholesale installation     | 会污染控制边界                        |
| Full Multica migration            | 会复活旧系统重量                       |

---

# 8. 正确使用 GStack / AgencyAgents / Multica

## 8.1 GStack：只抽 5 条机制

| GStack 机制                   | Paperclip artifact                                     | 触发条件                                           | 退出条件                                                 | 禁止事项                                  |
| --------------------------- | ------------------------------------------------------ | ---------------------------------------------- | ---------------------------------------------------- | ------------------------------------- |
| CEO / Wow premise challenge | `ceo_wow_review.md`                                    | DTC 方向选择、Boss Gallery narrative、executive pack | 明确 first 30s、weakest assumption、out-of-scope、3 种实现方式 | 不导入 GStack persona runtime            |
| Rendered design review      | `design_review_report.md`、screenshots                  | DTC / Boss Gallery 可浏览后                        | desktop/mobile/tablet 截图、AI-slop check、top fixes     | 不把 source code review 当 visual review |
| Browser QA health check     | `browser_qa_report.md`、`qa_baseline.json`              | 任何 URL 要展示前                                    | HTTP 200、console、main flows、mobile、broken links      | 不只测首页                                 |
| Runtime / CSO policy check  | `runtime_policy_review.md`、`secret_surface_map.md`     | 新 skill、MCP、CLI、browser/session、secrets、写权限    | 无 secret 泄漏、权限清楚、rollback plan                       | 不让实验 harness 接触 production session    |
| Ship / Checkpoint closeout  | `closeout.md`、`checkpoint.md`、`evidence_manifest.json` | issue done、handoff、review packet               | criteria → evidence 全映射；known limitations 明确         | 不把 cancelled/superseded work 算成功      |

必须禁止的 GStack 行为：

* telemetry；
* update checks；
* routing injection；
* proactive behavior；
* 写入 `~/.gstack` 或项目状态作为控制来源；
* 把 GStack 变成 Paperclip 控制面；
* Claude Code-centric assumptions；
* 没有 Paperclip artifact capture 的“review completed”。

## 8.2 AgencyAgents：现在价值有限

我的判断：**AgencyAgents 现在不是关键路径。**

可以抽：

```yaml
role_id:
mission:
not_responsible_for:
inputs_required:
outputs_required:
success_metrics:
evidence_required:
handoff_contract:
tools_allowed:
risk_limits:
```

不要抽：

* 大量 specialist persona；
* communication style 里的装饰性人格；
* 未审核 prompt files；
* global agent path 安装；
* 自动路由规则；
* 把角色卡当作能力证明。

更好的替代方式是：

> 为每个 Paperclip issue 指定 owner role，并让 role 由 artifact 反向定义。

例如：

* Product Intelligence Analyst 的能力不是“会研究产品”，而是能交付 `product_master_v0.csv`、`sample_product_dossiers/*.md`、`do_not_use_fields.md`。
* Commerce Strategist 的能力不是“懂增长”，而是能交付 `design_decision_matrix.csv` 和 `pdp_module_strategy_by_category.md`。
* Claim Steward 的能力不是“谨慎”，而是能维护 `claim_permission_matrix.csv` 和 `blocked_claims.md`。

## 8.3 Multica：只保留教训，不保留重量

应该抽取：

* control plane starts read-only；
* issue done ≠ product done；
* issue creation is not progress；
* cancelled smoke fixtures are failure evidence, not success；
* permission selftests matter；
* proof ledger / evidence bundle；
* high-risk review packet discipline。

必须禁止：

* 复活 Multica 为 daily control plane；
* 迁移大量历史 issue；
* 引入 unsupervised write actuator；
* 用旧 done issue 证明当前能力；
* 让 Multica assistant blueprints 进入 Labebe 两周 sprint；
* 把旧 observer/proposer 架构当成当前 Paperclip 必选实现。

---

# 9. 前两周精确计划

## Week 1 目标

产出一个可以信任的 **Labebe Evidence + Decision Base v0**，而不是一个仓促网站。

## Week 2 目标

产出两个前台可看 artifact：

1. 纯 DTC primary + fallback prototype。
2. AI Boss Gallery A-F v0，其中 2-3 个 demo 真正有冲击力，全部经过 claim gate。

## Day 1：Paperclip 最小控制核 + scope freeze

| 工作                                                                            | Artifact                                  |
| ----------------------------------------------------------------------------- | ----------------------------------------- |
| 建 2 个 active org：Labebe Commercial Studio、Paperclip Runtime & Evidence Kernel | Paperclip org/project tree                |
| 建 read-only Multica Archive / Pattern Library                                 | archive area                              |
| 写 DTC / Boss Gallery / Shared Evidence 边界                                     | `scope_boundary.md`                       |
| 写 issue closeout/evidence contract v0                                         | `issue_evidence_contract.md`              |
| 写 gate kernel v0                                                              | `gate_kernel_v0.md`                       |
| 建 source registry skeleton                                                    | `source_cards.tsv`、`source_registry.yaml` |

可见成果：Paperclip 不是空组织，而是一个能约束 Labebe 交付的最小系统。

## Day 2：tool / source method probe

| 工作                                             | Artifact                    |
| ---------------------------------------------- | --------------------------- |
| 测 Labebe PDP / collection / gallery extraction | `tool_method_comparison.md` |
| 测 Amazon public / no-key / existing script 路径  | `source_access_matrix.csv`  |
| 测 public media discovery 路径                    | `initial_media_probe.md`    |
| 记录失败方法                                         | `method_failures.md`        |

规则：不要 full crawl，只做 2-3 个 DTC URL、1-2 个 Amazon sample、若干 media paths。

## Day 3：product master v0 + data QA

| 工作                             | Artifact                        |
| ------------------------------ | ------------------------------- |
| 固定 46 products 唯一 ID           | `product_master_v0.csv`         |
| 检查 slug/image/PDP joins        | `slug_image_join_report.csv`    |
| 解析 dirty titles                | `dirty_title_parse_report.csv`  |
| 标注不能用于 copy / design claim 的字段 | `do_not_use_fields.md`          |
| 选定 6-8 SKU sample              | `sample_selection_rationale.md` |

Day 3 结束时必须知道：哪些字段可用，哪些字段不可信，哪些 SKU 进入 sample。

## Day 4：DTC PDP sample dossiers

| 工作                      | Artifact                       |
| ----------------------- | ------------------------------ |
| 每个 sample SKU 建 dossier | `sample_product_dossiers/*.md` |
| 抽 PDP facts             | `pdp_facts_sample.csv`         |
| 标注 unknown facts        | dossier 内 explicit unknowns    |
| 分类 images               | `image_role_sample.csv`        |
| 标出 claim source         | `claim_seed_ledger.csv`        |

重点：sample 要包括漂亮产品，也要包括数据问题产品。

## Day 5：ASIN identity and listing sample

| 工作                                  | Artifact                          |
| ----------------------------------- | --------------------------------- |
| 为 sample SKU 找 ASIN candidates      | `asin_candidates_sample.csv`      |
| 建 ASIN scoring rubric               | `asin_match_scoring.md`           |
| 抽 listing facts sample              | `amazon_listing_facts_sample.csv` |
| 标注 marketplace/language/source risk | `amazon_source_limitations.md`    |

规则：Day 5 不做 full review crawl；没有 ASIN confidence 就不把 reviews 当 VOC。

## Day 6：public media sample + design reference research

| 工作                                          | Artifact                          |
| ------------------------------------------- | --------------------------------- |
| 抽公共品牌视频/图片/广告 sample                        | `brand_video_assets.csv`          |
| 下载可用 sample 并记录 hash/source                 | `downloaded_media_manifest.csv`   |
| 做 scene index                               | `video_scene_index.csv`           |
| 标注使用限制                                      | `asset_rights_and_usage_notes.md` |
| 研究 design reference pattern，不做 final design | `reference_pattern_mapping.md`    |

设计参考必须回答“这个 pattern 解决哪个 Labebe 商业问题”，不能只是“看起来高级”。

## Day 7：Week 1 synthesis wall

| 工作                                       | Artifact                            |
| ---------------------------------------- | ----------------------------------- |
| 汇总 product/channel/media/sample evidence | `labebe_evidence_wall_v0.md`        |
| 更新 claim ledger                          | `claim_permission_matrix_v0.csv`    |
| 列出 asset gaps                            | `asset_gap_list.md`                 |
| 运行 Evidence Integrity Gate               | `evidence_integrity_gate_report.md` |
| 决定 Week 2 design inputs 是否足够             | `week1_go_no_go.md`                 |

Day 7 的目标是判断：是否已经足够进入 Commerce Decision Layer，而不是是否已经完成全部爬取。

---

## Day 8：Commerce Decision Layer v0

| 工作                           | Artifact                             |
| ---------------------------- | ------------------------------------ |
| 做 category portfolio map     | `category_portfolio_map.md`          |
| 做 shopper mission map        | `shopper_mission_map.md`             |
| 做 hero candidate matrix      | `hero_candidate_matrix.csv`          |
| 做 navigation decision matrix | `navigation_decision_matrix.md`      |
| 做 PDP module strategy        | `pdp_module_strategy_by_category.md` |
| 做 bundle/cross-sell map      | `bundle_and_cross_sell_map.csv`      |
| 做 design decision matrix     | `design_decision_matrix.csv`         |

这是整个项目的关键日。没有 Day 8，就不要做 high-fi DTC。

## Day 9：五个 architecture concept boards

每个方向只做 board，不做完整站点：

1. Gift-first Labebe
2. Home-fit Furniture Labebe
3. Child-sized Worlds Labebe
4. Playroom Reset Labebe
5. Object-led Product Theater Labebe

每个 board 必须包括：

* target shopper；
* homepage logic；
* collection logic；
* PDP logic；
* hero SKU；
* conversion mechanism；
* asset requirements；
* risk；
* 为什么不是 generic；
* 证据支持；
* 淘汰条件。

Artifact：

```text
concept_boards/
  gift_first.md
  home_fit_furniture.md
  child_sized_worlds.md
  playroom_reset.md
  object_led_theater.md
concept_selection_matrix.csv
```

## Day 10：选择 primary + fallback

| 工作                         | Artifact                          |
| -------------------------- | --------------------------------- |
| 运行 CEO/Wow Review advisory | `ceo_wow_review_dtc_direction.md` |
| 运行 Design Decision Gate    | `design_decision_gate_report.md`  |
| 选择 primary + fallback      | `primary_fallback_decision.md`    |
| 写 prototype brief          | `dtc_prototype_brief.md`          |

人类可以在 Day 10 介入裁决 primary/fallback，但 agent 应先给出明确建议，不要把选择完全丢给用户。

## Day 11-12：DTC prototype + Boss Gallery v0 并行

### DTC

| 工作                                     | Artifact                    |
| -------------------------------------- | --------------------------- |
| 做 primary high-fi clickable prototype  | prototype URL / local build |
| 做 fallback lighter prototype           | fallback URL / local build  |
| 做 desktop/mobile routes                | `route_map.md`              |
| 做 PDP key flow                         | PDP screens                 |
| 做 gift / furniture / room-bundle paths | flow screenshots            |

### Boss Gallery

| 工作                                       | Artifact                        |
| ---------------------------------------- | ------------------------------- |
| 基于现有 `labebe_wow` baseline 建 A-F gallery | `boss_gallery/index.html`       |
| 做 A-F demo cards                         | demo pages                      |
| 至少打磨 2-3 个最强 demo                        | selected demos                  |
| 每个 demo 带 evidence labels 和 claim status | `boss_gallery_claim_ledger.csv` |
| 不支持 claim 明确 blocked                     | `blocked_claims.md`             |

## Day 13：QA and claim gate

| 工作                       | Artifact                                 |
| ------------------------ | ---------------------------------------- |
| DTC browser QA           | `browser_qa_report_dtc.md`               |
| DTC design review        | `design_review_report_dtc.md`            |
| mobile screenshots       | `screenshots/mobile/*`                   |
| Boss Gallery browser QA  | `browser_qa_report_boss_gallery.md`      |
| Boss Gallery claim scan  | `claim_gate_report_boss_gallery.md`      |
| 如果有视频，做 contact sheet QA | `contact_sheet.jpg`、`video_qa_report.md` |

## Day 14：Executive decision pack

| 工作                  | Artifact                                 |
| ------------------- | ---------------------------------------- |
| 汇总 DTC prototype    | URL + screenshots                        |
| 汇总 Boss Gallery     | URL + walkthrough                        |
| 汇总 evidence wall    | `labebe_evidence_wall_v1.md`             |
| 汇总 design rationale | `design_decision_summary.md`             |
| 汇总 next build scope | `next_build_scope.md`                    |
| 准备老板级说明             | `executive_pack.md`                      |
| issue closeout      | `evidence_manifest.json`、`checkpoint.md` |

Day 14 不是最终生产版本，而是一个可以让人决策的包：

> “这是我们根据证据选择的网站方向，这是可点击原型，这是 AI Boss Gallery，这是证据链，这是风险和下一步投资范围。”

---

# 10. 下一批 10 个 Paperclip issues

下面这 10 个是我建议现在真正创建的，不是完整 backlog。

| #  | Title                                                  | Owner / Role                          | Why now                               | Acceptance criteria                                                                                                                                             | Evidence artifacts                                                                                                                                                                                                 | Stop condition                                        | What not to do                                                       |
| -- | ------------------------------------------------------ | ------------------------------------- | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------- | -------------------------------------------------------------------- |
| 1  | `PCL-001 Minimal Paperclip Operating Kernel`           | Paperclip Program Architect           | 没有最小证据合同，后面 issue done 会再次变成自报完成      | 建立 2 个 active org；建立 project tree；定义 issue closeout；定义 evidence manifest；定义 mandatory/advisory gates v0                                                         | `paperclip_org_tree.md`、`issue_evidence_contract.md`、`gate_kernel_v0.md`、`evidence_manifest_schema.json`                                                                                                           | 如果开始讨论 5 个 org 或完整 runtime platform，停止并降维             | 不建 Skill Foundry 独立 org；不迁移大量 Multica issue                          |
| 2  | `LAB-001 Scope Boundary and Source Registry`           | Program Strategist / Evidence Steward | 防止 DTC、Boss Gallery、Paperclip 再次混线    | 写清 DTC 禁止项、Boss Gallery 允许项、shared evidence layer；创建 source registry skeleton                                                                                   | `scope_boundary.md`、`source_registry.yaml`、`source_cards.tsv`                                                                                                                                                      | 如果 DTC 页面出现 AI/Paperclip/internal matrix，必须重做         | 不写泛泛愿景；不把 Paperclip 作为消费者前台                                          |
| 3  | `LAB-002 Tool and Source Method Probe`                 | Tooling Research Engineer             | Amazon 和 media 来源未预提供，必须先验证方法         | 测 2-3 个 Labebe PDP/collection/media 路径；测 1-2 个 Amazon sample 路径；列 no-key/manual/key-required methods；记录失败                                                       | `tool_method_comparison.md`、`source_access_matrix.csv`、`method_failures.md`、`initial_media_probe.md`                                                                                                               | 如果方法不可稳定复现，只能标 experimental，不得 full crawl             | 不做 full crawl；不假设 Apify/Keepa/SP-API 可用                              |
| 4  | `LAB-003 Product Master v0 and Data QA`                | Product Data Analyst                  | 网站设计必须先知道当前 46 产品数据是否可信               | 46 products 唯一识别；dirty title report；slug/image/PDP join report；do-not-use fields                                                                                | `product_master_v0.csv`、`current_data_qa.md`、`slug_image_join_report.csv`、`dirty_title_parse_report.csv`、`do_not_use_fields.md`                                                                                    | 如果产品无法唯一识别，后续 sample 和 ASIN 工作暂停                      | 不把不完整字段用于 copy；不静默丢失 image/PDP join                                  |
| 5  | `LAB-004 Stratified 6-8 SKU Product Dossiers`          | Product Intelligence Analyst          | 设计不能再只看漂亮产品，sample 必须暴露风险             | 完成 6-8 SKU dossiers；包含 Pink Unicorn、Kitchen、Learning Tower、near-duplicate furniture、low/no-review important SKU、B087P9SXZQ mapping check、no-match、slug mismatch | `sample_product_dossiers/*.md`、`pdp_facts_sample.csv`、`image_role_sample.csv`、`claim_seed_ledger.csv`、`sample_selection_rationale.md`                                                                              | 如果 source/provenance 不明，dossier 不得 pass               | 不只选好看的 SKU；不写 unsupported material/safety/development claims         |
| 6  | `LAB-005 ASIN Identity and Marketplace Listing Sample` | Marketplace Intelligence Analyst      | 没有 ASIN identity，Amazon VOC 会污染设计     | 为 sample SKU 建 ASIN candidates；给 confidence status；抽 listing facts；标 marketplace/language/source risks                                                          | `asin_candidates_sample.csv`、`asin_match_scoring.md`、`amazon_listing_facts_sample.csv`、`amazon_source_limitations.md`                                                                                              | ASIN 未达 accepted/probable，不得进入 VOC/copy/design proof  | 不先爬 review；不混 marketplace/language；不把 Amazon signal 当直接销量证明          |
| 7  | `LAB-006 Public Media Asset Probe and Scene Index`     | Media Asset Researcher                | DTC 和 Boss Gallery 都需要真实资产，但视频资产未手动提供 | 找 public brand media sample；下载可用样本；记录 URL、capture time、hash、page context；做 scene index 和 usage caveats                                                          | `brand_video_assets.csv`、`downloaded_media_manifest.csv`、`media_source_snapshots/`、`video_scene_index.csv`、`asset_rights_and_usage_notes.md`                                                                       | 如果来源不清或 usage caveat 不明，不得用于 final claim              | 不把 public capture 当法律 clearance；不把视频画面当 claim proof                  |
| 8  | `LAB-007 Commerce Decision Layer v0`                   | Commerce Strategist / UX Architect    | 这是 facts 到网站设计的硬中间层                   | 完成 portfolio、shopper mission、hero matrix、nav decision、PDP module strategy、bundle map、asset gap、claim permissions、design decision matrix                         | `category_portfolio_map.md`、`shopper_mission_map.md`、`hero_candidate_matrix.csv`、`navigation_decision_matrix.md`、`pdp_module_strategy_by_category.md`、`bundle_and_cross_sell_map.csv`、`design_decision_matrix.csv` | 如果 hero/nav/PDP 不能追溯到 evidence，不允许 high-fi prototype  | 不做 moodboard 代替决策；不只写“提升信任”这种空话                                      |
| 9  | `LAB-008 Pure DTC Primary + Fallback Prototype`        | UX Designer / Prototype Engineer      | 需要尽快得到可看、可点、可 QA 的消费者网站方向             | 基于 `LAB-007` 做一个 primary 和一个 fallback；含 desktop/mobile homepage、collection、PDP、核心购买路径；无 AI/Paperclip/internal matrix                                            | prototype URL/build、`route_map.md`、desktop/mobile screenshots、`design_review_report_dtc.md`、`browser_qa_report_dtc.md`                                                                                             | 如果 prototype 看起来可换 logo 泛用，回到 Commerce Decision Layer | 不实现五个完整网站；不把首页做成唯一重点；不写 fake reviews/claims                          |
| 10 | `LAB-009 AI Boss Gallery A-F v0 with Claim Gate`       | AI Demo Producer / Claim Steward      | 需要与 DTC 分开的老板级 AI 应用展示                | 基于现有 `labebe_wow`，做 A-F gallery skeleton；重点打磨 2-3 个 demo；每个 demo 有 evidence label、claim status、blocked claims；通过 browser/mobile QA                              | `boss_gallery/index.html`、demo pages、`boss_gallery_claim_ledger.csv`、`blocked_claims.md`、`browser_qa_report_boss_gallery.md`、contact sheet/video if generated                                                      | 如果第一屏讲 Paperclip 流程而不是 Labebe outcome，必须重写            | 不把 Boss Gallery 塞进 DTC；不把 concept 当 production CAD / safety approval |

---

# 11. 人类现在必须决策什么，什么不该问，什么等样本出来再说

## 11.1 必须由用户现在裁决

| 决策                               | 推荐默认值                                                                                                  |
| -------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Paperclip org 数量                 | 建 2 个 active org：Labebe Commercial Studio、Paperclip Runtime & Evidence Kernel；Multica 只读 archive       |
| 两周内主要成功标准                        | 一个 evidence-backed DTC primary/fallback prototype + 一个 claim-gated Boss Gallery v0                     |
| DTC 四个目标的排序                      | 不必选唯一目标，但要排序。我的默认排序：1 trust/PDP conversion，2 premium brand rebuild，3 gift conversion，4 room/bundle AOV |
| AI-generated assets 在 DTC 中的使用边界 | DTC 原型可以用 AI concept placeholder，但必须标记；最终消费者 copy 不用 unsupported AI claims                             |
| Amazon 数据源预算/权限                  | 默认先 no-key/manual/public sample；有 token/key 再升级，不等待                                                    |
| Boss Gallery 的 demo 风格           | 默认 result-first：先给业务 outcome，再显示 evidence/claim gate，不讲 Paperclip 流程                                   |

## 11.2 Agent 应该自己推进，不该问用户

| Agent 应自己决定                         | 原因                           |
| ----------------------------------- | ---------------------------- |
| 2-3 个 PDP method probe URL          | 不值得打断用户                      |
| sample 中具体哪个 no-match SKU           | 只要符合 sample criteria         |
| source registry 字段命名                | 可后续修                         |
| image role taxonomy v0              | 先跑起来                         |
| ASIN confidence scoring rubric v0   | 用户不该参与细节                     |
| initial media source paths          | agent 可自行探索                  |
| first draft Commerce Decision Layer | 用户应审结果，不应被问空问题               |
| Browser QA screenshot viewport      | 按标准 desktop/tablet/mobile 即可 |
| blocked claims 初筛                   | Claim Steward 应主动阻断          |

## 11.3 等样本出来后再裁决

| 决策                                                            | 为什么等                                         |
| ------------------------------------------------------------- | -------------------------------------------- |
| DTC primary architecture 是 Gift-first 还是 Home-fit Furniture 等 | 需要 hero matrix、asset readiness、PDP facts 后判断 |
| 是否 full Amazon crawl                                          | 要看 method probe 和 ASIN sample 质量             |
| 是否投入 public video/ad full acquisition                         | 要看 sample 是否有足够素材                            |
| Boss Gallery A-F 哪 2-3 个重点打磨                                  | 要看 evidence 支撑强度                             |
| 是否做 Pro review                                                | 先有 artifact packet，否则 review 会空泛             |
| 是否把 Browser/Vision Lab 升为 org                                 | 只有当 QA/harness work 持续成为瓶颈                   |
| 是否把 Skill Foundry 升为 org                                      | 只有当 repeated skill failure 影响多个项目            |
| 是否进入 Shopify / production implementation                      | 等 DTC prototype 和 decision pack 被认可          |

---

# 12. 最终建议路线

## 现在是否应该建立 Paperclip 团队？

应该，但只建最小版本。

不要把 Paperclip 第一周变成“组织建设周”。Paperclip 的价值必须立刻体现在：

* issue 有 evidence；
* claim 有 source；
* DTC 和 Boss Gallery 不混；
* prototype 先过 visual/browser QA；
* done 不再是 agent 自报。

## 建几个 org？

我的直接建议：

```text
2 个 active org + 1 个 read-only archive area
```

具体：

```text
1. Labebe Commercial Studio
2. Paperclip Runtime & Evidence Kernel
3. Multica Archive / Pattern Library，read-only，不作为 active sprint org
```

如果系统必须创建第三个 org，那就建：

```text
Multica Archive
```

但只允许一个 issue：`archive_lessons_and_failed_fixtures`。不要迁移大量历史 issue。

## 第一批 issues 是哪些？

创建这 10 个：

```text
PCL-001 Minimal Paperclip Operating Kernel
LAB-001 Scope Boundary and Source Registry
LAB-002 Tool and Source Method Probe
LAB-003 Product Master v0 and Data QA
LAB-004 Stratified 6-8 SKU Product Dossiers
LAB-005 ASIN Identity and Marketplace Listing Sample
LAB-006 Public Media Asset Probe and Scene Index
LAB-007 Commerce Decision Layer v0
LAB-008 Pure DTC Primary + Fallback Prototype
LAB-009 AI Boss Gallery A-F v0 with Claim Gate
```

## 在下一轮 Labebe 网站设计前，必须先完成什么？

必须完成：

1. `scope_boundary.md`
2. `product_master_v0.csv`
3. `current_data_qa.md`
4. `do_not_use_fields.md`
5. `sample_product_dossiers/*.md`
6. `pdp_facts_sample.csv`
7. `image_role_sample.csv`
8. `asin_match_scoring.md`
9. `brand_video_assets.csv` 或至少 `initial_media_probe.md`
10. `category_portfolio_map.md`
11. `hero_candidate_matrix.csv`
12. `navigation_decision_matrix.md`
13. `pdp_module_strategy_by_category.md`
14. `bundle_and_cross_sell_map.csv`
15. `claim_permission_matrix.csv`
16. `design_decision_matrix.csv`

没有这些，不要再做“下一版漂亮网站”。

## 现在坚决不要做什么？

不要做这些：

1. 不要建 5 个 active org。
2. 不要把 Skill Foundry 独立出来。
3. 不要把 Browser and Vision Lab 独立出来。
4. 不要导入 GStack。
5. 不要 bulk-install AgencyAgents。
6. 不要迁移 Multica 大量历史 issue。
7. 不要先做 full Amazon review crawl。
8. 不要还没 ASIN identity 就做 VOC synthesis。
9. 不要做五个完整 DTC 网站版本。
10. 不要让 Boss Gallery 讲 Paperclip，而不是讲 Labebe outcome。
11. 不要把 AI Studio、Paperclip board、Product Matrix 放进消费者 DTC 网站。
12. 不要用 fake reviews、fake certifications、fake safety/material claims。
13. 不要把视频包装做得比原型和证据更强。
14. 不要因为 Runtime Governance 未完而阻止 Labebe prototype 前进。
15. 不要把“issue created”“agent says done”“page opens”当作完成。

---

## 最直接的路线图

我会这样推进：

```text
Day 1:
  建最小 Paperclip kernel
  固定 scope/evidence/gate contract

Day 2-7:
  跑 Labebe product + marketplace + media sample
  修 data QA
  建 evidence wall

Day 8:
  做 Commerce Decision Layer

Day 9-10:
  做五个 architecture boards
  选 primary + fallback

Day 11-12:
  做 DTC prototype
  并行做 Boss Gallery A-F v0

Day 13:
  browser / visual / claim QA

Day 14:
  交 executive decision pack
```

我的最终建议是：

**先用 Labebe 逼 Paperclip 变锋利，而不是先用 Paperclip 逼 Labebe 变慢。**

Paperclip 的第一阶段价值不是“管理很多 AI 组织”，而是保证第一批 Labebe artifacts 真正有证据、有判断、有视觉质量、有 claim discipline、有 handoff。等这个闭环跑通，再扩 Skill Foundry、Browser/Vision、Runtime Governance、Multica lessons。现在扩那些，只会让系统看起来更成熟，但让 Labebe 结果更慢、更散、更不 wow。
