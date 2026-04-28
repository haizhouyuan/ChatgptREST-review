# 结论先说：Kimi 版不是“差”，但它现在只是一个漂亮的品牌气氛页，不是世界级 Demo

我看了你给的 Kimi 站点，也对照了 Labebe 当前可访问官方站、附件里的抓取数据和上下文包。我的判断很直接：

**Kimi 版比原站更有“设计感”，但它没有真正解决 Labebe 的核心问题；原站像一个能卖货但不够高级的电商站，Kimi 版像一个高级但不能卖货、不能证明增长能力、也不能代表真实品牌的概念页。**

真正要做成世界级 Demo，不应该只是“把 Labebe 页面做漂亮”，而应该做成一个 **“世界级儿童成长空间品牌站 + AI 增长工作流演示厅”**。也就是说，老板打开后不只是觉得“哇，好看”，而是要看到：

1. Labebe 可以从普通儿童玩具站升级成儿童成长空间品牌；
2. 一个 SKU 可以快速裂变成 Amazon、TikTok、Meta、Google、独立站全渠道资产；
3. 网站不只是展示产品，而是在引导父母按年龄、房间、礼物、玩法做购买决策；
4. AI 不只是画图和写文案，而是能把“产品 → 场景 → 内容 → 渠道 → 复盘”串成增长系统。

附件里已经强调，Labebe 后续方案不应继续停留在“AI 画图、AI 写文案、AI 投广告”的工具清单，而要围绕可演示的增长链路和可审批、可追责、可持续运行的工作流展开。

---

# 1. 我对 Kimi 版的总体评价

Kimi 版当前更像一个 **AI 生成的设计实验**，不是一个可以打动董事长、投资人、电商团队和品牌团队的世界级 Demo。

它的优点是：

* 视觉上比原站更轻、更艺术、更有留白；
* 有动效、手写字体、水彩背景、视频区、评论区、品牌故事区；
* 用了一些真实产品图片，比如 Pink Unicorn Plush Rocker、Learning Tower、Play Kitchen 等；
* 作为“AI 能快速生成一个网站”的展示，已经能证明基础能力。

但它的致命问题也很明显：

* **不忠于 Labebe 真实品牌**；
* **不忠于真实商品数据**；
* **不具备真实电商链路**；
* **不具备购买决策路径**；
* **不具备 AI 增长演示价值**；
* **不具备老板一眼看懂的商业闭环**；
* **有很多看起来高级、但和 Labebe 业务无关的动效。**

当前官方站至少已经有真实导航、促销、商品列表、Quick add、产品页、价格、评论数、信任说明等基础电商结构，比如首页有 Free US Shipping、首单 10% off、New In、Sale、Kids Furniture、Rockers & Ride-Ons、Kitchens & Pretend Play、Activity Toys 等入口。([Labebe Club][1])
而 Kimi 版虽然更像“作品集”，但缺少这些真正支撑下单和增长的结构。

所以我会把它定义为：

```text
当前 Kimi 版 = 视觉草稿 / AI 网页生成样机
目标世界级 Demo = 品牌升级样板 + 可购物网站 + AI 增长工作流演示系统
```

---

# 2. Kimi 版与原站的核心对比

## 2.1 原站的问题

原站的问题不是没有内容，而是内容组织方式太传统。官方站现在的首页和集合页基本是“促销条 + 导航 + Banner + 商品网格 + 订阅 + Footer”的结构。集合页有排序、Quick add、价格、折扣、评论数，但整体还是以类目和商品网格为中心。比如 Kids Furniture 集合页列出了 Montessori Shelf、Toy Storage Organizer、Desk & Chair、Learning Tower 等商品，并提供 Featured、Best Sellers、New Arrivals、价格排序等电商基础功能。([Labebe Club][2])

Rockers & Ride-Ons 集合页也已经有真实 SKU、价格、折扣和评论数，例如 Highlander Cattle Plush Rocker、Llama Plush Rocker、Pink Unicorn Plush Rocker、Wooden Rainbow Rocking Chair 等。([Labebe Club][3])

原站的核心问题是：

| 维度   | 原站现状             | 问题                                    |
| ---- | ---------------- | ------------------------------------- |
| 视觉   | 有真实产品图，但整体偏模板电商  | 品牌高级感不足                               |
| 购买路径 | 按类目进入            | 没有按年龄、房间、礼物、玩法、父母痛点进入                 |
| 首页   | 有促销和基础分类         | 没有明确品牌主张和场景故事                         |
| 集合页  | 商品网格为主           | 缺少场景化解释、导购、视频、FAQ                     |
| PDP  | 有价格、促销、信任模块和部分详情 | 缺少更强的视频演示、尺寸决策、安全解释、搭配推荐              |
| 内容系统 | 图多，但没有被组织成增长资产   | TikTok、Amazon、Meta、Google、独立站不能一套资产复用 |
| 品牌叙事 | About 页有真实故事     | 没有在首页和商品路径中充分放大                       |

原站 About 页其实已经给了非常重要的品牌锚点：Labebe 面向 6 个月到 10 岁儿童，起源于 wooden rocking horses，核心信念是 “More Brave, More You”，强调安全、想象力、自信、独立和自我表达。([Labebe Club][4])
这些才是 Kimi 版应该抓住的真实品牌内核。

---

## 2.2 Kimi 版的问题

Kimi 版的问题不是“页面不漂亮”，而是它的漂亮没有绑定 Labebe 的真实业务。

我解包看了 Kimi 的源码结构。它目前主要由以下 section 组成：

```text
Navigation
Hero
BrandIntro
CollectionShowcase
FeaturedProduct
BrandStory
VideoSection
Reviews
Newsletter
Footer
WatercolorCanvas
```

这个结构看上去像一个完整首页，但商业上很空。最明显的问题有 12 个。

---

## 2.3 问题 1：品牌故事是错的

Kimi 版 BrandStory 里写的是：

```text
Our toys are designed in Stockholm and handcrafted by artisans...
EST. 2012
```

这非常危险。

Labebe 官方 About 页明确说的是：Labebe 设计和制作安全、贴心的玩具和家具，面向 6 个月到 10 岁儿童，起源于 wooden rocking horses，并以 “More Brave, More You” 为理念。([Labebe Club][4])

所以 Kimi 版不能写 Stockholm、不能写 EST. 2012、不能乱写 handcrafted artisans。世界级 Demo 第一条原则是：

```text
高级可以，但不能假。
```

这类错误会让老板一眼觉得“不可信”，也会让团队无法继续拿它作为正式方向。

**要改成：**

```text
Born from rocking horses. Built for brave little moments.

Labebe began with wooden rocking horses — timeless pieces that help children move, imagine and build confidence. Today, our world has grown into Montessori-inspired furniture, pretend play sets, activity toys and warm wooden pieces for children from 6 months to 10 years old.

More Brave, More You.
```

---

## 2.4 问题 2：产品数据不真实

Kimi 版 Featured Product 写：

```text
Pink Unicorn Plush Rocker
$89.99
Suitable for ages 18 months and up.
```

但抓取摘要显示 Pink Unicorn Plush Rocker 当前价格是 $109.99，且它是抓取样本里评论数最高的 SKU。
官方产品页也显示 Pink Unicorn Plush Rocker 价格为 $109.99，描述为适合 kids 1–3Y 的 soft cushioned seat with harness、sturdy wooden base、gentle rocking fun。([Labebe Club][5])

这类错误会破坏 Demo 的可信度。世界级 Demo 必须使用真实产品数据，即使只是前端静态 Demo，也要用 `products.json` 或 `products.ts` 统一驱动页面。

建议建立：

```ts
type Product = {
  slug: string;
  title: string;
  collection: string;
  price: number;
  compareAtPrice?: number;
  reviews?: number;
  ageRange: string;
  roomTags: string[];
  playTags: string[];
  giftTags: string[];
  image: string;
  shortBenefit: string;
  badges: string[];
};
```

然后 Featured Product、Collection Cards、PDP、AI Growth Demo 全部从同一份产品数据读取。

---

## 2.5 问题 3：分类是错的

Kimi 版 CollectionShowcase 里的分类是：

```text
Building Blocks
Musical Play
Pretend Play
Art & Craft
Outdoor Fun
Learning Toys
```

这看起来像通用木玩品牌，不像 Labebe。

附件抓取摘要显示，Labebe 当前 46 个产品分布在 5 个主要集合：`furniture` 17 个、`rockers-ride-ons` 13 个、`pretend-play` 9 个、`activity-educational-toys` 6 个、`new-in` 1 个。

所以 Kimi 版分类必须改成真实业务入口：

```text
Giftable Rockers
Montessori Furniture
Pretend Play Worlds
Activity & Learning
Storage & Room
Outdoor Play
```

如果要做得世界级，甚至不应该只按品类，而应该做成多维入口：

```text
Shop by Age
Shop by Room
Shop by Play Style
Gift Guide
Montessori at Home
Watch It in Action
```

---

## 2.6 问题 4：Hero 没有产品、没有场景、没有购买动机

Kimi 版 Hero 的核心是一个 `Discover` 手写动效，下面一句：

```text
Every toy tells a story. Explore our world of handcrafted wooden wonders.
```

问题是：它看不出 Labebe 卖什么，也不能让父母知道该点哪里。

世界级 Hero 必须在 5 秒内回答：

```text
我是谁？
我卖什么？
我适合谁？
我为什么值得信任？
我下一步点哪里？
```

建议改成：

```text
Create a Warm, Playful Space for Every Little Milestone

Montessori-inspired furniture, plush rockers and wooden pretend play sets for children from 6 months to 10 years old.

[Shop by Age] [Explore Gift Picks]
```

右侧或背景必须是一个真实场景，不要只是水彩背景。可以用：

* Pink Unicorn Plush Rocker 放在 nursery；
* Learning Tower 放在现代厨房；
* Montessori Shelf 放在 playroom；
* Play Kitchen 放在儿童角色扮演角。

Hero 下方加信任条：

```text
Free US Shipping 3–7 Business Days
FSC-certified wood
Non-toxic finishes
ASTM / EN71 tested
Loved by families
```

官方产品页已经有 FSC-certified wood、non-toxic finishes、CPC、ASTM、EN71 等信任信息。([Labebe Club][5])

---

## 2.7 问题 5：动效是“炫技”，不是“业务叙事”

Kimi 版用了 WebGL 水彩背景、Lorenz attractor 小球、stroke draw text、GSAP scroll reveal 等。视觉上有趣，但很多动效和 Labebe 业务没有关系。

世界级 Demo 不是不能用动效，而是动效必须服务购买和演示：

| 当前动效                      | 问题      | 应改成              |
| ------------------------- | ------- | ---------------- |
| Lorenz Canvas 菜单球         | 和儿童玩具无关 | 改成购物车、搜索、年龄导购入口  |
| Discover 手写动效             | 有美感但信息弱 | 改成产品场景进入 + 微交互   |
| 全局水彩背景                    | 容易抢内容   | 局部用在品牌故事和礼赠场景    |
| Contact sheet 作为视频 poster | 显得像素材盘  | 改成真实 15 秒产品视频封面  |
| 滚动 reveal                 | 可以保留    | 但减少数量，避免页面慢和审美疲劳 |

更高级的动效应该是：

```text
儿童房场景中，用户点击 “Age 1–3” → 摇马、活动墙、收纳架被高亮；
点击 “Kitchen Helper” → Learning Tower 从侧边滑入厨房场景；
点击 “Gift Pick” → Unicorn Rocker 变成礼盒场景；
点击 “Generate TikTok” → 一个 SKU 裂变成 5 条短视频卡片。
```

这才是有商业含义的动效。

---

## 2.8 问题 6：没有真实可购物链路

Kimi 版有 Add to Cart，但它只是按钮，没有真实 cart drawer、SKU、数量、价格、变体、checkout、库存状态、推荐搭配。

原站集合页至少有 Quick add 和真实商品卡；比如 Rockers & Ride-Ons 集合页列出每个 rocker 的价格、折扣、评论数和 Quick add。([Labebe Club][3])

世界级 Demo 不一定要接真实支付，但必须至少做出：

```text
Product card → Quick add → Cart drawer → Bundle recommendation → Checkout simulation
```

最低要求：

```text
1. 产品卡可点击进入 PDP
2. PDP 可 Add to Cart
3. Cart drawer 显示商品、价格、数量、小计
4. Cart 中推荐搭配商品
5. CTA 可写 “Demo Checkout”
```

例如：

```text
Pink Unicorn Plush Rocker
+ Gift Wrapping
+ Wooden Bakery Toy Food Playset
+ First Birthday Gift Card
```

这会比一个静态 Add to Cart 按钮高级很多。

---

## 2.9 问题 7：没有按父母真实决策方式导购

父母买儿童产品时，通常不是先想“我要买 furniture 类目”，而是想：

```text
我孩子几岁？
适不适合我家空间？
安不安全？
能不能当生日礼物？
能不能培养独立性？
能不能让房间更整洁？
能不能用久一点？
```

所以世界级 Demo 要有“导购智能层”。

建议首页第 2 屏做一个非常强的模块：

```text
Find the Right Labebe Piece

Step 1: Child's age
[6–18 months] [18–36 months] [3–6 years] [6+ years]

Step 2: Room
[Nursery] [Playroom] [Kitchen] [Bedroom] [Outdoor]

Step 3: Goal
[Gift] [Independence] [Pretend Play] [Storage] [Activity]

Result:
Recommended Labebe setup
```

示例输出：

```text
For a 1–3 year old nursery gift:
1. Pink Unicorn Plush Rocker
2. Activity Cube Baby Push Walker
3. Rubber Wood Corner Cabinet
```

这就是比原站和 Kimi 版都更高级的地方。

---

## 2.10 问题 8：没有把 Labebe 最强视觉资产放大

从 contact sheet 和抓取摘要看，Labebe 其实有几个很强的视觉赛道：

* Plush animal rockers；
* Montessori / learning tower / children furniture；
* Pretend-play kitchens、coffee shop、bakery、washer dryer、mud kitchen；
* Storage、shelves、desks、activity boards。

Kimi 版虽然用了部分图片，但没有建立“视觉世界”。

世界级 Demo 应该建立 4 个清晰世界：

```text
World 1: Giftable Rockers
粉色独角兽、高地牛、羊驼、天鹅、狐狸

World 2: Montessori at Home
学习塔、蒙氏架、书桌、收纳柜

World 3: Tiny Pretend Worlds
厨房、咖啡店、烘焙、洗衣房、泥厨房

World 4: Playroom Reset
收纳、活动墙、画架、桌椅
```

每个世界都应该有：

```text
Hero 场景
3 个主推 SKU
15 秒视频
父母痛点
购买理由
入口 CTA
```

---

## 2.11 问题 9：评论区像假的

Kimi 版 Reviews 写了 Sarah M.、David K.、Emily R. 等泛用评论。问题是太像模板，且提到 building blocks 等不符合当前产品结构的内容。

抓取摘要里有真实产品评论数数据，例如 Pink Unicorn 18 条、Children’s Writing Desk 12 条、Kids Wooden Desk 11 条、Midnight Serenity Kitchen 10 条、Cream Play Kitchen 9 条、Montessori Shelf 9 条。

Demo 中可以不展示完整真实评论原文，但必须让评论区绑定真实产品：

```text
Most loved by families

Pink Unicorn Plush Rocker
18 reviews
“Perfect as a first birthday gift.”

Cream Wooden Play Kitchen
9 reviews
“Beautiful pretend play corner.”

Natural Wood Montessori Shelf
9 reviews
“Makes toy rotation easier.”
```

如果没有真实评论内容，就写成“review themes”而不是伪造用户长评。

---

## 2.12 问题 10：没有 AI Demo 层

这是最大缺口。

你前面要的不是普通网站，而是“网站升级与 AI 短视频 / 营销素材生产方案”。Kimi 版却没有把 AI 能力做成可见体验。

世界级 Demo 必须有一个独立入口：

```text
AI Growth Studio
```

它不是给消费者看的，而是给老板看的。建议在导航右侧放一个低调但高级的按钮：

```text
AI Growth Demo
```

进入后展示 3 条链路：

```text
1. One SKU → Multi-Channel Asset Matrix
2. VOC → Product Concept → Launch Test
3. Weekly Growth Assistant
```

附件里已经建议重点示范“一款 Amazon 爆款 SKU → Amazon / TikTok / Google / Meta / 独立站资产矩阵”的链路。
这应该成为世界级 Demo 的核心，而不是附属说明。

---

# 3. 我建议的世界级 Demo 目标

不要把目标定成：

```text
做一个更漂亮的 Labebe 首页
```

而应该定成：

```text
做一个让老板看到 Labebe 未来 12 个月增长方式的交互式样板。
```

世界级 Demo 应该同时满足 5 个层级。

---

## 3.1 第一层：像真正的高端儿童品牌

打开首页，第一眼要像：

```text
温暖
干净
有安全感
有设计审美
有儿童成长理念
有礼赠价值
```

不是花哨，不是 AI 炫技，不是儿童乐园式廉价色彩。

视觉关键词：

```text
warm wood
soft nursery
Scandi home
Montessori calm
giftable plush
parent-child participation
organized playroom
```

---

## 3.2 第二层：像真正能下单的电商站

至少要有：

```text
真实产品数据
真实价格
真实分类
真实商品卡
真实 PDP
真实购物车抽屉
真实推荐搭配
真实信任模块
```

即使不接真实 Shopify，也要让人觉得“这可以明天接 Shopify API 上线”。

---

## 3.3 第三层：像真正懂父母的导购系统

必须提供：

```text
Shop by Age
Shop by Room
Shop by Gift Occasion
Shop by Play Style
Shop by Parent Goal
```

这是原站和 Kimi 版都没有做好的地方。

---

## 3.4 第四层：像真正的多渠道内容中台

选择一个 SKU，就可以看到：

```text
Amazon A+ Hero
Amazon Video
TikTok 9:16
Meta Carousel
Google Shopping image
PDP Demo video
Email module
```

这比单纯网页设计更能打动老板。

---

## 3.5 第五层：像真正的 AI 增长系统

不是“AI 生成了一张图”，而是：

```text
产品数据 → 生成脚本 → 生成图片 → 生成视频 → 平台适配 → 审核 → 发布 → 数据复盘
```

附件已经指出，真正先进的做法不是 AI 画图、AI 写文案、AI 投广告，而是可观测、可审批、可追责、可持续运行的 Agent / 工作流系统。

---

# 4. 新 Demo 应该长什么样：推荐信息架构

我建议把 Demo 做成两个模式：

```text
Consumer Experience
AI Growth Demo
```

也就是：

```text
普通用户看到的是高端品牌电商站；
老板点击 AI Growth Demo，看到的是 AI 增长系统演示。
```

---

## 4.1 Consumer Experience 路由

```text
/
首页

/shop
全部商品

/shop/by-age
按年龄购买

/shop/by-room
按房间购买

/collections/giftable-rockers
礼赠摇马

/collections/montessori-at-home
蒙氏家庭空间

/collections/pretend-play-worlds
角色扮演世界

/collections/playroom-reset
儿童房收纳与改造

/product/:slug
产品详情页

/pages/about
品牌故事

/pages/gift-guide
礼物指南
```

---

## 4.2 AI Growth Demo 路由

```text
/ai-growth-demo
AI 增长演示首页

/ai-growth-demo/one-sku
单 SKU 多渠道裂变

/ai-growth-demo/voc-to-product
评论 / VOC 到新品概念

/ai-growth-demo/creative-matrix
素材矩阵

/ai-growth-demo/weekly-growth-assistant
每周增长助手

/ai-growth-demo/workflow
AI 工作流与人工审批节点
```

---

# 5. 首页应该重做成这样

## 5.1 首页模块顺序

```text
1. Hero：Create a Warm, Playful Space for Every Little Milestone
2. Quick Finder：按年龄 / 房间 / 礼物 / 玩法导购
3. Four Worlds：Giftable Rockers / Montessori at Home / Pretend Play / Playroom Reset
4. Best Sellers：真实 SKU 卡片
5. Watch It in Action：短视频演示
6. Montessori Home Builder：互动房间搭建
7. Giftable Rockers：礼赠专区
8. Product Detail Preview：核心 SKU 快速 PDP
9. Trust & Safety：FSC / Non-toxic / ASTM / EN71
10. AI Growth Studio Teaser：老板演示入口
11. Reviews / Parent Moments
12. Email Capture：领取 Gift Guide / Room Setup Guide
13. Footer
```

---

## 5.2 Hero 模块

当前 Kimi Hero 太空。建议改为：

```text
Create a Warm, Playful Space
for Every Little Milestone

Montessori-inspired furniture, plush rockers and wooden pretend play sets for children from 6 months to 10 years old.

[Shop by Age] [Explore Gift Picks]
```

画面：

```text
左侧：标题、信任条、CTA
右侧：一个温暖儿童房场景
场景中露出 Pink Unicorn Rocker + Montessori Shelf + Activity Cube
```

Hero 下方立即出现：

```text
6–18 months
18–36 months
3–6 years
6+ years
```

这比单纯写 Discover 强很多。

---

## 5.3 Quick Finder 模块

这个模块是世界级 Demo 的关键。

```text
Find the right piece in 30 seconds
```

交互：

```text
Step 1: How old is your child?
6–18m / 18–36m / 3–6y / 6y+

Step 2: Where will it live?
Nursery / Playroom / Kitchen / Bedroom / Outdoor

Step 3: What are you looking for?
Gift / Independence / Pretend Play / Storage / Activity
```

输出卡片：

```text
Recommended for you:
1. Pink Unicorn Plush Rocker
2. Activity Cube Baby Push Walker
3. Rubber Wood Corner Cabinet
```

这可以用静态规则实现，不需要真 AI，但观感会像智能导购。

---

## 5.4 Four Worlds 模块

把 Kimi 的 CollectionShowcase 改掉。

当前：

```text
Building Blocks
Musical Play
Pretend Play
Art & Craft
Outdoor Fun
Learning Toys
```

改成：

```text
Giftable Rockers
First rides, first birthdays, first brave little moments.

Montessori at Home
Learning towers, shelves and desks that help children participate.

Tiny Pretend Worlds
Kitchens, coffee shops, bakeries and mud kitchens for big imagination.

Playroom Reset
Storage, activity walls and art corners that make home feel calm again.
```

每张卡片加：

```text
SKU count
Age range
Best for
CTA
```

示例：

```text
Giftable Rockers
13 products
Best for 1st birthdays, nurseries and grandparent gifts
[Explore Rockers]
```

---

## 5.5 Best Sellers 模块

必须使用真实抓取数据。

首批显示：

```text
Pink Unicorn Plush Rocker — $109.99 — 18 reviews
Children’s Writing Desk & Chair Set — $179.99 — 12 reviews
Kids Wooden Desk & Chair Set — $179.99 — 11 reviews
Midnight Serenity Wooden Play Kitchen — $129.99 — 10 reviews
Cream Wooden Play Kitchen — $129.99 — 9 reviews
Natural Wood Montessori Shelf — $114.99 — 9 reviews
```

这些都是抓取摘要里的高评论 SKU。

每张卡要有：

```text
真实图
真实价格
评论数
Age badge
Room badge
Gift / Montessori / Pretend Play badge
Quick Add
View Details
```

---

## 5.6 Watch It in Action 模块

Kimi 版 VideoSection 当前把 contact sheet 当 poster，这很不专业。

应该改为 5 条具体短视频卡：

```text
1. First Birthday Rocker
Pink Unicorn Plush Rocker
15s

2. Kitchen Helper Moment
Foldable Learning Tower
20s

3. Tiny Chef Pretend Play
Cream Wooden Play Kitchen
15s

4. Toy Rotation Reset
Montessori Shelf
12s

5. Busy Hands Wall
Activity Wall Busy Board
15s
```

每条视频卡有：

```text
产品
场景
父母痛点
平台复用标签：PDP / TikTok / Meta / Amazon
```

---

## 5.7 AI Growth Studio Teaser 模块

首页靠后放一个很高级的模块：

```text
From One Product to Every Channel

See how Labebe can turn a single SKU into a full Amazon, TikTok, Meta, Google and website content pack in 48 hours.

[Open AI Growth Demo]
```

视觉：

```text
中心：Pink Unicorn Plush Rocker
四周飞出：
Amazon Video
TikTok Short
Meta Carousel
Google Shopping Image
PDP Demo Video
Email Gift Guide
```

这个模块会让老板觉得：这不是普通网页，这是增长能力演示。

---

# 6. PDP 产品详情页要做到世界级

Kimi 版目前没有 PDP。原站 PDP 有基础商品页，比如 Pink Unicorn Plush Rocker 有图片、标题、描述、价格、促销、数量、信任说明和认证信息。([Labebe Club][5])

但世界级 PDP 应该这样做。

---

## 6.1 PDP 模块结构

```text
1. 商品首屏
2. Gallery：图片 + 视频
3. Age / Room / Gift badge
4. 价格、评论、Add to Cart
5. 3 个核心购买理由
6. Watch it in action
7. Safety & Materials
8. Dimensions & Fit
9. Assembly & Care
10. Perfect for
11. Bundle with
12. Reviews
13. FAQ
14. Related products
```

---

## 6.2 Pink Unicorn Plush Rocker PDP 示例

```text
Pink Unicorn Plush Rocker

A soft first rocker for magical birthday moments.

$109.99
★★★★★ 18 reviews

Age: 1–3Y
Room: Nursery / Playroom
Best for: First Birthday / Baby Shower / Grandparent Gift

[Add to Cart] [Add Gift Wrap]
```

卖点：

```text
Soft plush comfort
Sturdy wooden rocker base
Cushioned seat with harness
Nursery-ready design
Gentle rocking for confident movement
```

安全说明：

```text
Made with child-friendly materials
Designed with a secure seat and harness
Built on a sturdy wooden rocker base
```

注意：所有认证表述必须和真实数据一致，不能随便加 “safest” 或 “#1”。

---

## 6.3 Learning Tower PDP 示例

官方 Learning Tower 产品页已经有价格、折扣、描述和 “Safe. Stable. Foldable.”、“Grows With Your Child”等模块。([Labebe Club][6])

世界级 PDP 可以进一步升级为：

```text
Foldable Learning Tower & Montessori Kitchen Helper

Let them safely join everyday kitchen moments.

$79.99
Was $109.99

Age: 18 months – 6 years
Room: Kitchen
Best for: Independence / Parent-child routines / Small spaces
```

必须加：

```text
Folded vs Open size comparison
Kitchen counter height visual
Parent-supervised usage note
Assembly time
Cleaning instruction
Safety do / don't
```

---

# 7. AI Growth Demo：这是世界级效果的核心

如果只做消费者网站，最多是“好看的改版”。
如果加上 AI Growth Demo，才会变成“老板会眼前一亮”的东西。

---

## 7.1 AI Growth Demo 首页

标题：

```text
Labebe AI Growth Studio

From product data to multi-channel content, launch-ready in 48 hours.
```

三个主卡片：

```text
1. One SKU → Multi-Channel Asset Matrix
Turn Pink Unicorn Plush Rocker into Amazon, TikTok, Meta, Google and website assets.

2. VOC → Product Concept
Turn reviews and parent pain points into a new product direction.

3. Weekly Growth Assistant
Monitor products, creative fatigue, reviews and opportunities.
```

---

## 7.2 Demo 1：One SKU → Multi-Channel Asset Matrix

这是最应该先做的世界级演示。

流程：

```text
Select SKU
↓
Pink Unicorn Plush Rocker
↓
AI reads product data
↓
Generates channel strategy
↓
Creates scripts
↓
Creates visual prompts
↓
Outputs asset matrix
```

页面左侧是 SKU card：

```text
Pink Unicorn Plush Rocker
Collection: Rockers & Ride-Ons
Price: $109.99
Reviews: 18
Best for: First birthday, nursery, gift
```

页面右侧是生成结果：

```text
Amazon
- 16:9 product video
- A+ hero
- Feature tiles

TikTok
- 3 hooks
- 5 vertical short concepts
- Captions

Meta
- Carousel
- Reels
- Copy variants

Google
- Shopping image
- Lifestyle image
- YouTube Shorts

Website
- PDP video
- Hero section
- Gift guide module
```

这个流程可以先用预生成内容实现，不需要实时生成。关键是让老板看到完整链路。

---

## 7.3 Demo 2：VOC → Product Concept

这个 Demo 用 Learning Tower 或 Rocker 做。

页面结构：

```text
Step 1: Import review themes
Step 2: AI clusters pain points
Step 3: AI proposes product improvements
Step 4: AI generates concept cards
Step 5: AI generates launch test assets
```

输出示例：

```text
Pain point cluster:
- Takes too much space
- Assembly is confusing
- Parents want safer kitchen participation
- Hard to store in small homes

New concept:
SpaceSmart Foldable Learning Tower

Key features:
- Fold-flat design
- Rounded edges
- Wider base
- Two-sided activity board
- Small kitchen friendly
```

配 4 张概念卡：

```text
Folded position
Open kitchen use
Detail close-up
Comparison with standard tower
```

附件中已经有 “从差评到概念图” 的产品创新演示链路：导入评论数据、聚类痛点、生成产品方向、输出概念图和测试素材。

---

## 7.4 Demo 3：Weekly Growth Assistant

这个 Demo 不要做成聊天机器人，应该做成 dashboard。

```text
This week’s growth opportunities

1. Pink Unicorn Rocker
Opportunity: gift content underused
Action: create first birthday campaign
Assets needed: 3 TikToks, 1 PDP video, 1 gift guide module

2. Learning Tower
Opportunity: foldable feature not visible enough
Action: add folded/open comparison to PDP and ad creatives

3. Pretend Play Kitchen
Opportunity: high visual potential
Action: create “tiny chef morning routine” video series
```

再加审批状态：

```text
Draft generated
Needs brand review
Needs safety review
Approved
Published
```

这会体现“可审批、可追责”，不是简单 AI 聊天。

---

# 8. 组件级修改清单

下面是可以直接给开发 / Kimi / 设计团队执行的修改清单。

---

## 8.1 Navigation.tsx

当前问题：

```text
Home / Explore / Our Story / Play / Contact
右侧 Lorenz 动效按钮
没有购物车
没有搜索
没有真实 shop link
没有 mega menu
```

改成：

```text
Shop
Shop by Age
Shop by Room
Gift Guide
Montessori at Home
Watch It in Action
AI Growth Demo
Search
Cart
```

Mega menu：

```text
Shop
- Rockers & Ride-Ons
- Montessori Furniture
- Pretend Play
- Activity & Learning
- Storage & Room
- Outdoor Play

Shop by Age
- 6–18 months
- 18–36 months
- 3–6 years
- 6+ years

Shop by Room
- Nursery
- Playroom
- Kitchen
- Bedroom
- Outdoor
```

删除 LorenzCanvas。这个动效和 Labebe 无关，会分散注意力。

---

## 8.2 Hero.tsx

当前问题：

```text
只有 Discover
没有产品图
没有强 CTA
没有真实品牌主张
没有可购物入口
```

改成：

```tsx
<Hero
  eyebrow="More Brave, More You"
  title="Create a Warm, Playful Space for Every Little Milestone"
  subtitle="Montessori-inspired furniture, plush rockers and wooden pretend play sets for children from 6 months to 10 years old."
  primaryCta="Shop by Age"
  secondaryCta="Explore Gift Picks"
  heroImage="/images/hero-labebe-room.webp"
/>
```

下方加：

```text
Free US Shipping
FSC-certified wood
Non-toxic finishes
ASTM / EN71 tested
```

---

## 8.3 BrandIntro.tsx

当前文案太泛：

```text
From building blocks to musical instruments...
```

Labebe 当前抓取商品里并不是以 building blocks 和 musical instruments 为主，而是 furniture、rockers、pretend play、activity toys。

改成：

```text
From first rockers to kitchen helpers, from pretend play worlds to calm storage corners, Labebe helps children move, imagine, organize and grow at home.
```

---

## 8.4 CollectionShowcase.tsx

当前分类要全部替换。

新数据：

```ts
const WORLDS = [
  {
    name: 'Giftable Rockers',
    description: 'Soft animal rockers for first birthdays and nursery moments.',
    count: 13,
    image: '/images/14_ref_pink_unicorn_rocker.jpg',
    href: '/collections/giftable-rockers',
  },
  {
    name: 'Montessori at Home',
    description: 'Learning towers, shelves and desks for everyday independence.',
    count: 17,
    image: '/images/16_ref_foldable_learning_tower.jpg',
    href: '/collections/montessori-at-home',
  },
  {
    name: 'Tiny Pretend Worlds',
    description: 'Kitchens, coffee shops and mud kitchens for big imagination.',
    count: 9,
    image: '/images/17_ref_cream_play_kitchen.jpg',
    href: '/collections/pretend-play-worlds',
  },
  {
    name: 'Activity & Learning',
    description: 'Busy boards, easels and activity toys for focused little hands.',
    count: 6,
    image: '/images/20_ref_magnetic_easel_pink.jpg',
    href: '/collections/activity-learning',
  },
];
```

---

## 8.5 FeaturedProduct.tsx

当前问题：

```text
价格错
年龄可能错
按钮无链路
没有评论
没有真实 badge
没有安全信息
```

改成从数据读取：

```tsx
<FeaturedProduct product={products['pink-unicorn-plush-rocker']} />
```

展示：

```text
$109.99
18 reviews
Age 1–3Y
Gift Pick
Nursery Favorite
```

并加：

```text
[Add to Cart] [View Product]
```

---

## 8.6 BrandStory.tsx

当前必须重写。

删除：

```text
designed in Stockholm
EST. 2012
```

改成：

```text
Born from rocking horses

Labebe began with wooden rocking horses — timeless pieces that spark imagination and build confidence. Today, our collection has grown into Montessori-inspired furniture, pretend play sets and warm wooden essentials for children from 6 months to 10 years old.

More Brave, More You.
```

这与官方 About 页一致。([Labebe Club][4])

---

## 8.7 VideoSection.tsx

当前问题：

```text
poster 用 contact sheet
缩略图点击不切换视频
视频不是按产品组织
```

改成：

```text
Watch It in Action
```

视频卡数据：

```ts
const VIDEOS = [
  {
    title: 'First Birthday Rocker',
    product: 'Pink Unicorn Plush Rocker',
    platform: ['PDP', 'TikTok', 'Meta'],
    poster: '/images/03_storyboard_pink_unicorn_rocker.jpg',
    src: '/videos/pink-unicorn-demo.mp4',
  },
  {
    title: 'Kitchen Helper Moment',
    product: 'Foldable Learning Tower',
    platform: ['PDP', 'Amazon', 'Reels'],
    poster: '/images/16_ref_foldable_learning_tower.jpg',
    src: '/videos/learning-tower-demo.mp4',
  },
];
```

---

## 8.8 Reviews.tsx

当前评论应改成两层：

```text
1. Real product review signals
2. Parent moment quotes
```

如果没有真实评论原文，就展示：

```text
Review themes from real product pages
```

不要伪造具体用户评价。

---

## 8.9 Newsletter.tsx

当前：

```text
Join Our Adventure
```

太泛。

改成更有价值的 lead magnet：

```text
Get the First Birthday Gift Guide

A simple guide to choosing safe, beautiful wooden gifts by age, room and play style.

[Email]
[Send me the guide]
```

或者：

```text
Get the Montessori Room Setup Checklist
```

这样邮件订阅才有转化意义。

---

## 8.10 Footer.tsx

当前 Footer 也是通用的。

改成真实结构：

```text
Shop
- Rockers & Ride-Ons
- Kids Furniture
- Pretend Play
- Activity Toys
- New In
- Sale

Guides
- Shop by Age
- Shop by Room
- Gift Guide
- Montessori at Home
- Product Care

Support
- Shipping
- Returns
- FAQ
- Contact
- Assembly Guides

Brand
- About Labebe
- More Brave, More You
- Safety & Materials
```

保留真实联系方式，但要注意排版更高级。

---

# 9. 技术上怎么做到世界级

## 9.1 不要再做单页假网站

Kimi 版现在是一个 SPA 首页。世界级 Demo 至少要有：

```text
首页
集合页
PDP
购物车抽屉
AI Growth Demo
```

建议技术结构：

```text
src/
  data/
    products.ts
    collections.ts
    demoAssets.ts
    reviewThemes.ts

  routes/
    Home.tsx
    CollectionPage.tsx
    ProductPage.tsx
    ShopByAge.tsx
    ShopByRoom.tsx
    AIGrowthDemo.tsx
    OneSkuDemo.tsx
    VocToProductDemo.tsx

  components/
    ProductCard.tsx
    CartDrawer.tsx
    VideoCard.tsx
    TrustBadges.tsx
    AgeFinder.tsx
    RoomBuilder.tsx
    AssetMatrix.tsx
    WorkflowTimeline.tsx

  sections/
    Hero.tsx
    FourWorlds.tsx
    BestSellers.tsx
    WatchItInAction.tsx
    GiftableRockers.tsx
    MontessoriAtHome.tsx
```

---

## 9.2 图片和视频要按性能重做

当前 Kimi 版 assets 里有些图片超过 800KB，视频约 5MB。作为 Demo 可以接受，但如果要世界级，必须做性能优化。

目标：

```text
Hero 图片：WebP / AVIF，桌面 1920px，控制 300–500KB
移动 Hero：768–1024px，单独裁切
产品卡图：600–900px，不直接用大图
PDP 图：1200–2000px，懒加载
视频：首屏不自动加载大视频，用 poster + lazy load
```

Google 官方 Core Web Vitals 建议 LCP 在 2.5 秒内、INP 不超过 200ms、CLS 不超过 0.1。([web.dev][7])

所以不要全站放重 WebGL 背景。高端网站不是越重越高级。

---

## 9.3 SEO 和结构化数据

世界级 Demo 应该展示 SEO 能力，不一定真的上线，但代码结构要对。

每个 PDP 要有：

```text
Product JSON-LD
price
availability
review count
image
description
brand
breadcrumb
FAQ
```

Google 的 Product structured data 能让产品信息在搜索结果中以更丰富方式呈现，例如价格、库存、评价、配送信息等。([Google for Developers][8])

Collection 页要有：

```text
title
meta description
canonical
breadcrumb
FAQ schema
internal links
```

---

## 9.4 购物车 Demo

即使不接真实支付，也要做一个本地 cart：

```ts
type CartItem = {
  slug: string;
  title: string;
  price: number;
  quantity: number;
  image: string;
};
```

体验：

```text
点击 Add to Cart
右侧 Cart Drawer 滑出
显示商品
显示推荐搭配
显示小计
按钮：Continue Shopping / Demo Checkout
```

推荐搭配规则：

```text
Pink Unicorn → Gift Wrap + Activity Cube + Corner Cabinet
Learning Tower → Play Kitchen + Montessori Shelf
Play Kitchen → Bakery Set + Washer Dryer
Montessori Shelf → Toy Storage Organizer + Activity Wall
```

---

# 10. 世界级视觉方向

我建议 Labebe 不要走“儿童彩虹乐园风”，而要走：

```text
Warm Premium Montessori Home
```

视觉关键词：

```text
奶油白
浅木色
柔粉
鼠尾草绿
温暖陶土色
少量深蓝作为 CTA
自然光
真实家居
儿童空间
礼赠场景
```

当前 Kimi 版的 cream、terracotta、sage、cobalt 色板可以保留，但要减少 cobalt 的突兀感。Cobalt 只用于 CTA 和 AI Demo，不要大面积出现。

---

## 10.1 字体建议

Kimi 版使用 Playfair Display + DM Sans + Architects Daughter。这个组合有一定高级感，但 Playfair 太偏编辑杂志，Architects Daughter 用多了会显得像手工博客。

建议：

```text
Display: Fraunces / Cormorant Garamond / Playfair Display
Body: Inter / DM Sans
Accent: 少量手写字体，仅用于 badge 或小标题
```

原则：

```text
标题温暖高级
正文清晰易读
手写元素少量点缀
```

---

## 10.2 图像风格

图片不应只是产品图，而要有三个层级：

```text
1. Product truth
真实商品图，准确展示结构

2. Lifestyle desire
家居场景，展示父母想要的生活方式

3. Demo intelligence
AI 生成 / 视频 / 多渠道资产矩阵，展示增长能力
```

---

# 11. 老板演示路径

世界级 Demo 必须考虑“怎么讲”。我建议 15 分钟演示这样走。

---

## 11.1 第 1 分钟：先看原问题

```text
原站已经能卖货，但还是传统商品目录；
Kimi 版更漂亮，但没有真实商业链路；
我们要做的是第三种：品牌升级 + 增长系统。
```

---

## 11.2 第 2–4 分钟：看新版首页

展示：

```text
Hero
按年龄导购
按房间导购
四大产品世界
Best Sellers
```

老板感受到：

```text
Labebe 不再只是卖单品，而是在卖儿童成长空间。
```

---

## 11.3 第 5–7 分钟：看一个 PDP

打开 Pink Unicorn Plush Rocker：

```text
视频
礼赠场景
安全说明
真实价格
评论
Add to Cart
搭配推荐
```

老板感受到：

```text
单个产品的转化力提升了。
```

---

## 11.4 第 8–11 分钟：打开 AI Growth Demo

选择 Pink Unicorn：

```text
One SKU → Amazon / TikTok / Meta / Google / Website
```

展示自动生成的：

```text
视频脚本
平台素材
广告文案
PDP 模块
Email 模块
```

老板感受到：

```text
AI 能把一个产品变成多渠道增长资产。
```

---

## 11.5 第 12–14 分钟：展示 VOC 到新品

选择 Learning Tower：

```text
评论痛点
空间占用
组装困难
安全感
```

生成：

```text
SpaceSmart Foldable Learning Tower
概念图
场景图
测试落地页
```

老板感受到：

```text
AI 不是只做营销，还能帮助产品创新。
```

---

## 11.6 第 15 分钟：收口

```text
30 天内我们可以交付：
1. 一个新版品牌电商 Demo
2. 五个真实 SKU 的 PDP
3. 一个单 SKU 多渠道素材裂变演示
4. 一个 VOC 到新品概念演示
5. 一套后续可接 Shopify / Amazon / Meta / TikTok 的数据结构
```

---

# 12. 最小可执行版本：7 天内做到“非常惊艳”

如果时间紧，我建议不要铺太大。7 天做一个强 Demo，重点如下。

---

## Day 1：数据和结构

交付：

```text
products.ts
collections.ts
routes
导航
首页 wireframe
```

真实产品先放 12 个：

```text
Pink Unicorn Plush Rocker
Highlander Cattle Plush Rocker
Llama Plush Rocker
Activity Cube Baby Push Walker
Foldable Learning Tower
Natural Wood Montessori Shelf
Kids Toy Storage Organizer
Cream Wooden Play Kitchen
Kids Coffee Shop
Wooden Washer Dryer
Outdoor Mud Kitchen
Magnetic Easel
```

---

## Day 2：首页重做

完成：

```text
Hero
Quick Finder
Four Worlds
Best Sellers
Trust strip
```

---

## Day 3：PDP

完成 3 个 PDP：

```text
Pink Unicorn Plush Rocker
Foldable Learning Tower
Cream Wooden Play Kitchen
```

每个 PDP 有：

```text
Gallery
Video placeholder
真实价格
真实 review count
Add to Cart
Safety
Dimensions placeholder
Bundle recommendation
FAQ
```

---

## Day 4：AI Growth Demo 第一条链路

完成：

```text
One SKU → Multi-Channel Asset Matrix
```

用 Pink Unicorn 做。

---

## Day 5：AI Growth Demo 第二条链路

完成：

```text
VOC → Product Concept
```

用 Learning Tower 做。

---

## Day 6：动效和视觉 polish

只做有意义的动效：

```text
Hero 场景 parallax
产品卡 hover
Finder 推荐过渡
Asset matrix 生成动画
Cart drawer
Workflow timeline
```

---

## Day 7：演示脚本和细节修正

完成：

```text
15 分钟演示路径
老板版讲稿
移动端适配
性能检查
错别字和数据一致性检查
```

---

# 13. 现在最应该改的 P0 清单

如果你现在让 Kimi 或开发继续改，我建议第一轮只下这 15 条硬要求。

```text
P0-01 删除错误品牌故事：Stockholm、EST.2012、handcrafted artisans。
P0-02 用官方品牌故事：More Brave, More You、wooden rocking horses 起源、6m–10y。
P0-03 删除 Building Blocks / Musical Play 等不匹配分类。
P0-04 改成真实业务入口：Giftable Rockers / Montessori at Home / Pretend Play / Activity & Learning / Storage & Room。
P0-05 修正 Pink Unicorn 价格为 $109.99。
P0-06 所有产品数据从统一 products.ts 读取。
P0-07 Hero 加真实产品场景、真实 CTA、真实信任条。
P0-08 Navigation 加 Shop by Age、Shop by Room、Gift Guide、AI Growth Demo、Search、Cart。
P0-09 Collection card 可点击到真实集合页。
P0-10 至少做 3 个 PDP。
P0-11 Add to Cart 接本地 Cart Drawer。
P0-12 VideoSection 不再用 contact sheet 作为主视频封面。
P0-13 Reviews 不再写泛用假评论，改成真实 review signals。
P0-14 增加 AI Growth Demo：One SKU → Multi-Channel Asset Matrix。
P0-15 减少无关 WebGL / 炫技动效，把动效用于导购和素材裂变。
```

---

# 14. 我会怎么定义最终“世界级 Demo”验收标准

## 14.1 品牌验收

```text
打开 5 秒能看懂 Labebe 是什么品牌。
不会出现任何虚假品牌历史。
视觉像高端儿童家居 / 蒙氏木玩品牌。
```

## 14.2 电商验收

```text
有真实产品数据。
有真实价格和评论数。
有集合页。
有 PDP。
有 Add to Cart。
有推荐搭配。
```

## 14.3 导购验收

```text
可以按年龄买。
可以按房间买。
可以按礼物买。
可以按玩法买。
可以从父母痛点进入。
```

## 14.4 AI Demo 验收

```text
能展示一个 SKU 如何裂变成多渠道资产。
能展示评论 / VOC 如何转成新品概念。
能展示人工审批和发布流程。
```

## 14.5 老板观感验收

老板看完应该能说出：

```text
这不是一个网页；
这是 Labebe 未来品牌、电商、内容和 AI 增长的样板。
```

---

# 15. 给 Kimi 的下一轮提示词

你可以直接把下面这段给 Kimi，让它按这个方向重做。

```text
你现在不是做一个漂亮首页，而是重做 Labebe 世界级品牌电商 + AI 增长演示 Demo。

必须基于真实 Labebe 产品数据，不许编造品牌历史、价格、年龄、认证和评论。

当前 Kimi 版的问题：
1. 品牌故事错误，不能写 Stockholm、EST.2012、handcrafted artisans。
2. 产品分类不真实，不能用 Building Blocks、Musical Play 这种泛用木玩分类。
3. Pink Unicorn 价格错误，必须使用真实数据 $109.99。
4. 首页没有真实购买路径。
5. 没有集合页、PDP、Cart Drawer。
6. 没有 AI Growth Demo。
7. 动效过多但与业务无关。

请重做为双层 Demo：

A. Consumer Experience
- 首页
- Shop by Age
- Shop by Room
- Giftable Rockers
- Montessori at Home
- Pretend Play Worlds
- Playroom Reset
- Product Detail Page
- Cart Drawer

B. AI Growth Demo
- One SKU → Multi-Channel Asset Matrix
- VOC → Product Concept
- Weekly Growth Assistant
- Workflow approval timeline

首页模块顺序：
1. Hero：Create a Warm, Playful Space for Every Little Milestone
2. Quick Finder：按年龄 / 房间 / 礼物 / 玩法推荐
3. Four Worlds：Giftable Rockers / Montessori at Home / Tiny Pretend Worlds / Playroom Reset
4. Best Sellers：真实 SKU 卡片
5. Watch It in Action：真实产品视频卡
6. Trust & Safety：FSC / non-toxic / ASTM / EN71
7. AI Growth Studio Teaser
8. Reviews / Parent Moments
9. Newsletter：Gift Guide 或 Montessori Room Checklist
10. Footer

必须创建：
- data/products.ts
- data/collections.ts
- components/ProductCard.tsx
- components/CartDrawer.tsx
- components/QuickFinder.tsx
- components/AssetMatrix.tsx
- routes/ProductPage.tsx
- routes/AIGrowthDemo.tsx

首批真实 SKU：
- Pink Unicorn Plush Rocker
- Highlander Cattle Plush Rocker
- Foldable Learning Tower
- Natural Wood Montessori Shelf
- Kids Toy Storage Organizer
- Cream Wooden Play Kitchen
- Kids Coffee Shop
- Wooden Washer Dryer
- Outdoor Mud Kitchen
- Activity Cube Baby Push Walker
- Magnetic Easel
- Elephant Activity Wall Busy Board

视觉方向：
Warm Premium Montessori Home，不要廉价卡通风，不要无关科技风。
动效只服务导购、购物车、产品演示和 AI 素材裂变，不要炫技。

最终目标：
老板打开后 15 分钟内能看懂：
1. Labebe 可以升级成儿童成长空间品牌；
2. 原站可以从商品网格变成场景化购买路径；
3. 一个 SKU 可以在 48 小时内裂变成 Amazon / TikTok / Meta / Google / 独立站素材；
4. AI 可以从评论和痛点生成产品概念与上市测试素材。
```

---

# 16. 最终判断

Kimi 版现在最大的问题不是“不够漂亮”，而是 **漂亮和业务脱节**。

原站的问题是：

```text
能卖货，但不够世界级；
有产品，但没有场景化品牌系统；
有商品网格，但没有增长故事。
```

Kimi 版的问题是：

```text
有气氛，但不够真实；
有动效，但没有购买路径；
有页面，但没有 AI 增长演示；
有设计，但没有 Labebe 的业务灵魂。
```

真正的世界级 Demo 应该做到：

```text
打开首页：像一个高端儿童成长空间品牌；
点击商品：像一个能真实转化的电商站；
进入 AI Growth Demo：像一个可以改变公司增长方式的系统；
演示 15 分钟：老板能立刻决定继续投入下一阶段。
```

我建议下一步不要让 Kimi 继续“美化当前页面”，而是直接按上面的结构重做。当前 Kimi 版可以保留的只有色彩方向、部分图片资产和少量滚动动效；信息架构、品牌文案、产品数据、购买链路和 AI Demo 层都要大改。

[1]: https://labebeclub.com/ "Montessori Toys & Wooden Toys for Toddlers | Labebe"
[2]: https://labebeclub.com/collection/furniture "Montessori Toys & Wooden Toys for Toddlers | Labebe"
[3]: https://labebeclub.com/collection/rockers-ride-ons "Montessori Toys & Wooden Toys for Toddlers | Labebe"
[4]: https://labebeclub.com/pages/about-us?srsltid=AfmBOooZySucrG8wbgRL-OgU3eeGYVP7ZcaisSVl6_ya3wXdUrCxew5y "About Labebe | Montessori-Inspired Wooden Toys for Kids"
[5]: https://labebeclub.com/product/pink-unicorn-plush-rocker "Cute Pink Unicorn Rocking Horse with Safety Belt | Labebe"
[6]: https://labebeclub.com/product/foldable-learning-tower-montessori-kitchen-tower-log-color "Foldable Montessori Learning Tower & Kitchen Helper Stool | Labebe"
[7]: https://web.dev/articles/vitals?utm_source=chatgpt.com "Web Vitals | Articles"
[8]: https://developers.google.com/search/docs/appearance/structured-data/product?utm_source=chatgpt.com "Intro to Product Structured Data on Google"
# Labebe 世界级 Demo 设计素材与参考库

我会把设计素材分成 **7 个素材层** 来收集和使用，而不是简单丢一堆链接给 Kimi。Labebe 这个 Demo 最核心的视觉定位应该是：

> **Warm Premium Montessori Home + Giftable Childhood Moments + AI Growth Studio**

也就是：前台像一个高端儿童成长空间品牌，后台 / 演示层像一个 AI 原生增长工作室。

这个方向和 Labebe 现有素材高度匹配：附件里抓到 46 个产品，主要集中在 furniture、rockers-ride-ons、pretend-play、activity-educational-toys、new-in 五类；现有图片也已经形成了毛绒摇马、蒙氏家具、Pretend Play、收纳 / 活动墙几条强视觉赛道。
同时，之前上下文包已经明确提醒：Labebe 的 AI 方案不能停在“AI 画图 / AI 写文案 / AI 投广告”，要做成可演示、可审批、可追踪、可持续运行的增长链路。

---

# 1. 同类型优秀品牌网站借鉴

这一组是最重要的。Kimi 现在的问题是“漂亮但不像 Labebe，也不像能卖货的儿童家居品牌”。所以第一批素材要看同类优秀品牌：儿童木玩、蒙氏家具、婴幼儿家具、高端儿童房、礼赠型玩具。

## 1.1 Lovevery：年龄阶段导购与“专家感”标杆

**适合借鉴：**

* `Shop by Age`
* 成长阶段导购
* 专家背书
* Play Guide / 使用指南
* 订阅式内容逻辑
* 父母教育焦虑的温柔化表达

Lovevery 首页很强的一点是它不是按产品类目卖，而是按儿童年龄 / 成长阶段卖；它明确提供 0–12 months、1-year-old、2-year-old、3-year-old、4-year-old 等年龄入口，并强调 Play Kits、Play Guide、week-by-week developmental tips。([Lovevery][1])

**Labebe 怎么借：**

| Lovevery 做法    | Labebe 改造                                  |
| -------------- | ------------------------------------------ |
| Explore by Age | 首页第二屏做 `Shop by Age`：6–18m、18–36m、3–6y、6y+ |
| Play Guide     | 每个重点 SKU 做 `How to Play / How to Use`      |
| 专家感            | 不要乱写专家认证，但可以做 `Developmental Benefits`     |
| 每阶段玩具组合        | 做 `Room Setup by Age`                      |
| 订阅式逻辑          | 不必做订阅，可做 `Gift Guide / Growth Guide`       |

**可截图收集：**

```text
Lovevery 首页 Hero
Lovevery Explore by Age 模块
Play Kits 产品页
Play Guide / App / 使用指南模块
Gift / Registry 模块
```

---

## 1.2 Lalo：成人审美的儿童用品

**适合借鉴：**

* “给孩子用，但让成人也愿意摆在家里”
* 品牌语气非常适合 Labebe 从玩具站升级到儿童家居站
* 简洁、亲切、现代的 DTC 视觉
* Verified Customer 评论与礼赠语境

Lalo 的品牌表达非常值得 Labebe 学。它直接说自己做的是 “baby & toddler essentials for the adults in the room”，并强调产品 safe、beautiful、built to last。([Lalo][2])

**Labebe 怎么借：**

| Lalo 做法                        | Labebe 改造                                     |
| ------------------------------ | --------------------------------------------- |
| Their Size, Your Style         | `Their Play, Your Home`                       |
| Designed by Parents            | `Designed for everyday family spaces`         |
| Safe, beautiful, built to last | `Safe, warm, made for growing kids`           |
| 成人审美                           | 摇马、学习塔、收纳架全部拍在真实家居场景里                         |
| 礼赠评论                           | Pink Unicorn Rocker 做 `Grandparent Gift Pick` |

**可截图收集：**

```text
Lalo 首页首屏
Our Values 模块
评论模块
产品卡片
品牌语气
```

---

## 1.3 Milton & Goose：高端 Pretend Play 与“传家感”

**适合借鉴：**

* Play Kitchen / Play Market / Play Furniture 的高端定位
* “Heirloom Play” 叙事
* 高客单价但仍然有购买说服力
* 真实木材、手工、居家融合
* 类目结构很适合 Labebe 的 pretend-play 线

Milton & Goose 的首页明确把自己定位为 “Heirloom Play, Made for Childhood”，并强调 thoughtfully crafted furniture、real wood、made in USA、play kitchens、storage、outdoor play、decor 等结构。([Milton & Goose][3])

**Labebe 怎么借：**

| Milton & Goose 做法    | Labebe 改造                                                                    |
| -------------------- | ---------------------------------------------------------------------------- |
| Heirloom Play        | `Giftable pieces for little milestones`                                      |
| Play Kitchens 高端场景   | Cream Wooden Play Kitchen 做小厨师场景视频                                           |
| Shop by Category     | `Pretend Play Worlds`：Kitchen / Coffee Shop / Bakery / Laundry / Mud Kitchen |
| 高端木材叙事               | Labebe 强化 wood、rounded edges、home-friendly design                            |
| Featured In / Values | Labebe 暂时不要伪造媒体露出，先做 Safety & Materials                                      |

**可截图收集：**

```text
Milton & Goose 首页 Hero
Shop by Category
Most Loved Pieces
Play Kitchen PDP
Our Values 模块
Designing Spaces for Childhood 模块
```

---

## 1.4 Little Partners：学习塔 / 蒙氏家具功能叙事

**适合借鉴：**

* Learning Tower 的产品教育
* 安全、独立、亲子互动
* Montessori kid’s furniture 的类目语言
* 适合 Labebe 的 learning tower、easel、art center、step stool、cubby 等家具线

Little Partners 明确说其 Montessori kids furniture 可以为孩子提供 safe and sustainable environment，帮助孩子 learn independence and interact with adults。([Little Partners][4])

**Labebe 怎么借：**

| Little Partners 做法        | Labebe 改造                                         |
| ------------------------- | ------------------------------------------------- |
| Independence              | `Let them join everyday family routines`          |
| Interact with adults      | Learning Tower 场景一定要有 parent-child kitchen moment |
| Eco-friendly / Montessori | 不要滥用 Montessori，改成 `Montessori-inspired`          |
| 原创 Learning Tower 权威感     | Labebe 可用安全、折叠、收纳、小空间作为差异化                        |

**可截图收集：**

```text
Learning Tower 产品页
安全说明模块
Assembly / instruction 模块
Montessori furniture collection
功能对比图
```

---

## 1.5 Crate & Kids：儿童房空间服务与 Room Makeover

**适合借鉴：**

* 儿童房设计服务
* Playroom Makeover
* Mood Board
* 3D / 2D 空间规划概念
* “不是卖单品，而是卖儿童空间”

Crate & Kids 的 Kids Design Desk 提供 playroom、bedroom、homework area 等儿童空间的免费设计服务，并强调可通过到店、上门或视频沟通来完成儿童房设计。([Crate & Barrel][5])

**Labebe 怎么借：**

| Crate & Kids 做法       | Labebe 改造                                                       |
| --------------------- | --------------------------------------------------------------- |
| Free Kids Design Desk | Demo 里做 `Build Your Labebe Room`                                |
| Playroom Makeover     | `Playroom Reset` 页面                                             |
| Mood Board            | AI Growth Demo 里做 `AI Room Board Generator`                     |
| Shop Rooms            | `Shop by Room`：Nursery / Playroom / Kitchen / Bedroom / Outdoor |
| Design Services       | 先不承诺真实服务，Demo 中做交互式房间推荐                                         |

**可截图收集：**

```text
Kids Interior Design 页面
Room Makeover 案例
Shop Rooms 导航
Design Desk CTA
空间规划 / moodboard 风格
```

---

## 1.6 Pottery Barn Kids：礼赠、Registry、Room、Collaboration

**适合借鉴：**

* Baby Registry
* Gift Guide
* Design Boards
* Shop Rooms
* Collaborations
* 促销条 / 信任条 / 顶部服务入口

Pottery Barn Kids 网站顶部同时提供 expert design advice、Better-for-Baby Registry、Free Shipping、Design Boards、Registry、Favorites、Shop Rooms、Collaborations 等入口，说明高端儿童零售不是单纯产品网格，而是“购物 + 礼赠 + 房间 + 服务”的组合。([Pottery Barn Kids][6])

**Labebe 怎么借：**

| Pottery Barn Kids 做法 | Labebe 改造                                      |
| -------------------- | ---------------------------------------------- |
| Baby Registry        | `Baby Shower Gifts` / `First Birthday Gifts`   |
| Design Boards        | `Room Setup Ideas`                             |
| Shop Rooms           | `Shop by Room`                                 |
| Collaborations       | 暂时不要硬做联名，先做 seasonal collection                |
| 顶部服务条                | Free US Shipping、Safe Materials、30-day Returns |

**可截图收集：**

```text
顶部服务条
Baby Registry 入口
Shop Rooms 导航
Design Boards 入口
Gift 页面
```

---

## 1.7 Maisonette：童装 / 玩具 / 家具精选买手店

**适合借鉴：**

* “专家精选 / editorial curation”
* 高端儿童生活方式市场感
* Newsletter 文案更轻盈
* 适合 Labebe 后续做 Gift Guide 和 Buyer’s Edit

Maisonette 定位为 kids and baby clothing、furniture、decor、toys 的精选目的地，并用 “expert edits” 做编辑式导购。([Maisonette][7])

**Labebe 怎么借：**

| Maisonette 做法  | Labebe 改造                                     |
| -------------- | --------------------------------------------- |
| Expert edits   | `Labebe Picks by Age`                         |
| Kids boutique  | `Curated wooden pieces for warm family homes` |
| Fresh arrivals | `New In` 不要只放 1 个新品，要做新品机制                    |
| Newsletter     | `Get the First Birthday Gift Guide`           |

---

## 1.8 Tender Leaf Toys：木玩世界观与插画感

**适合借鉴：**

* Wooden toy brand 的温暖世界观
* Award / sustainability badge
* 轻度童话感
* 适合 Labebe 的 Pretend Play 与动物摇马系列

Tender Leaf Toys 强调 “Love wood & play”，并把自己表达为 beautifully crafted、eco-friendly toys and gifts，还展示了 Junior Design Award 2025 的 Best Toy Brand 相关信息。([Tender Leaf][8])

**Labebe 怎么借：**

| Tender Leaf 做法           | Labebe 改造                                |
| ------------------------ | ---------------------------------------- |
| Love wood & play         | `Wooden play, warm homes`                |
| Awarded Toys             | Labebe 如有真实奖项可展示；没有就不要编                  |
| Whimsical product worlds | `Animal Friends` / `Tiny Pretend Worlds` |
| 插画感                      | 用于 guide / gift 页面，不要覆盖真实产品图             |

---

## 1.9 Nestig / Oeuf / Ferm Living Kids：高端儿童房美学

**适合借鉴：**

* Nursery / Kids Room 的空间感
* “built to grow” 成长性
* 家居级儿童家具语言
* muted colors / Scandinavian / timeless design
* 适合 Labebe furniture 类目升级

Nestig 强调 heirloom quality convertible cribs、kids beds、wallpaper、shelves，并提供 design advice 类内容；Oeuf 定位为现代、环保 baby and child furniture；Ferm Living Kids 强调儿童房要兼顾 style、functional storage、personal style、timeless design。([Nestig][9])

**Labebe 怎么借：**

| 做法               | Labebe 改造                                  |
| ---------------- | ------------------------------------------ |
| Heirloom quality | 礼赠摇马和木制家具做 `lasting pieces`                |
| Built to grow    | `Grow-with-me furniture`                   |
| Kids room style  | 把 shelf、desk、corner cabinet 做成 room set    |
| Design advice    | 建博客 / guide：`How to build a calm playroom` |

---

# 2. 世界级非同类网站设计借鉴

这组不是儿童品牌，但很适合 Kimi 做“世界级 Demo 效果”：信息密度、动效节奏、产品叙事、AI 工作流展示。

## 2.1 Linear：系统感、速度感、AI 工作流感

Linear 官网的核心价值是高密度但极克制的产品叙事。它把自己表达为 “system for product development”，并明确强调 AI workflows、purpose-built、speed、focus。([Linear][10])

**Labebe 借法：**

```text
用 Linear 的“系统感”做 AI Growth Studio，
不要用儿童风做后台演示。
```

适合借鉴模块：

```text
AI Growth Studio 首屏
Workflow timeline
Asset matrix
Dashboard cards
Subtle dark mode
高密度信息卡片
```

---

## 2.2 Raycast：Command Center 式产品演示

Raycast 的官网强调 “Your shortcut to everything”，用清晰的产品能力结构讲述“一个入口连接很多工具”。([Raycast][11])

**Labebe 借法：**

```text
把 AI Growth Demo 做成 “Labebe Command Center”：
选择 SKU → 生成脚本 → 生成素材 → 分发渠道 → 审批发布。
```

适合借鉴模块：

```text
Command palette
Quick actions
Tool cards
Compact product screenshots
Workflow shortcuts
```

---

## 2.3 Framer：设计自由、SEO、性能、AI 生成页面

Framer 官网强调 custom websites、CMS、SEO、real-time collaboration，并展示 Lighthouse 的 SEO / Performance / Accessibility 分数。([Framer][12])

**Labebe 借法：**

```text
世界级 Demo 不只要好看，还要展示：
Performance
SEO
Accessibility
Mobile-first
CMS-ready
```

适合借鉴模块：

```text
Performance badge
SEO-ready page preview
Responsive breakpoint demo
On-page editing / CMS-ready 提示
```

---

## 2.4 Stripe Atlas：复杂服务的清晰解释

Stripe Atlas 页面非常适合借鉴“复杂流程如何讲简单”：它把公司注册这种复杂事情变成 step-by-step 的可信流程，并加入法律 / 信任 / 限制说明。([Stripe][13])

**Labebe 借法：**

```text
AI Growth Demo 里所有自动化都要有：
Input
AI Process
Human Review
Output
Risk / Approval
```

适合借鉴模块：

```text
Process cards
Legal / compliance note
Trust section
Step-by-step onboarding
```

---

# 3. 设计系统与 Agent 文档素材

你提到的 “Claude Design / Google 的 design.md” 方向非常关键。它本质上不是一个普通设计文档，而是让 AI coding agent 不再每次从零猜颜色、字体、间距、按钮，而是能读取一个固定的视觉系统。

## 3.1 Google Stitch / DESIGN.md

Google 已经把 DESIGN.md 的 draft specification 开源，官方说明它可以让 AI agents 不再猜设计意图，而是知道颜色用途，并能根据 WCAG 可访问性规则做校验；Stitch 也能在项目之间导入 / 导出设计规则。([blog.google][14])

Google Labs 的 GitHub 仓库说明，DESIGN.md 用来描述 visual identity，让 coding agents 获得 persistent、structured 的 design system 理解；同时它目前还是 alpha，CLI 可导出 Tailwind theme config 和 DTCG tokens.json。([GitHub][15])

**Labebe 借法：**

```text
必须给 Kimi / Claude / Cursor 一个 Labebe DESIGN.md，
否则它每次都会生成 generic pastel / default Tailwind / 假北欧风。
```

---

## 3.2 awesome-design-md / getdesign.md

VoltAgent 的 awesome-design-md 是一个收集 DESIGN.md 的项目，说明可以把某个品牌风格的 DESIGN.md 放进项目根目录，让 AI agent 生成更一致的 UI；它还区分了 `AGENTS.md` 负责“怎么构建”，`DESIGN.md` 负责“看起来应该是什么样”。([GitHub][16])

**Labebe 借法：**

```text
可以参考它的结构，但不能直接复制别的品牌 DESIGN.md。
我们要做的是 Labebe 专属 DESIGN.md：
儿童空间、礼赠、木质、蒙氏、AI Growth Studio 双视觉系统。
```

---

## 3.3 AGENTS.md

AGENTS.md 是给 coding agents 的项目说明文件，官方描述是一个专门给 agent 的 README，用于写清 build steps、tests、conventions、security considerations 等。它还说明嵌套 AGENTS.md 可以让不同子项目读取最近的规则。([Agents][17])

**Labebe 借法：**

```text
Labebe Demo 项目应该同时有：
DESIGN.md：规定视觉
AGENTS.md：规定怎么开发、测试、验收
CONTENT.md：规定文案语气、禁用词、产品数据来源
```

---

## 3.4 Claude Code Best Practices

Claude Code 官方 best practices 强调：先探索、再计划、再编码；要提供具体上下文；要写有效的 CLAUDE.md；要管理上下文窗口；要给 Claude 验证工作的方式。([Claude][18])

**Labebe 借法：**

```text
下一轮不要只给 Kimi 一句“做得更高级”。
要给它：
- DESIGN.md
- 产品数据
- 页面结构
- 竞品参考
- 组件验收标准
- 禁止事项
- 测试方式
```

---

## 3.5 Google Material 3 Expressive

Google Design 解释 Material 3 Expressive 是一次基于大量研究的设计系统更新，核心不是“花哨”，而是用 color、shape、size、motion、containment 引导注意力、增强情绪和可用性；Google 还提到它经历了 46 项研究、超过 18,000 名参与者。([Google Design][19])

**Labebe 借法：**

```text
Labebe 可以“温暖、情绪化、可爱”，但每个色块、动效、形状都要服务购买路径。
不要做没有业务意义的漂浮小球和炫技背景。
```

---

## 3.6 Apple HIG / Shopify Polaris / Google Design

Apple Human Interface Guidelines 是 Apple 官方平台设计规范；Shopify Polaris 提供 commerce/admin 相关的 foundations、patterns、components、tokens、icons；Google Design 是研究 Google 产品设计、字体、Material、AI 原型和 UX 的素材库。([Apple Developer][20])

**Labebe 借法：**

| 设计系统            | Labebe 用法                                    |
| --------------- | -------------------------------------------- |
| Apple HIG       | 克制、清晰、触控友好、移动端优先                             |
| Shopify Polaris | Cart、filter、badge、admin-like AI Studio 的组件逻辑 |
| Google Design   | AI 产品叙事、Material Expressive、字体和可访问性          |
| DESIGN.md       | 让 AI 生成页面不跑偏                                 |
| AGENTS.md       | 让 AI 开发过程不乱改、不乱编                             |

---

# 4. 灵感平台与素材检索库

这一组用来每天找“视觉参考”和“交互参考”，不是直接复制。

## 4.1 Awwwards

Awwwards 是顶级网站设计灵感库，会展示 Site of the Day、Honorable Mention、Developer Award 等获奖作品。([Awwwards][21])

**用于 Labebe：**

```text
找 Hero 动效
找长滚动叙事
找高端品牌质感
找 AI Growth Studio 的交互表达
```

搜索关键词：

```text
kids
furniture
ecommerce
luxury
interaction design
storytelling
product page
```

---

## 4.2 Land-book

Land-book 是 hand-picked website inspiration gallery，并且分类里有 Landing、Ecommerce、Product listing、Product page、Kids、Furniture & Interiors 等筛选项。([Landbook][22])

**用于 Labebe：**

```text
找电商首页
找产品页
找家具 / interior 布局
找 kids 类视觉
找 landing page 结构
```

---

## 4.3 Mobbin

Mobbin 收集真实产品的 UI / UX 设计模式，包含大量 screens、flows、UI elements；它特别适合找 Search、Checkout、Collections、Account Setup、Subscription 等真实流程。([Mobbin][23])

**用于 Labebe：**

```text
找移动端 checkout
找 cart drawer
找 filter / sort
找 onboarding quiz
找 AI Growth Studio dashboard
找产品推荐 flow
```

---

## 4.4 GSAP / Rive / LottieFiles / Motion

GSAP Showcase 收集了大量高质量 Web 动画案例；Rive 可以做可交互动画，并强调 design、animate、code in one place；LottieFiles 适合轻量动画素材；Motion 是生产级 React / JS / Vue 动画库，适合 scroll、exit、layout、timeline、spring 等 UI 动画。([GSAP][24])

**用于 Labebe：**

| 工具 / 平台     | 适合做什么                                          |
| ----------- | ---------------------------------------------- |
| GSAP        | 首页长滚动、素材矩阵裂变、房间场景动效                            |
| Rive        | 活动墙、学习塔、AI workflow 状态机                        |
| LottieFiles | 小图标动效、loading、trust badges                     |
| Motion      | React 页面里的卡片、cart drawer、filter、PDP gallery 动效 |

**Labebe 动效原则：**

```text
只做 5 类动效：
1. 产品进入房间场景
2. Shop by Age 推荐结果切换
3. Cart drawer
4. One SKU → Multi-channel asset matrix
5. Workflow approval timeline
```

不要再做和业务无关的 WebGL 科技球。

---

# 5. Labebe 应该重点收集的截图素材清单

下面这份可以直接交给设计师或 Kimi，让它按模块截图、贴到 moodboard。

## 5.1 首页 Hero 参考

| 参考               | 要截图的点                   | Labebe 用法         |
| ---------------- | ----------------------- | ----------------- |
| Lovevery         | 年龄导购 + 成长阶段感            | Hero 下方放年龄入口      |
| Lalo             | 成人审美 + 温柔 DTC 语气        | Hero 文案不要低幼       |
| Milton & Goose   | 高端玩具家具场景                | 用家居场景做主视觉         |
| Nestig           | nursery / kids room 空间感 | Labebe room setup |
| Ferm Living Kids | muted children room     | 色彩与收纳氛围           |

---

## 5.2 导航 / Mega Menu 参考

| 参考                | 要截图的点                                 | Labebe 用法                      |
| ----------------- | ------------------------------------- | ------------------------------ |
| Pottery Barn Kids | Shop Rooms / Registry / Design Boards | 导航加入 Shop by Room / Gift Guide |
| Milton & Goose    | Play / Furniture / Decor / Gifting    | Labebe 做世界观分类                  |
| Maisonette        | expert edits / boutique selection     | Gift Guide、Labebe Picks        |
| Crate & Kids      | design service / room entries         | Room Makeover 入口               |

---

## 5.3 PDP 产品页参考

| 参考              | 要截图的点                  | Labebe 用法                     |
| --------------- | ---------------------- | ----------------------------- |
| Little Partners | Learning Tower 安全与功能说明 | Learning Tower PDP            |
| Milton & Goose  | 高价 play kitchen 产品展示   | Pretend Play PDP              |
| Lovevery        | Play Guide / 使用教育      | 每个 SKU 的 How to Use           |
| Oeuf / Nestig   | 家具材质、成长性、空间图           | shelf、desk、corner cabinet PDP |

---

## 5.4 Gift Guide / Registry 参考

| 参考                | 要截图的点                           | Labebe 用法                           |
| ----------------- | ------------------------------- | ----------------------------------- |
| Pottery Barn Kids | Baby Registry / gift navigation | First Birthday Gift Guide           |
| Lovevery          | Gift The Play Kits              | Rocker gift collection              |
| Lalo              | baby shower gift 语气             | Grandparent gift / Baby Shower gift |
| Maisonette        | curated edits                   | `Labebe Gift Picks`                 |

---

## 5.5 AI Growth Studio 参考

| 参考                        | 要截图的点                          | Labebe 用法              |
| ------------------------- | ------------------------------ | ---------------------- |
| Linear                    | dark / glass / system cards    | AI dashboard           |
| Raycast                   | command center / quick actions | SKU command center     |
| Stripe Atlas              | complex process simplified     | VOC → Concept → Assets |
| Framer                    | performance / SEO / responsive | Demo 的工程可信度            |
| Google Stitch / DESIGN.md | AI design system portability   | Labebe DESIGN.md       |

---

# 6. Labebe 的素材情绪板方向

不要再让 Kimi 做“水彩梦幻儿童网站”。Labebe 的 Demo 应该分成两个视觉系统。

## 6.1 Consumer Site 视觉系统

关键词：

```text
warm wood
soft nursery
modern family home
Montessori calm
giftable plush
cream background
muted sage
dusty pink
natural oak
soft shadow
large lifestyle photography
editorial product cards
```

适合页面：

```text
首页
Shop by Age
Shop by Room
Giftable Rockers
Montessori at Home
Pretend Play Worlds
PDP
Gift Guide
```

## 6.2 AI Growth Studio 视觉系统

关键词：

```text
calm dark interface
soft glass panels
data cards
asset matrix
workflow timeline
approval states
channel chips
creative ID
human review
audit trail
```

适合页面：

```text
AI Growth Demo
One SKU → Multi-channel
VOC → Product Concept
Weekly Growth Assistant
Workflow Approval Timeline
```

这两个系统要有关联，但不要混成一个。前台温暖，后台冷静；前台卖给父母，后台演示给老板。

---

# 7. Labebe 页面模块借鉴矩阵

## 7.1 首页

| 首页模块                    | 参考来源                             | Labebe 具体做法                                                            |
| ----------------------- | -------------------------------- | ---------------------------------------------------------------------- |
| Hero                    | Lalo + Nestig + Lovevery         | 温暖儿童房场景 + 明确年龄 / 礼赠 CTA                                                |
| Shop by Age             | Lovevery                         | 6–18m、18–36m、3–6y、6y+                                                  |
| Shop by Room            | Crate & Kids + Pottery Barn Kids | Nursery、Playroom、Kitchen、Bedroom、Outdoor                               |
| Four Worlds             | Milton & Goose + Tender Leaf     | Giftable Rockers、Montessori at Home、Tiny Pretend Worlds、Playroom Reset |
| Best Sellers            | Labebe 抓取数据                      | 使用真实价格和评论数                                                             |
| Watch It in Action      | TikTok / PDP 视频化                 | 每个重点 SKU 15 秒演示                                                        |
| Trust & Safety          | Lovevery + Little Partners       | 安全、材质、测试、适龄                                                            |
| AI Growth Studio Teaser | Linear + Raycast                 | 一个 SKU 裂变为多渠道素材                                                        |

---

## 7.2 集合页

| 集合页                 | 参考来源                         | 关键模块                                           |
| ------------------- | ---------------------------- | ---------------------------------------------- |
| Giftable Rockers    | Pottery Barn Kids + Lalo     | Gift occasion、age、nursery、grandparent picks    |
| Montessori at Home  | Lovevery + Little Partners   | Independence、kitchen helper、toy rotation       |
| Pretend Play Worlds | Milton & Goose + Tender Leaf | Kitchen、coffee shop、bakery、laundry、mud kitchen |
| Playroom Reset      | Crate & Kids + Ferm Living   | Before / after、storage、room calmness           |
| Shop by Age         | Lovevery                     | age window + recommended setup                 |
| Shop by Room        | Crate & Kids                 | room moodboard + products                      |

---

## 7.3 PDP

| PDP 模块             | 参考来源                       | Labebe 具体做法                             |
| ------------------ | -------------------------- | --------------------------------------- |
| Product gallery    | 高端电商通用                     | 图片 + 视频 + 细节 + 尺寸                       |
| Watch it in action | Lovevery / Little Partners | 产品真实使用演示                                |
| Safety & Materials | Lovevery / Little Partners | 不夸大，不虚构认证                               |
| Room fit           | Nestig / Crate & Kids      | 尺寸、房间比例、搭配                              |
| Giftability        | Lalo / Pottery Barn Kids   | First birthday / baby shower            |
| Bundle             | Milton & Goose             | Kitchen + bakery；Rocker + activity cube |
| FAQ                | Shopify / Apple HIG 思路     | 年龄、尺寸、组装、清洁、安全                          |

---

## 7.4 AI Growth Demo

| 模块                        | 参考来源                 | Labebe 具体做法                                           |
| ------------------------- | -------------------- | ----------------------------------------------------- |
| Command Center            | Raycast              | 选择 SKU、触发任务                                           |
| Workflow System           | Linear               | 产品、素材、渠道、审批状态                                         |
| Process Explainer         | Stripe Atlas         | 输入 → AI → 审核 → 输出                                     |
| Design System Portability | Google DESIGN.md     | Labebe DESIGN.md 驱动 UI                                |
| Motion                    | GSAP / Motion / Rive | One SKU → Amazon / TikTok / Meta / Google / Site 卡片飞出 |

---

# 8. Labebe DESIGN.md v0.1 草案

下面这份可以直接作为 `DESIGN.md` 的第一版给 Kimi / Claude / Cursor。它不是最终设计系统，但可以显著减少 AI 乱生成的问题。

```md
# Labebe DESIGN.md

## 1. Design Intent

Labebe is a warm premium children's home and play brand.

The visual language should feel:
- warm, safe, soft, trustworthy
- Montessori-inspired but not overly academic
- giftable and emotionally memorable
- home-friendly for modern parents
- playful through product moments, not cheap cartoon decoration

Avoid:
- generic pastel SaaS UI
- overly childish cartoon style
- fake Scandinavian brand claims
- random WebGL or technology effects unrelated to shopping
- loud rainbow colors across the full interface
- fake reviews, fake awards, fake certifications

Primary brand expression:
"Warm Premium Montessori Home"

Secondary demo expression:
"AI Growth Studio"

---

## 2. Brand Principles

### Principle 1: Child wonder, adult taste
Products are for children, but the website should appeal to parents who care about home aesthetics.

### Principle 2: Product truth first
Never distort product shape, price, age range, safety claims, or review counts.

### Principle 3: Scenario before category
Users should discover products by:
- age
- room
- gift occasion
- play style
- parent goal

### Principle 4: Warm but structured
Use soft colors and rounded shapes, but keep layout clear, editorial, and premium.

### Principle 5: AI demo must feel operational
AI Growth Studio should look like a real workflow system, not a chatbot or gimmick.

---

## 3. Color Tokens

### Consumer Site Palette

--color-cream-50: #FFF9F1
Use for main page background.

--color-cream-100: #F7EFE2
Use for warm section backgrounds.

--color-oak-100: #E8D3B3
Use for wood-inspired surfaces and subtle cards.

--color-oak-300: #C89F68
Use for warm accents and product highlight lines.

--color-sage-100: #DDE8D6
Use for Montessori / calm room sections.

--color-sage-500: #7E9A77
Use for secondary CTA and badges.

--color-blush-100: #F6D6D4
Use for Giftable Rockers and soft emotional moments.

--color-blush-500: #D77F7A
Use for gift badges and selected states.

--color-clay-500: #B8664B
Use for primary warm CTA when the page is consumer-facing.

--color-ink-900: #2E2925
Use for primary text.

--color-ink-600: #6C625A
Use for secondary text.

--color-white: #FFFFFF
Use for product cards and PDP panels.

### AI Growth Studio Palette

--studio-bg: #101214
Use for AI Growth Studio dark background.

--studio-surface: #181B1F
Use for main panels.

--studio-surface-soft: #22262B
Use for cards and workflow steps.

--studio-line: #343A42
Use for dividers and borders.

--studio-text: #F5F3EE
Use for primary studio text.

--studio-muted: #A9A39A
Use for secondary studio text.

--studio-accent: #89B4FA
Use for AI actions, active chips, generated states.

--studio-success: #8CCF9E
Use for approved states.

--studio-warning: #E9B872
Use for needs-review states.

--studio-danger: #E17C7C
Use for rejected / blocked states.

---

## 4. Typography

### Display Font
Use a warm editorial serif for large marketing headlines.
Recommended options:
- Fraunces
- Cormorant Garamond
- Playfair Display

Use for:
- homepage hero title
- collection landing page titles
- gift guide titles
- storytelling pull quotes

### Body Font
Use a clean sans-serif.
Recommended options:
- DM Sans
- Inter
- Google Sans compatible fallback
- Nunito Sans only if a softer tone is needed

Use for:
- navigation
- PDP descriptions
- product cards
- filters
- AI Growth Studio

### Accent Font
Use very sparingly.
Optional:
- a handwritten accent for small labels only

Use for:
- "Gift Pick"
- "First Birthday Favorite"
- small editorial labels

Do not use handwritten font for paragraphs or product titles.

---

## 5. Type Scale

--text-xs: 12px / 16px
--text-sm: 14px / 20px
--text-md: 16px / 24px
--text-lg: 18px / 28px
--text-xl: 24px / 32px
--text-2xl: 32px / 40px
--text-3xl: 44px / 52px
--text-4xl: 64px / 72px

Desktop hero headline:
64px max, 52px preferred for warmth.

Mobile hero headline:
36px to 42px.

Body copy:
16px minimum.

Product card title:
16px to 18px.

---

## 6. Spacing

Base spacing unit: 8px

--space-1: 4px
--space-2: 8px
--space-3: 12px
--space-4: 16px
--space-5: 24px
--space-6: 32px
--space-7: 48px
--space-8: 64px
--space-9: 96px
--space-10: 128px

Page sections:
Desktop: 96px top/bottom
Mobile: 56px top/bottom

Cards:
24px internal padding desktop
16px internal padding mobile

---

## 7. Radius

--radius-sm: 8px
--radius-md: 16px
--radius-lg: 24px
--radius-xl: 32px
--radius-pill: 999px

Use large soft radius for consumer site cards.
Use medium radius for AI Studio system panels.

---

## 8. Shadows

Consumer shadows:
Soft, warm, low opacity.

--shadow-card: 0 12px 32px rgba(75, 55, 38, 0.08)
--shadow-hover: 0 20px 48px rgba(75, 55, 38, 0.14)

Studio shadows:
Minimal, mostly borders and glow.

--studio-glow: 0 0 40px rgba(137, 180, 250, 0.12)

Do not use harsh black shadows.

---

## 9. Imagery

Preferred imagery:
- real product photos
- warm home scenes
- nursery corners
- modern kitchens
- playrooms with natural light
- parent-child interaction
- organized shelves
- pretend play in action

Image rules:
- product shape must remain accurate
- no fake product functions
- no unsafe child usage
- no exaggerated scale
- avoid overly synthetic AI faces
- use AI-generated imagery only for concept or demo scenes, not as final product truth

---

## 10. Components

### Button

Primary consumer button:
- clay background
- white text
- pill radius
- medium weight
- hover: slightly darker clay
- text: clear verb

Examples:
- Shop by Age
- Explore Gift Picks
- Build Your Room

Secondary consumer button:
- transparent or cream
- ink text
- oak border

Studio primary button:
- studio-accent background
- studio-bg text
- compact, system-like

### Product Card

Required fields:
- product image
- title
- price
- review count when available
- age badge
- room badge
- play type badge
- 1-line benefit
- quick add
- view details

Product card should not look like a generic marketplace tile.
It should feel editorial and warm.

### Badge

Consumer badges:
- Gift Pick
- Best Seller
- Montessori-inspired
- New In
- Age 1–3Y
- Nursery Favorite

Studio badges:
- Draft
- Generated
- Needs Review
- Approved
- Published
- Blocked

### Collection Card

Each collection card needs:
- image
- collection name
- emotional subtitle
- product count
- best-for line
- CTA

Example:
Giftable Rockers
"First rides, first birthdays, first brave little moments."
13 products
Best for nurseries, milestone gifts and grandparent picks.

---

## 11. Motion

Motion should be soft, purposeful, and business-driven.

Approved motion:
- product card hover lift
- cart drawer slide
- filter chips transition
- PDP gallery fade
- room builder recommendation change
- AI asset cards expanding from one SKU
- workflow timeline progress
- approval state transitions

Avoid:
- unrelated floating orbs
- heavy WebGL backgrounds
- motion that blocks shopping
- excessive parallax
- childish bouncing animations everywhere

Motion duration:
- micro interactions: 120ms–180ms
- card transitions: 220ms–320ms
- section entrance: 420ms–600ms
- AI matrix generation: 800ms–1200ms

---

## 12. Page Templates

### Homepage

Required sections:
1. Hero
2. Shop by Age / Room / Gift / Play Type quick finder
3. Four Worlds
4. Best Sellers
5. Watch It in Action
6. Montessori at Home
7. Giftable Rockers
8. Trust & Safety
9. AI Growth Studio teaser
10. Reviews / Parent Moments
11. Gift Guide email capture
12. Footer

### PDP

Required sections:
1. Product gallery
2. Price / reviews / CTA
3. age, room, gift badges
4. core benefits
5. Watch It in Action
6. Safety & Materials
7. Dimensions & Fit
8. Assembly & Care
9. Bundle recommendations
10. FAQ
11. Related products

### AI Growth Studio

Required sections:
1. Studio overview
2. SKU selector
3. One SKU to multi-channel asset matrix
4. Script generation
5. Visual prompt generation
6. Asset cards for Amazon, TikTok, Meta, Google, Site
7. Review and approval timeline
8. Publishing readiness checklist
9. Performance learning loop

---

## 13. Content Voice

Voice:
- warm
- practical
- trustworthy
- parent-facing
- emotionally clear
- never overclaiming

Use:
- "for little milestones"
- "made for everyday family moments"
- "helps children participate"
- "keeps playrooms calmer"
- "giftable favorites"
- "watch it in action"

Avoid:
- "the safest"
- "#1"
- "guaranteed development"
- fake expert claims
- fake certifications
- fake country origin
- fake awards
- inflated AI ROI claims

---

## 14. Accessibility

Minimum:
- body text 16px
- visible focus states
- contrast must pass WCAG AA where possible
- buttons must be reachable by keyboard
- do not rely on color alone for status
- all product images need useful alt text
- video needs captions or text overlays
- motion should respect prefers-reduced-motion

---

## 15. Labebe Data Truth Rules

Use real product data where available:
- product title
- collection
- price
- review count
- image
- age range
- safety feature
- material
- URL slug

Do not invent:
- price
- review count
- awards
- certification
- origin story
- manufacturing location
- influencer quotes
- press mentions

When data is unknown, mark it as:
"To be confirmed"
```

---

# 9. Labebe AGENTS.md v0.1 草案

这个给开发 Agent，不是给视觉 Agent。

```md
# Labebe Demo AGENTS.md

## Project Goal

Build a world-class Labebe brand commerce and AI growth demo.

The demo has two layers:

1. Consumer Experience
A premium children's home and play ecommerce experience.

2. AI Growth Studio
A business-facing demo showing how one SKU becomes multi-channel marketing assets.

## Non-Negotiables

- Use real Labebe product data when provided.
- Do not invent brand history, awards, certifications, review counts or prices.
- Do not create generic toy categories unrelated to Labebe.
- Do not use random WebGL effects unless tied to business meaning.
- Every page must be mobile responsive.
- Every major component must be reusable.

## Required Routes

/
Homepage

/collections/giftable-rockers
Giftable Rockers collection

/collections/montessori-at-home
Montessori-inspired furniture collection

/collections/pretend-play-worlds
Pretend Play collection

/collections/playroom-reset
Storage and room collection

/shop/by-age
Age-based shopping

/shop/by-room
Room-based shopping

/product/:slug
Product detail page

/ai-growth-demo
AI Growth Studio overview

/ai-growth-demo/one-sku
One SKU to multi-channel asset matrix

/ai-growth-demo/voc-to-product
VOC to product concept demo

## Required Data Files

src/data/products.ts
src/data/collections.ts
src/data/demoAssets.ts
src/data/reviewSignals.ts
src/data/channelSpecs.ts

## Required Components

ProductCard
CollectionCard
QuickFinder
CartDrawer
PDPGallery
TrustBadges
VideoCard
AssetMatrix
WorkflowTimeline
ApprovalStatus
RoomBuilder

## Verification

Before finalizing:
- run type check
- check mobile layout
- check product data consistency
- verify all Add to Cart buttons open cart drawer
- verify all collection cards navigate somewhere
- verify no placeholder fake brand claims remain
- verify Lighthouse-oriented image lazy loading and alt text
```

---

# 10. 素材文件夹结构

建议把设计素材整理成这样的结构，让 Kimi / Claude / Cursor 都能读取。

```text
/labebe_design_reference_pack
  /00_strategy
    labebe_positioning.md
    visual_direction.md
    design_principles.md

  /01_same_category_references
    lovevery_age_based_play.md
    lalo_adult_taste_child_products.md
    milton_goose_heirloom_play.md
    little_partners_learning_tower.md
    crate_kids_room_design.md
    pottery_barn_kids_registry_gift.md
    tender_leaf_wooden_world.md
    nestig_kids_room_growth.md
    ferm_living_kids_home_aesthetic.md

  /02_world_class_web_references
    linear_ai_workflow_system.md
    raycast_command_center.md
    framer_performance_website.md
    stripe_atlas_process_explainer.md

  /03_page_patterns
    homepage_patterns.md
    mega_menu_patterns.md
    collection_page_patterns.md
    pdp_patterns.md
    gift_guide_patterns.md
    room_builder_patterns.md
    cart_drawer_patterns.md

  /04_ai_growth_studio
    one_sku_asset_matrix.md
    voc_to_product_concept.md
    workflow_approval_timeline.md
    weekly_growth_assistant.md

  /05_motion_references
    gsap_scroll_storytelling.md
    rive_interactive_product_demo.md
    lottie_micro_interactions.md
    motion_react_page_transitions.md

  /06_design_system
    DESIGN.md
    AGENTS.md
    CONTENT.md
    component_inventory.md
    tokens.json
    tailwind.theme.notes.md

  /07_prompts
    kimi_redesign_prompt.md
    claude_frontend_prompt.md
    image_generation_prompts.md
    video_storyboard_prompts.md

  /08_screenshots
    /homepage
    /navigation
    /pdp
    /gift
    /room
    /ai_studio
    /motion
```

---

# 11. Labebe 应该做的 6 张 Moodboard

## Moodboard 1：Warm Premium Montessori Home

内容：

```text
Lovevery age cards
Lalo lifestyle product scenes
Nestig nursery
Ferm Living Kids muted room
Oeuf furniture detail
Labebe learning tower / shelf / desk images
```

输出：

```text
首页视觉方向
Shop by Room 页面
Montessori at Home 页面
```

---

## Moodboard 2：Giftable Rockers

内容：

```text
Pottery Barn Kids gifting / registry
Lalo baby shower tone
Lovevery gift page
Labebe pink unicorn / highlander cattle / llama rocker
soft nursery scenes
gift card / gift wrap / birthday moment
```

输出：

```text
Giftable Rockers 集合页
Pink Unicorn PDP
First Birthday Gift Guide
Meta carousel
TikTok gift video
```

---

## Moodboard 3：Tiny Pretend Worlds

内容：

```text
Milton & Goose play kitchens
Tender Leaf play worlds
Labebe kitchen / coffee shop / bakery / washer / mud kitchen
children cooking / market / laundry pretend play scenes
```

输出：

```text
Pretend Play Worlds 页面
Play Kitchen PDP
短视频脚本
AI image-to-video prompt
```

---

## Moodboard 4：Playroom Reset

内容：

```text
Crate & Kids room makeover
Ferm Living storage
Oeuf play table
Labebe Montessori shelf / toy organizer / corner cabinet / activity wall
before-after room organization
```

输出：

```text
Playroom Reset 页面
Toy Rotation Guide
Storage PDP
Before/After 短视频
```

---

## Moodboard 5：AI Growth Studio

内容：

```text
Linear dashboard / workflow
Raycast command center
Stripe Atlas process explanation
Google Stitch DESIGN.md
Framer performance / SEO section
```

输出：

```text
AI Growth Demo
One SKU → Multi-channel Asset Matrix
VOC → Product Concept
Workflow approval timeline
```

---

## Moodboard 6：Motion & Microinteraction

内容：

```text
GSAP showcase
Rive interactive demos
Lottie micro animations
Motion layout animations
Apple-like drawer / sheet transitions
```

输出：

```text
Cart drawer
Product card hover
Quick Finder result transition
AI asset card generation
Workflow approval animation
```

---

# 12. 直接给 Kimi 的下一轮设计素材提示词

下面这段可以直接给 Kimi。

```text
你现在要为 Labebe 做一个世界级品牌电商 + AI Growth Studio Demo，不是继续美化旧页面。

请先阅读以下设计方向，并严格按 DESIGN.md 和 AGENTS.md 执行。

核心定位：
Warm Premium Montessori Home + Giftable Childhood Moments + AI Growth Studio

参考品牌：
1. Lovevery：学习 Shop by Age、developmental windows、Play Guide、专家感。
2. Lalo：学习成人审美的 baby/toddler DTC 语气，children products for adults in the room。
3. Milton & Goose：学习 Heirloom Play、Play Kitchens、real wood、高端 pretend play。
4. Little Partners：学习 Learning Tower 的安全、独立、亲子参与叙事。
5. Crate & Kids：学习 Room Design、Playroom Makeover、Shop by Room。
6. Pottery Barn Kids：学习 Baby Registry、Gift Guide、Design Boards、Shop Rooms。
7. Tender Leaf Toys：学习木玩世界观、轻度童话感、可持续木玩叙事。
8. Nestig / Ferm Living / Oeuf：学习高端儿童房、成长型家具、muted colors。

非同类世界级网站参考：
1. Linear：用于 AI Growth Studio 的系统感、workflow、dark panels。
2. Raycast：用于 command center、quick actions、SKU 操作入口。
3. Stripe Atlas：用于复杂流程 step-by-step 解释。
4. Framer：用于 performance / SEO / responsive / editability 的工程可信度。
5. Google Stitch / DESIGN.md：用于 agent-readable design system。

必须输出：
- 新首页
- Shop by Age
- Shop by Room
- Giftable Rockers
- Montessori at Home
- Pretend Play Worlds
- Playroom Reset
- 3 个 PDP
- Cart Drawer
- AI Growth Demo
- One SKU → Multi-channel Asset Matrix
- VOC → Product Concept
- Workflow Approval Timeline

禁止：
- 不许写 Stockholm、EST.2012、handcrafted artisans 等未经证实品牌故事。
- 不许使用 Building Blocks、Musical Play 这种不匹配 Labebe 的泛用分类。
- 不许乱改 Pink Unicorn 价格。
- 不许伪造评论、奖项、认证、媒体报道。
- 不许用与业务无关的 WebGL 科技球。
- 不许让页面只有好看没有购买路径。
- 不许让 AI Growth Demo 只是聊天框。

视觉要求：
Consumer Site:
warm cream background, oak wood tones, soft blush, sage, editorial photography, large product cards, calm Montessori home.

AI Growth Studio:
dark calm interface, system cards, workflow timeline, approval badges, asset matrix, channel chips, audit trail.

动效要求：
只允许服务业务：
1. Product card hover
2. Cart drawer
3. Quick Finder recommendation transition
4. One SKU expands into channel asset cards
5. Workflow approval timeline

页面结构：
首页必须包含：
Hero、Quick Finder、Four Worlds、Best Sellers、Watch It in Action、Montessori at Home、Giftable Rockers、Trust & Safety、AI Growth Studio Teaser、Reviews、Newsletter、Footer。

请先生成：
1. sitemap
2. component inventory
3. visual tokens
4. homepage wireframe
5. AI Growth Studio wireframe
6. implementation plan

然后再写代码。
```

---

# 13. 设计素材收集优先级

## P0：今天就应该收集

```text
Lovevery 首页、Play Kits、Shop by Age
Lalo 首页、Values、评论模块
Milton & Goose 首页、Play Kitchen、Shop by Category、Values
Little Partners Learning Tower 页面
Crate & Kids Kids Design Desk
Pottery Barn Kids Registry / Shop Rooms / Design Boards
Google DESIGN.md spec
Linear 首页和 workflow 风格
Raycast 首页 command center 风格
Awwwards / Land-book 里 10 个 kids / furniture / ecommerce 页面
```

## P1：第二轮收集

```text
Nestig nursery / kids room
Oeuf furniture PDP
Ferm Living Kids collection
Tender Leaf Toys pretend play worlds
Maisonette gift / curated edits
GSAP Showcase 里的 5 个 scroll storytelling
Rive website demos
Mobbin checkout / collection / onboarding flows
```

## P2：第三轮收集

```text
Apple HIG 具体组件原则
Shopify Polaris cart / badge / filter 组件
Material 3 Expressive color / motion / containment 原则
Google Fonts / Typewolf 字体搭配
Coolors / Adobe Color 色板实验
Figma Community kids ecommerce kits
```

---

# 14. 最终素材使用方式

不要让 Kimi “看完参考后自由发挥”。要让它按下面方式输出。

```text
每个参考必须拆成 5 个字段：

1. reference_name
2. what_to_borrow
3. what_not_to_copy
4. labebe_mapping
5. target_component
```

示例：

```yaml
reference_name: Lovevery
what_to_borrow:
  - age-based discovery
  - play guide structure
  - developmental window logic
what_not_to_copy:
  - subscription model
  - expert claims unless verified
labebe_mapping:
  - Shop by Age
  - PDP How to Use
  - Montessori at Home guide
target_component:
  - QuickFinder
  - PDPBenefitBlocks
  - AgeLandingPage
```

这样 Kimi 才不会变成“拼贴大师”，而是变成“设计系统执行者”。

---

# 15. 这次 Demo 的审美红线

要做世界级，最重要的是知道哪些东西不能做。

```text
不要低幼卡通。
不要整站彩虹。
不要 fake Scandinavian。
不要 fake handcrafted。
不要 fake award。
不要 fake review。
不要 fake safety certification。
不要让 AI 图把产品结构改错。
不要用 contact sheet 当视频封面。
不要做无意义科技动效。
不要让 AI Growth Demo 看起来像客服聊天框。
不要让页面只像作品集，不像能卖货。
```

真正的方向是：

```text
前台：
像 Lovevery + Lalo + Milton & Goose + Crate & Kids 的结合体。

后台演示：
像 Linear + Raycast + Stripe Atlas + Google Stitch 的结合体。

整体：
Labebe 自己的产品、真实数据、真实购买路径、真实 AI 增长链路。
```

---

# 16. 最后收口：给 Labebe 的“世界级 Demo 参考公式”

```text
Labebe Consumer Site
= Lovevery 的年龄导购
+ Lalo 的成人审美
+ Milton & Goose 的高端木玩质感
+ Little Partners 的蒙氏功能叙事
+ Crate & Kids 的儿童房空间服务
+ Pottery Barn Kids 的礼赠 / Registry 逻辑
+ Labebe 自己的真实产品数据

Labebe AI Growth Studio
= Linear 的系统界面
+ Raycast 的 command center
+ Stripe Atlas 的流程解释
+ Google DESIGN.md 的 agent-ready 设计规则
+ Labebe 单 SKU 多渠道素材裂变链路
```

这份素材库的核心目的不是“找漂亮页面”，而是让下一版 Demo 在 15 分钟内同时证明三件事：

1. Labebe 可以升级成一个儿童成长空间品牌；
2. Labebe 的网站可以从产品网格升级成场景化购买路径；
3. AI 可以把一个真实 SKU 变成多渠道素材、PDP 内容、广告脚本、视频分镜和增长复盘系统。

[1]: https://lovevery.com/?srsltid=AfmBOopVxSaOTNC64bCsXW-iTrC5vcvnDl7cfDLldGsVt5v1CpNIvuYt&utm_source=chatgpt.com "Lovevery | Stage-Based Play for Your Child's Developing Brain"
[2]: https://www.meetlalo.com/?srsltid=AfmBOorT4Nwz23O8ibbHSnJsnxVPHrfIxslKRr2TZJvSAg583Wjd3eNt "
      Lalo | Baby & Toddler Products You'll Be Proud to Own
"
[3]: https://miltonandgoose.com/?srsltid=AfmBOoqbG0yvHPgJejSVyMRzaEFw4vSPsI3dIyJei-B395xBsHzdunsJ "Heirloom Play Kitchens, Toys & Furniture for Kids | Milton & Goose"
[4]: https://littlepartners.com/?srsltid=AfmBOopnMvvDElhc87MVFzoPb-t0o62A_4Oyzui6AIhRJ5z6QluZnJkv "
        
            Top Montessori Furniture for Kids | Little Partners®

    "
[5]: https://www.crateandbarrel.com/kids/interior-design/ "Kids Interior Design | Crate & Kids"
[6]: https://www.potterybarnkids.com/ "Kids’ & Baby Furniture, Kids Bedding & Gifts | Baby Registry | Pottery Barn Kids "
[7]: https://www.maisonette.com/?srsltid=AfmBOopox9TxJx6sxVvCyUu0y8Ppo0GPVYcaOIanfy64ERfaqDVA2Onx&utm_source=chatgpt.com "Maisonette | Clothes, Toys & Decor for Kids & Babies"
[8]: https://www.tenderleaftoys.com/?srsltid=AfmBOorbwkgNi7UgDfjez6HEjP-Y9H3X0XSSSdNVBhpUFjn6UfHJ5dYq "
    Tender Leaf
    
    
    
  "
[9]: https://www.nestig.com/?srsltid=AfmBOopOGV98FqCuGnN__LesMWBbunN-QYjQR6u-2wyuthZ63evXFToa&utm_source=chatgpt.com "Nestig: Delightful Baby & Kids Furniture & Decor"
[10]: https://linear.app/?utm_source=chatgpt.com "Linear – The system for product development"
[11]: https://www.raycast.com/?utm_source=chatgpt.com "Raycast - Your shortcut to everything"
[12]: https://www.framer.com/?utm_source=chatgpt.com "Framer: Create a professional website, free. No code website ..."
[13]: https://stripe.com/atlas?utm_source=chatgpt.com "Stripe Atlas | Incorporate your startup in Delaware"
[14]: https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-design-md/ "Stitch app’s DESIGN.md format is now open-source for designers"
[15]: https://github.com/google-labs-code/design.md "GitHub - google-labs-code/design.md: A format specification for describing a visual identity to coding agents. DESIGN.md gives agents a persistent, structured understanding of a design system. · GitHub"
[16]: https://github.com/VoltAgent/awesome-design-md "GitHub - VoltAgent/awesome-design-md: A collection of DESIGN.md files inspired by popular brand design systems. Drop one into your project and let coding agents generate a matching UI. · GitHub"
[17]: https://agents.md/ "AGENTS.md"
[18]: https://code.claude.com/docs/en/best-practices "Best Practices for Claude Code - Claude Code Docs"
[19]: https://design.google/library/expressive-material-design-google-research "Expressive Design: Google's UX Research"
[20]: https://developer.apple.com/design/human-interface-guidelines "Human Interface Guidelines | Apple Developer Documentation"
[21]: https://www.awwwards.com/websites/ "Winning websites. Web Design Inspiration - Awwwards"
[22]: https://land-book.com/ "Landbook - website design inspiration gallery"
[23]: https://mobbin.com/ "Mobbin — UI & UX design inspiration for mobile & web apps"
[24]: https://gsap.com/showcase/?utm_source=chatgpt.com "GSAP Showcase"
