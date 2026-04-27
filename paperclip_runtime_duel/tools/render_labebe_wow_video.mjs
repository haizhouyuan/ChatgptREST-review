#!/usr/bin/env node
import { copyFileSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(join(__dirname, ".."));
const repoRoot = resolve(join(root, ".."));
const outputDir = join(root, "outputs", "labebe_wow");
const assetDir = join(outputDir, "assets");
const slideHtmlDir = join(outputDir, "slides-html");
const slidePngDir = join(outputDir, "slides");
const segmentDir = join(outputDir, "segments");

for (const dir of [outputDir, assetDir, slideHtmlDir, slidePngDir, segmentDir]) {
  mkdirSync(dir, { recursive: true });
}

const sourceAssets = {
  learningTower: join(repoRoot, "labebe-ai-design-studio/workspace/outputs/boss-demo-wow/assets/foldable-learning-tower-montessori-kitchen-tower-log-color.jpg"),
  playKitchen: join(repoRoot, "labebe-ai-design-studio/workspace/outputs/boss-demo-wow/assets/cream-wooden-play-kitchen-set-with-storage.jpg"),
  bakery: join(repoRoot, "labebe-ai-design-studio/workspace/outputs/boss-demo-wow/assets/wooden-bakery-toy-food-playset.jpg"),
  playroom: join(repoRoot, "labebe-ai-design-studio/workspace/outputs/boss-demo-wow/assets/room-playroom.jpg"),
  heroHome: join(repoRoot, "pro_requests/20260425_labebe_v2_pro_review/attachments/website_pack/current_site/public/hero-home.jpg"),
  rocker: join(repoRoot, "pro_requests/20260425_labebe_v2_pro_review/attachments/website_pack/current_site/public/products/pink-unicorn-plush-rocker.jpg"),
  shelf: join(repoRoot, "pro_requests/20260425_labebe_v2_pro_review/attachments/website_pack/current_site/public/products/natural-wood-montessori-shelf-with-storage-boxes.jpg"),
};

const assets = {};
const slideAssets = {};
for (const [key, source] of Object.entries(sourceAssets)) {
  if (!existsSync(source)) throw new Error(`Missing source asset ${key}: ${source}`);
  const dest = join(assetDir, `${key}.jpg`);
  copyFileSync(source, dest);
  assets[key] = `./assets/${key}.jpg`;
  slideAssets[key] = pathToFileURL(dest).href;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

const conceptSignals = [
  ["RS-001", "小厨房收纳占地", "转成 fold-flat stow-away requirement"],
  ["RS-002", "台阶与角落清洁摩擦", "转成 wipe-clean step geometry"],
  ["RS-003", "折叠形态需要锁定信号", "转成 visible lock-state cue"],
  ["DT-006", "样本不能证明真实需求", "阻止 proven demand claim"],
];

const demoLanes = [
  ["A", "Design Opportunity Radar", "从 review / competitor / trend 样本找 P0 产品机会"],
  ["B", "VOC to New Concept", "把评论痛点翻译为 SpaceSmart 学习塔需求"],
  ["C", "Sketch to Concept", "把草图方向变成可审核 concept route"],
  ["D", "Custom Toy Kitchen Builder", "让家长定制玩具厨房模块与房间适配"],
  ["E", "Design Director + DFM", "美学、工程、安全、成本在上线前先卡住"],
  ["F", "Concept-to-Market Matrix", "同一概念裂变 PDP、A+、短视频、广告与邮件资产"],
];

const channels = [
  ["PDP", "首屏概念模块", "compact kitchen routine + fold-flat story", "Draft"],
  ["Amazon A+", "Problem / Solution / Gate 三段", "不写 certification / ranking", "Review"],
  ["TikTok 15s", "小厨房 before / after 分镜", "lock mechanism 进入工程审核", "Draft"],
  ["Meta", "4 帧 carousel", "痛点、概念、门槛、下一步", "Draft"],
  ["Google Image", "温暖木色厨房场景 brief", "无 available-now 文案", "Draft"],
  ["Email", "老板审批邮件", "只请求 prototype exploration", "Internal"],
];

const blockedClaims = [
  "Certified safe",
  "Proven market demand",
  "Lower cost than competitors",
  "Available now",
  "Production-ready CAD",
];

function pageHtml() {
  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Labebe AI Application Wow Demo</title>
    <style>
      :root {
        color-scheme: light;
        --ink: #151c18;
        --muted: #5e6d64;
        --paper: #faf8f2;
        --soft: #f1ece2;
        --panel: #fffdf8;
        --line: #ded5c6;
        --green: #245d45;
        --blue: #2b5d82;
        --clay: #b95c3e;
        --amber: #ddae33;
        --red: #a63e36;
      }

      * { box-sizing: border-box; }
      html { scroll-behavior: smooth; }
      body {
        margin: 0;
        background: var(--paper);
        color: var(--ink);
        font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        letter-spacing: 0;
        overflow-x: hidden;
      }
      img { max-width: 100%; display: block; }
      a { color: inherit; text-decoration: none; }
      .topbar {
        position: sticky;
        top: 0;
        z-index: 20;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 24px;
        padding: 14px clamp(18px, 4vw, 56px);
        border-bottom: 1px solid rgba(222, 213, 198, 0.9);
        background: rgba(250, 248, 242, 0.94);
        backdrop-filter: blur(14px);
      }
      .brand strong { display: block; font-size: 19px; line-height: 1.1; }
      .brand span { color: var(--clay); font-size: 12px; font-weight: 850; text-transform: uppercase; }
      .topbar nav { max-width: 100%; display: flex; flex-wrap: wrap; gap: 8px; }
      .topbar a, .ghost-link {
        min-height: 38px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 9px 13px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: rgba(255, 253, 248, 0.88);
        font-size: 14px;
        font-weight: 800;
      }
      .hero {
        min-height: calc(100dvh - 68px);
        display: grid;
        grid-template-columns: minmax(0, 1.02fr) minmax(360px, 0.98fr);
        gap: clamp(24px, 4vw, 62px);
        align-items: center;
        padding: clamp(28px, 5vw, 72px);
        background:
          linear-gradient(120deg, rgba(250,248,242,0.98), rgba(250,248,242,0.72)),
          url("${assets.heroHome}") center / cover;
        border-bottom: 1px solid var(--line);
      }
      .kicker {
        margin: 0 0 12px;
        color: var(--green);
        font-size: 13px;
        font-weight: 950;
        text-transform: uppercase;
      }
      h1, h2, h3, p { overflow-wrap: anywhere; }
      h1 {
        margin: 0;
        max-width: 980px;
        font-size: clamp(46px, 7.2vw, 106px);
        line-height: 0.98;
        word-break: break-word;
      }
      .hero-copy h1 span { display: block; }
      .hero-copy p span { display: block; }
      .hero-copy { min-width: 0; }
      .hero-copy > p:not(.kicker) {
        max-width: 760px;
        color: #405048;
        font-size: clamp(18px, 2vw, 26px);
        line-height: 1.42;
      }
      .hero-actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 28px; }
      .primary {
        min-height: 46px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 12px 18px;
        border-radius: 8px;
        background: var(--green);
        color: #fffdf8;
        font-size: 15px;
        font-weight: 900;
      }
      .machine-card {
        align-self: stretch;
        display: grid;
        grid-template-rows: 1fr auto;
        overflow: hidden;
        border: 1px solid rgba(21,28,24,0.18);
        border-radius: 8px;
        background: rgba(255,253,248,0.92);
        box-shadow: 0 26px 90px rgba(21,28,24,0.22);
      }
      .machine-card img { width: 100%; height: 100%; min-height: 420px; object-fit: cover; }
      .machine-caption { padding: 24px; border-top: 1px solid var(--line); }
      .machine-caption h2 { margin: 0 0 10px; font-size: clamp(28px, 3vw, 46px); line-height: 1.02; }
      .machine-caption p { margin: 0; color: var(--muted); font-size: 17px; line-height: 1.44; }
      .stats {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
        margin-top: 28px;
        max-width: 780px;
      }
      .stats div {
        min-height: 92px;
        padding: 18px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: rgba(255,253,248,0.9);
      }
      .stats strong { display: block; color: var(--green); font-size: 31px; line-height: 1; }
      .stats span { display: block; margin-top: 8px; color: var(--muted); font-size: 13px; font-weight: 700; }
      .section { padding: clamp(44px, 6vw, 82px) clamp(18px, 5vw, 72px); border-bottom: 1px solid var(--line); }
      .section-head {
        display: grid;
        grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
        gap: 28px;
        align-items: end;
        margin-bottom: 28px;
      }
      .section h2 { margin: 0; font-size: clamp(34px, 5vw, 68px); line-height: 1.02; }
      .section-head p:not(.kicker) { color: var(--muted); font-size: 18px; line-height: 1.52; }
      .signals {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
      }
      .signal, .lane, .asset-card, .claim, .decision-card {
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--panel);
      }
      .signal { min-height: 180px; padding: 18px; }
      .signal strong { color: var(--blue); font-size: 15px; }
      .signal h3 { margin: 12px 0 10px; font-size: 22px; line-height: 1.13; }
      .signal p { margin: 0; color: var(--muted); font-size: 15px; line-height: 1.45; }
      .machine {
        display: grid;
        grid-template-columns: minmax(220px, 0.85fr) repeat(5, minmax(140px, 1fr)) minmax(240px, 0.9fr);
        gap: 10px;
        align-items: stretch;
      }
      .station {
        position: relative;
        min-height: 270px;
        display: grid;
        align-content: space-between;
        padding: 18px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: #fffdf8;
      }
      .station.input { background: #14201a; color: #fffdf8; }
      .station.output { background: #e7f0ea; }
      .station b { display: block; font-size: 13px; text-transform: uppercase; color: var(--clay); }
      .station.input b { color: #f0c26c; }
      .station h3 { margin: 12px 0; font-size: 24px; line-height: 1.08; }
      .station p { margin: 0; color: var(--muted); font-size: 15px; line-height: 1.42; }
      .station.input p { color: rgba(255,253,248,0.82); }
      .status {
        justify-self: start;
        margin-top: 20px;
        padding: 7px 10px;
        border-radius: 999px;
        background: rgba(36,93,69,0.12);
        color: var(--green);
        font-size: 12px;
        font-weight: 900;
      }
      .asset-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
      }
      .asset-card { min-height: 240px; padding: 20px; display: grid; align-content: space-between; }
      .asset-card span { color: var(--clay); font-size: 12px; font-weight: 900; text-transform: uppercase; }
      .asset-card h3 { margin: 12px 0; font-size: 28px; line-height: 1.08; }
      .asset-card p { margin: 0; color: var(--muted); font-size: 16px; line-height: 1.42; }
      .asset-card em {
        justify-self: start;
        margin-top: 18px;
        padding: 8px 11px;
        border-radius: 999px;
        background: #e7f0ea;
        color: var(--green);
        font-size: 12px;
        font-style: normal;
        font-weight: 900;
      }
      .claims-layout {
        display: grid;
        grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
        gap: 18px;
      }
      .claim { padding: 24px; }
      .claim.blocked { border-color: rgba(166,62,54,0.5); background: #fff8f5; }
      .claim h3 { margin: 0 0 18px; font-size: 34px; }
      .claim-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 14px;
        padding: 13px 0;
        border-top: 1px solid var(--line);
        color: var(--muted);
        font-size: 16px;
      }
      .claim-row b { color: var(--ink); }
      .claim-row span {
        flex: 0 0 auto;
        padding: 7px 10px;
        border-radius: 999px;
        background: #e7f0ea;
        color: var(--green);
        font-size: 11px;
        font-weight: 900;
        text-transform: uppercase;
      }
      .claim.blocked .claim-row span { background: #f4dfda; color: var(--red); }
      .visual-strip {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 14px;
      }
      .visual-strip figure {
        margin: 0;
        overflow: hidden;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: #fff;
      }
      .visual-strip img { width: 100%; height: 300px; object-fit: cover; }
      .visual-strip figcaption { padding: 14px; color: var(--green); font-weight: 900; }
      .lanes {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
      }
      .lane { min-height: 190px; padding: 20px; }
      .lane strong { color: var(--blue); font-size: 15px; }
      .lane h3 { margin: 12px 0; font-size: 25px; line-height: 1.1; }
      .lane p { margin: 0; color: var(--muted); font-size: 15px; line-height: 1.44; }
      .decision {
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(320px, 0.72fr);
        gap: 20px;
      }
      .decision-card { padding: 24px; background: #14201a; color: #fffdf8; }
      .decision-card h3 { margin: 0 0 14px; font-size: 38px; line-height: 1.05; }
      .decision-card p, .decision-card li { color: rgba(255,253,248,0.8); font-size: 17px; line-height: 1.5; }
      .decision-card ul { margin: 18px 0 0; padding-left: 20px; }
      .evidence {
        display: grid;
        gap: 10px;
        align-content: start;
      }
      .evidence a {
        display: block;
        padding: 16px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--panel);
        color: var(--blue);
        font-weight: 900;
      }
      @media (max-width: 900px) {
        .hero, .section-head, .claims-layout, .decision { grid-template-columns: 1fr; }
        .hero { min-height: auto; }
        .hero { padding: 28px 18px; }
        h1 { font-size: clamp(32px, 9vw, 36px); line-height: 1.08; word-break: break-all; }
        .hero-copy > p:not(.kicker) { max-width: 100%; font-size: 16px; word-break: break-all; }
        .topbar nav { display: grid; grid-template-columns: 1fr; width: 100%; }
        .topbar a { width: 100%; }
        .machine-card img { min-height: 300px; }
        .stats, .signals, .asset-grid, .visual-strip, .lanes { grid-template-columns: 1fr; }
        .machine { grid-template-columns: 1fr; }
        .section { padding-block: 42px; }
        .topbar { align-items: flex-start; flex-direction: column; }
      }
    </style>
  </head>
  <body>
    <header class="topbar">
      <div class="brand">
        <span>Result-first boss demo</span>
        <strong>Labebe AI Application Wow</strong>
      </div>
      <nav>
        <a href="#concept">Concept</a>
        <a href="#machine">Machine</a>
        <a href="#matrix">Assets</a>
        <a href="#gate">Claim Gate</a>
        <a href="#lanes">Pro Demos</a>
      </nav>
    </header>

    <main>
      <section class="hero">
        <div class="hero-copy">
          <p class="kicker">不是 AI 技术展示，是 Labebe 拿到的业务结果</p>
          <h1><span>新品概念</span><span>裂变成</span><span>可审核增长资产包。</span></h1>
          <p><span>本地样本信号转成产品方向。</span><span>渠道素材进入老板决策包。</span><span>安全、认证、需求、成本、上市声明全部先过门禁。</span></p>
          <div class="stats">
            <div><strong>1</strong><span>review-ready concept</span></div>
            <div><strong>6</strong><span>channel asset drafts</span></div>
            <div><strong>0</strong><span>unsupported launch claims</span></div>
          </div>
          <div class="hero-actions">
            <a class="primary" href="#concept">先看最终概念</a>
            <a class="ghost-link" href="./labebe_ai_application_wow.mp4">打开老板视频</a>
          </div>
        </div>
        <article class="machine-card">
          <img src="${assets.learningTower}" alt="SpaceSmart Foldable Learning Tower concept" />
          <div class="machine-caption">
            <h2>SpaceSmart Foldable Learning Tower</h2>
            <p>Compact storage, visible lock-state cue, cleanable geometry. Status: local draft/demo, prototype exploration only.</p>
          </div>
        </article>
      </section>

      <section id="concept" class="section">
        <div class="section-head">
          <div>
            <p class="kicker">Demo B / VOC to New Concept</p>
            <h2>评论痛点变成新品概念，而不是一页流程图。</h2>
          </div>
          <p>Pro 要的 hero moment 是老板能复述的产品故事：小厨房占地、清洁摩擦、折叠锁定这三类信号，转成 SpaceSmart 的可审核产品方向。</p>
        </div>
        <div class="signals">
          ${conceptSignals.map(([id, title, detail]) => `
            <article class="signal">
              <strong>${escapeHtml(id)}</strong>
              <h3>${escapeHtml(title)}</h3>
              <p>${escapeHtml(detail)}</p>
            </article>
          `).join("")}
        </div>
      </section>

      <section id="machine" class="section">
        <div class="section-head">
          <div>
            <p class="kicker">AI Packaging Machine</p>
            <h2>一个 SKU 投入机器，右侧吐出增长资产。</h2>
          </div>
          <p>这就是 Pro 建议的表达方式：不要解释 AI，要让 AI 像生产线一样发生。Paperclip 留在后台做控制和证据，老板看到的是结果。</p>
        </div>
        <div class="machine">
          <article class="station input"><b>Input</b><h3>SpaceSmart SKU seed</h3><p>本地样本、产品图片、设计约束和 Data Truth 规则。</p><span class="status">truth core</span></article>
          <article class="station"><b>01</b><h3>Fact Intake</h3><p>标记 verified / demo_sample / forbidden claim。</p><span class="status">source labels</span></article>
          <article class="station"><b>02</b><h3>VOC Press</h3><p>把用户痛点压印成 requirement map。</p><span class="status">concept brief</span></article>
          <article class="station"><b>03</b><h3>Route Cutter</h3><p>四条设计路线，选择 Fold-Flat Pantry。</p><span class="status">route review</span></article>
          <article class="station"><b>04</b><h3>DFM Gate</h3><p>tipping、pinch、small parts、cost 进入人审。</p><span class="status">conditional go</span></article>
          <article class="station"><b>05</b><h3>Asset Press</h3><p>PDP、A+、TikTok、Meta、Google、Email 同步出稿。</p><span class="status">draft only</span></article>
          <article class="station output"><b>Output</b><h3>Boss decision pack</h3><p>批准 prototype exploration，或先要求更多证据。</p><span class="status">review-ready</span></article>
        </div>
      </section>

      <section id="matrix" class="section">
        <div class="section-head">
          <div>
            <p class="kicker">Demo F / Concept-to-Market Matrix</p>
            <h2>同一概念，不同渠道，一次生成。</h2>
          </div>
          <p>老板要看到的是 AI 给 Labebe 带来的产能：不是一段文案，而是一个受控的多渠道增长资产矩阵。</p>
        </div>
        <div class="asset-grid">
          ${channels.map(([name, title, detail, status]) => `
            <article class="asset-card">
              <span>${escapeHtml(name)}</span>
              <div>
                <h3>${escapeHtml(title)}</h3>
                <p>${escapeHtml(detail)}</p>
              </div>
              <em>${escapeHtml(status)}</em>
            </article>
          `).join("")}
        </div>
      </section>

      <section id="gate" class="section">
        <div class="section-head">
          <div>
            <p class="kicker">Claim Firewall Arena</p>
            <h2>最该给老板看的 wow：AI 会生成，也会停。</h2>
          </div>
          <p>儿童家居产品不能靠 AI 编漂亮话。这个 demo 的核心不是“写得快”，而是能把不能说的话挡在发布前。</p>
        </div>
        <div class="claims-layout">
          <article class="claim">
            <h3>Allowed draft claims</h3>
            <div class="claim-row"><b>Designed for compact kitchen routines.</b><span>RS-001</span></div>
            <div class="claim-row"><b>Explores a fold-flat helper-tower concept.</b><span>LAB-4</span></div>
            <div class="claim-row"><b>Visible lock-state detail is part of concept direction.</b><span>RS-003</span></div>
            <div class="claim-row"><b>Draft assets are local and not launched.</b><span>verified</span></div>
          </article>
          <article class="claim blocked">
            <h3>Blocked before boss approval</h3>
            ${blockedClaims.map((claim) => `<div class="claim-row"><b>${escapeHtml(claim)}</b><span>blocked</span></div>`).join("")}
          </article>
        </div>
      </section>

      <section class="section">
        <div class="section-head">
          <div>
            <p class="kicker">Visual result shelf</p>
            <h2>Labebe 的产品世界先站出来。</h2>
          </div>
          <p>Pro 的批评是对的：不能让“技术控制台”抢主角。展示必须先让人看到产品、房间、渠道资产和可执行决策。</p>
        </div>
        <div class="visual-strip">
          <figure><img src="${assets.playKitchen}" alt="Labebe play kitchen" /><figcaption>Modular Tiny Pretend Kitchen</figcaption></figure>
          <figure><img src="${assets.bakery}" alt="Labebe bakery playset" /><figcaption>Mini Bakery Kitchen Corner</figcaption></figure>
          <figure><img src="${assets.playroom}" alt="Labebe playroom" /><figcaption>Playroom Reset System</figcaption></figure>
        </div>
      </section>

      <section id="lanes" class="section">
        <div class="section-head">
          <div>
            <p class="kicker">Pro specified demo lanes</p>
            <h2>后续十几个 demo 必须按这 6 条主线做结果展示。</h2>
          </div>
          <p>这些不是技术步骤，而是 Labebe AI 应用后可以给老板看的业务能力。</p>
        </div>
        <div class="lanes">
          ${demoLanes.map(([id, title, detail]) => `
            <article class="lane">
              <strong>Demo ${escapeHtml(id)}</strong>
              <h3>${escapeHtml(title)}</h3>
              <p>${escapeHtml(detail)}</p>
            </article>
          `).join("")}
        </div>
      </section>

      <section class="section">
        <div class="decision">
          <article class="decision-card">
            <p class="kicker">Boss close</p>
            <h3>今天要批准的不是上线，而是下一轮原型与证据投入。</h3>
            <p>这才是安全的老板口径：AI 已经把机会、概念、渠道资产和风险门槛整理成可决策包，但任何安全、认证、成本、需求、上市 claim 都必须继续人审。</p>
            <ul>
              <li>Approve prototype exploration for SpaceSmart.</li>
              <li>Request more customer evidence before demand claims.</li>
              <li>Keep channel assets local until human review passes.</li>
            </ul>
          </article>
          <div class="evidence">
            <a href="../claude_kimi_showcase.html">旧技术展示入口</a>
            <a href="../video/boss_video.html">旧 Paperclip 视频入口</a>
            <a href="./labebe_ai_application_wow.mp4">新 Labebe wow 视频</a>
            <a href="../evidence/artifact_ledger.json">Evidence ledger</a>
          </div>
        </div>
      </section>
    </main>
  </body>
</html>`;
}

const slideData = [
  {
    kicker: "方向纠偏",
    title: "先给老板看 Labebe 得到了什么。",
    subtitle: "不是 11 个 Paperclip run，而是 1 个可审核新品概念、6 类渠道资产、0 条未证实上线声明。",
    image: slideAssets.learningTower,
    metrics: [["Concept", "SpaceSmart"], ["Assets", "PDP / A+ / TikTok / Meta / Google / Email"], ["Gate", "Blocked unsafe claims"]],
  },
  {
    kicker: "Demo A",
    title: "AI 先找产品机会。",
    subtitle: "Pro 指定的机会雷达：SpaceSmart Learning Tower、Modular Tiny Pretend Kitchen、Giftable Animal Rocker、Playroom Reset。",
    image: slideAssets.playroom,
    bullets: ["本地样本只做探索，不伪装成真实需求", "Data Truth Guard 先标记 source boundary", "老板看到 P0/P1 产品机会，不看后台日志"],
  },
  {
    kicker: "Demo B",
    title: "评论痛点变成 SpaceSmart 新品概念。",
    subtitle: "小厨房占地、清洁摩擦、折叠锁定，被转译为 fold-flat storage、cleanable geometry、visible lock-state cue。",
    image: slideAssets.learningTower,
    callouts: conceptSignals,
  },
  {
    kicker: "AI Packaging Machine",
    title: "一款 SKU 被加工成增长资产包。",
    subtitle: "Fact Intake → VOC Press → Route Cutter → DFM Gate → Asset Press → Claim Gate。老板看到机器在产出，不是人在解释 AI。",
    machine: true,
  },
  {
    kicker: "Demo F",
    title: "同一概念，六类渠道资产同时成型。",
    subtitle: "PDP、Amazon A+、TikTok、Meta、Google Image、Email 都是本地 draft/demo，并保留 source 与 review 状态。",
    assets: channels,
  },
  {
    kicker: "最强 wow 点",
    title: "AI 会写，但也知道哪些话不能说。",
    subtitle: "Certified safe、proven demand、lower cost、available now、production-ready CAD 全部 blocked，儿童产品风险没有被包装成营销话术。",
    blocked: blockedClaims,
  },
  {
    kicker: "Pro 的真正 demo 清单",
    title: "十几个 demo 要做成 Labebe 业务结果墙。",
    subtitle: "Design Radar、VOC-to-Concept、Sketch-to-Concept、Toy Kitchen Builder、Design/DFM Gate、Concept-to-Market Matrix。",
    lanes: demoLanes,
  },
  {
    kicker: "老板决策",
    title: "批准下一轮原型探索，而不是批准上市。",
    subtitle: "这就是可信的 AI 应用展示：速度、创意、渠道产能和风险门槛一起出现。",
    image: slideAssets.heroHome,
    bullets: ["Prototype exploration: conditional go", "External marketing: stop until review", "Demand / safety / certification claims: require evidence"],
  },
];

function metricHtml(metrics = []) {
  return `<div class="metrics">${metrics.map(([label, value]) => `
    <div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>
  `).join("")}</div>`;
}

function slideHtml(slide, index) {
  const body = slide.machine ? `
    <div class="slide-copy full">
      <p class="kicker">${escapeHtml(slide.kicker)}</p>
      <h1>${escapeHtml(slide.title)}</h1>
      <p class="subtitle">${escapeHtml(slide.subtitle)}</p>
      <div class="slide-machine">
        ${["SKU Seed", "Fact Intake", "VOC Press", "Route Cutter", "DFM Gate", "Asset Press", "Claim Gate"].map((item, step) => `
          <div class="${step === 0 ? "dark" : step === 6 ? "gate" : ""}">
            <b>${String(step).padStart(2, "0")}</b>
            <strong>${escapeHtml(item)}</strong>
          </div>
        `).join("")}
      </div>
    </div>`
  : slide.assets ? `
    <div class="slide-copy full">
      <p class="kicker">${escapeHtml(slide.kicker)}</p>
      <h1>${escapeHtml(slide.title)}</h1>
      <p class="subtitle">${escapeHtml(slide.subtitle)}</p>
      <div class="slide-assets">
        ${slide.assets.map(([name, title, detail, status]) => `
          <div>
            <span>${escapeHtml(name)} / ${escapeHtml(status)}</span>
            <strong>${escapeHtml(title)}</strong>
            <p>${escapeHtml(detail)}</p>
          </div>
        `).join("")}
      </div>
    </div>`
  : slide.blocked ? `
    <div class="slide-copy full">
      <p class="kicker">${escapeHtml(slide.kicker)}</p>
      <h1>${escapeHtml(slide.title)}</h1>
      <p class="subtitle">${escapeHtml(slide.subtitle)}</p>
      <div class="blocked-grid">
        ${slide.blocked.map((claim) => `<div><strong>${escapeHtml(claim)}</strong><span>BLOCKED</span></div>`).join("")}
      </div>
    </div>`
  : slide.lanes ? `
    <div class="slide-copy full">
      <p class="kicker">${escapeHtml(slide.kicker)}</p>
      <h1>${escapeHtml(slide.title)}</h1>
      <p class="subtitle">${escapeHtml(slide.subtitle)}</p>
      <div class="lane-grid">
        ${slide.lanes.map(([id, title, detail]) => `
          <div><span>Demo ${escapeHtml(id)}</span><strong>${escapeHtml(title)}</strong><p>${escapeHtml(detail)}</p></div>
        `).join("")}
      </div>
    </div>`
  : slide.callouts ? `
    <div class="slide-split">
      <div class="slide-copy">
        <p class="kicker">${escapeHtml(slide.kicker)}</p>
        <h1>${escapeHtml(slide.title)}</h1>
        <p class="subtitle">${escapeHtml(slide.subtitle)}</p>
        <div class="callouts">${slide.callouts.map(([id, title, detail]) => `<div><span>${escapeHtml(id)}</span><strong>${escapeHtml(title)}</strong><p>${escapeHtml(detail)}</p></div>`).join("")}</div>
      </div>
      <div class="slide-img"><img src="${slide.image}" alt=""></div>
    </div>`
  : `
    <div class="slide-split">
      <div class="slide-copy">
        <p class="kicker">${escapeHtml(slide.kicker)}</p>
        <h1>${escapeHtml(slide.title)}</h1>
        <p class="subtitle">${escapeHtml(slide.subtitle)}</p>
        ${slide.metrics ? metricHtml(slide.metrics) : ""}
        ${slide.bullets ? `<ul>${slide.bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
      </div>
      <div class="slide-img"><img src="${slide.image}" alt=""></div>
    </div>`;

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    :root {
      --ink: #151c18;
      --muted: #5e6d64;
      --paper: #faf8f2;
      --panel: #fffdf8;
      --line: #ded5c6;
      --green: #245d45;
      --blue: #2b5d82;
      --clay: #b95c3e;
      --red: #a63e36;
    }
    * { box-sizing: border-box; }
    body {
      width: 1920px;
      height: 1080px;
      margin: 0;
      overflow: hidden;
      background: var(--paper);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    .slide {
      position: relative;
      width: 1920px;
      height: 1080px;
      padding: 70px;
      background:
        linear-gradient(120deg, rgba(250,248,242,0.98), rgba(250,248,242,0.9)),
        radial-gradient(circle at 92% 8%, rgba(43,93,130,0.16), transparent 34%),
        radial-gradient(circle at 8% 92%, rgba(36,93,69,0.14), transparent 34%);
    }
    .brand, .num {
      position: absolute;
      top: 38px;
      font-size: 18px;
      font-weight: 950;
      text-transform: uppercase;
    }
    .brand { left: 70px; color: var(--green); }
    .num { right: 70px; color: var(--muted); }
    .slide-split {
      height: 100%;
      display: grid;
      grid-template-columns: minmax(0, 1.02fr) minmax(0, 0.98fr);
      gap: 54px;
      align-items: center;
      padding-top: 28px;
    }
    .slide-copy { display: grid; gap: 24px; align-content: center; min-width: 0; }
    .slide-copy.full { width: min(1640px, 100%); height: 100%; margin: 0 auto; }
    .kicker { margin: 0; color: var(--green); font-size: 23px; font-weight: 950; text-transform: uppercase; }
    h1 {
      margin: 0;
      max-width: 1580px;
      font-size: 88px;
      line-height: 1.02;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }
    .subtitle {
      margin: 0;
      max-width: 1320px;
      color: var(--muted);
      font-size: 32px;
      line-height: 1.38;
      overflow-wrap: anywhere;
    }
    .slide-img {
      height: 820px;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 24px 80px rgba(21,28,24,0.16);
    }
    .slide-img img { width: 100%; height: 100%; object-fit: cover; }
    .metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 16px; }
    .metrics div, .callouts div, .slide-assets div, .blocked-grid div, .lane-grid div {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }
    .metrics div { min-height: 150px; padding: 22px; }
    .metrics span, .callouts span, .slide-assets span, .lane-grid span {
      display: block;
      color: var(--clay);
      font-size: 17px;
      font-weight: 950;
      text-transform: uppercase;
    }
    .metrics strong {
      display: block;
      margin-top: 14px;
      color: var(--green);
      font-size: 32px;
      line-height: 1.13;
      overflow-wrap: anywhere;
    }
    ul { display: grid; gap: 16px; margin: 0; padding: 0; list-style: none; }
    li {
      padding: 19px 22px;
      border-left: 8px solid var(--green);
      border-radius: 8px;
      background: var(--panel);
      color: #27362e;
      font-size: 28px;
      line-height: 1.28;
    }
    .callouts { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 14px; }
    .callouts div { min-height: 160px; padding: 19px; }
    .callouts strong { display: block; margin-top: 10px; font-size: 25px; line-height: 1.1; }
    .callouts p { margin: 10px 0 0; color: var(--muted); font-size: 18px; line-height: 1.35; }
    .slide-machine { display: grid; grid-template-columns: repeat(7,minmax(0,1fr)); gap: 12px; margin-top: 24px; }
    .slide-machine div {
      min-height: 280px;
      display: grid;
      align-content: space-between;
      padding: 22px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }
    .slide-machine .dark { background: #14201a; color: #fffdf8; }
    .slide-machine .gate { border-color: rgba(166,62,54,0.5); background: #fff3ef; }
    .slide-machine b { color: var(--clay); font-size: 20px; }
    .slide-machine strong { font-size: 31px; line-height: 1.08; overflow-wrap: anywhere; }
    .slide-assets { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 14px; margin-top: 20px; }
    .slide-assets div { min-height: 210px; padding: 22px; }
    .slide-assets strong { display: block; margin-top: 12px; font-size: 29px; line-height: 1.06; }
    .slide-assets p { margin: 12px 0 0; color: var(--muted); font-size: 20px; line-height: 1.32; }
    .blocked-grid { display: grid; grid-template-columns: repeat(5,minmax(0,1fr)); gap: 14px; margin-top: 28px; }
    .blocked-grid div { min-height: 250px; display: grid; align-content: space-between; padding: 22px; border-color: rgba(166,62,54,0.45); background: #fff8f5; }
    .blocked-grid strong { font-size: 32px; line-height: 1.08; }
    .blocked-grid span {
      justify-self: start;
      padding: 9px 12px;
      border-radius: 999px;
      background: #f4dfda;
      color: var(--red);
      font-size: 14px;
      font-weight: 950;
    }
    .lane-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 14px; margin-top: 20px; }
    .lane-grid div { min-height: 190px; padding: 20px; }
    .lane-grid strong { display: block; margin-top: 11px; font-size: 28px; line-height: 1.06; }
    .lane-grid p { margin: 11px 0 0; color: var(--muted); font-size: 19px; line-height: 1.32; }
  </style>
</head>
<body>
  <section class="slide">
    <div class="brand">Labebe AI Application Wow</div>
    <div class="num">${String(index + 1).padStart(2, "0")} / ${String(slideData.length).padStart(2, "0")}</div>
    ${body}
  </section>
</body>
</html>`;
}

function playerHtml() {
  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Labebe AI Application Wow Video</title>
    <style>
      :root { color-scheme: light; --ink:#151c18; --muted:#5e6d64; --paper:#faf8f2; --panel:#fffdf8; --line:#ded5c6; --green:#245d45; }
      * { box-sizing: border-box; }
      body { margin: 0; background: var(--paper); color: var(--ink); font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; letter-spacing: 0; }
      main { min-height: 100dvh; display: grid; align-content: center; gap: 24px; padding: clamp(18px, 5vw, 64px); }
      header { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 20px; align-items: end; }
      h1 { margin: 0; max-width: 980px; font-size: clamp(38px, 6vw, 78px); line-height: 1.02; }
      p { margin: 12px 0 0; max-width: 850px; color: var(--muted); font-size: 18px; line-height: 1.5; }
      .links { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
      a { min-height: 40px; display: inline-flex; align-items: center; padding: 9px 13px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); color: inherit; text-decoration: none; font-weight: 850; }
      video, img { width: 100%; border: 1px solid var(--line); border-radius: 8px; background: #000; box-shadow: 0 24px 80px rgba(21,28,24,0.16); }
      .sheet { background: var(--panel); padding: 14px; border: 1px solid var(--line); border-radius: 8px; }
      .sheet h2 { margin: 0 0 12px; font-size: 24px; }
      @media (max-width: 760px) { header { grid-template-columns: 1fr; } .links { justify-content: flex-start; } }
    </style>
  </head>
  <body>
    <main>
      <header>
        <div>
          <h1>Labebe AI 应用结果展示视频</h1>
          <p>这版按 Pro 的方向重做：先展示 Labebe 新品概念、渠道资产矩阵和 Claim Gate 结果，再把 Paperclip 作为后台证据。</p>
        </div>
        <div class="links">
          <a href="./index.html">打开互动展示页</a>
          <a href="./labebe_ai_application_wow.mp4">直接打开 MP4</a>
        </div>
      </header>
      <video controls poster="./labebe_ai_application_wow_poster.jpg" src="./labebe_ai_application_wow.mp4"></video>
      <section class="sheet">
        <h2>Storyboard contact sheet</h2>
        <img src="./labebe_ai_application_wow_contact_sheet.jpg" alt="Video contact sheet" />
      </section>
    </main>
  </body>
</html>`;
}

function run(command, args) {
  const result = spawnSync(command, args, { stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} failed with status ${result.status}`);
}

writeFileSync(join(outputDir, "index.html"), pageHtml(), "utf8");

const slideFiles = [];
slideData.forEach((slide, index) => {
  const base = `slide-${String(index + 1).padStart(2, "0")}`;
  const htmlPath = join(slideHtmlDir, `${base}.html`);
  const pngPath = join(slidePngDir, `${base}.png`);
  writeFileSync(htmlPath, slideHtml(slide, index), "utf8");
  slideFiles.push(pngPath);
  run("google-chrome", [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--no-proxy-server",
    `--screenshot=${pngPath}`,
    "--window-size=1920,1080",
    pathToFileURL(htmlPath).href,
  ]);
});

const segmentFiles = [];
slideFiles.forEach((pngPath, index) => {
  const segmentPath = join(segmentDir, `segment-${String(index + 1).padStart(2, "0")}.mp4`);
  segmentFiles.push(segmentPath);
  run("ffmpeg", [
    "-y",
    "-loop", "1",
    "-i", pngPath,
    "-f", "lavfi",
    "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
    "-t", "6.2",
    "-r", "30",
    "-vf", "scale=1920:1080,setsar=1,format=yuv420p",
    "-c:v", "libx264",
    "-preset", "veryfast",
    "-crf", "18",
    "-c:a", "aac",
    "-b:a", "128k",
    "-shortest",
    segmentPath,
  ]);
});

const concatPath = join(outputDir, "segments.txt");
writeFileSync(concatPath, segmentFiles.map((file) => `file '${file.replaceAll("'", "'\\''")}'`).join("\n") + "\n", "utf8");

const videoPath = join(outputDir, "labebe_ai_application_wow.mp4");
run("ffmpeg", [
  "-y",
  "-f", "concat",
  "-safe", "0",
  "-i", concatPath,
  "-c", "copy",
  "-movflags", "+faststart",
  videoPath,
]);

const posterPath = join(outputDir, "labebe_ai_application_wow_poster.jpg");
run("ffmpeg", [
  "-y",
  "-i", videoPath,
  "-frames:v", "1",
  "-update", "1",
  "-q:v", "2",
  posterPath,
]);

const contactSheetPath = join(outputDir, "labebe_ai_application_wow_contact_sheet.jpg");
run("ffmpeg", [
  "-y",
  "-i", videoPath,
  "-vf", "fps=1/6.2,scale=480:270,tile=4x2:padding=8:margin=8:color=white",
  "-frames:v", "1",
  "-update", "1",
  "-q:v", "3",
  contactSheetPath,
]);

writeFileSync(join(outputDir, "boss_video.html"), playerHtml(), "utf8");

const storyboard = `# Labebe AI Application Wow Video

This replaces the previous technical Paperclip-first video.

## Pro-aligned direction

- Show Labebe business/product outcome first.
- Use SpaceSmart Foldable Learning Tower as the hero concept.
- Show One SKU to Multi-channel Growth Asset Matrix.
- Make Claim Gate the remembered wow moment.
- Keep Paperclip as the backstage evidence/control plane.

## Slide order

1. Boss sees what Labebe got.
2. Demo A: opportunity radar output.
3. Demo B: VOC to SpaceSmart concept.
4. AI Packaging Machine.
5. Demo F: six channel asset drafts.
6. Claim Gate blocks unsupported claims.
7. Pro's six demo lanes.
8. Boss decision: prototype exploration, not launch approval.

## Outputs

- Interactive page: \`outputs/labebe_wow/index.html\`
- Video player: \`outputs/labebe_wow/boss_video.html\`
- MP4: \`outputs/labebe_wow/labebe_ai_application_wow.mp4\`
- Contact sheet: \`outputs/labebe_wow/labebe_ai_application_wow_contact_sheet.jpg\`
`;

writeFileSync(join(outputDir, "storyboard.md"), storyboard, "utf8");

console.log(`page=${join(outputDir, "index.html")}`);
console.log(`player=${join(outputDir, "boss_video.html")}`);
console.log(`video=${videoPath}`);
console.log(`contactSheet=${contactSheetPath}`);
