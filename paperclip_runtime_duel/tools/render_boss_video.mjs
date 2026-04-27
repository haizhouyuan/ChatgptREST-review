#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(join(__dirname, ".."));
const outputs = join(root, "outputs");
const videoDir = join(outputs, "video");
const htmlDir = join(videoDir, "slides-html");
const slideDir = join(videoDir, "slides");
const segmentDir = join(videoDir, "segments");

for (const dir of [videoDir, htmlDir, slideDir, segmentDir]) {
  mkdirSync(dir, { recursive: true });
}

const scorecard = JSON.parse(readFileSync(join(outputs, "evidence", "scorecard.json"), "utf8"));
const secretScan = JSON.parse(readFileSync(join(outputs, "evidence", "secret_scan.json"), "utf8"));
const claudeKimi = scorecard.lanes.claudeKimi;
const packageSha = "8422aec2b2a0299700038481bf1dedbcd2f5e6291fb08bf13eb6ea000516b404";
const issueId = "5521d6b7-b772-45b7-b247-904a20ad9e3a";
const runId = "8cb4fcd5-944b-4976-868e-fdc28c74c23d";

function fileUrl(path) {
  return pathToFileURL(path).href;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

const assets = {
  hero: fileUrl(join(outputs, "showpiece_assets", "ai-studio-hero.jpg")),
  result: fileUrl(join(outputs, "qa", "claude-kimi-rendered-result-desktop.png")),
  showcase: fileUrl(join(outputs, "qa", "claude-kimi-showcase-after-rendered-link-desktop.png")),
  learningTower: fileUrl(join(outputs, "showpiece_assets", "foldable-learning-tower.jpg")),
  kitchen: fileUrl(join(outputs, "showpiece_assets", "play-kitchen.jpg")),
  bakery: fileUrl(join(outputs, "showpiece_assets", "bakery-playset.jpg")),
  playroom: fileUrl(join(outputs, "showpiece_assets", "playroom.jpg")),
};

for (const [name, url] of Object.entries(assets)) {
  const path = fileURLToPath(url);
  if (!existsSync(path)) throw new Error(`Missing asset ${name}: ${path}`);
}

const slides = [
  {
    kicker: "Labebe AI Design Studio",
    title: "先看结果，不看过程",
    subtitle: "Paperclip + Claude Code Kimi 已经产出一个可审计、可展示、可复盘的老板版 demo pack。",
    image: assets.hero,
    theme: "hero",
    metrics: [
      ["RUN-3", "done"],
      ["Score", `${claudeKimi.score}/100`],
      ["Secret scan", `${secretScan.findingCount} findings`],
    ],
    note: "本视频只展示结果和可信证据，过程细节留在 Paperclip issue 与 evidence 包里。",
  },
  {
    kicker: "Result First",
    title: "最终结果页已经渲染",
    subtitle: "不再让老板看到 raw Markdown。第一屏直接给结论、评分、运行事实和证据入口。",
    screenshot: assets.result,
    bullets: [
      "完整 boss demo pack 已转成 HTML 结果页",
      "确定性评分 100，修正 self-score 97",
      "手机 390px CDP 视口已做视觉确认",
    ],
  },
  {
    kicker: "Runtime Truth",
    title: "这是 Kimi 通过 Claude Code 兼容路径",
    subtitle: "不是官方 Claude Code 与 Kimi 的品牌对比，而是 claudekimi wrapper 的真实效果测试。",
    flow: [
      "Paperclip issue RUN-3",
      "/home/yuanhaizhou/.local/bin/claudekimi",
      "raw stream-json: kimi-for-coding",
      "claude_kimi_code_demo_rendered.html",
    ],
    warning: "aggregate usageJson 仍显示 Claude Code 默认计费元数据，所以视频和报告都明确披露 metadata conflict。",
  },
  {
    kicker: "Control Plane",
    title: "Paperclip 不是聊天框，是 AI 团队控制台",
    subtitle: "展示价值在于组织、分工、审计、证据和可停止的执行闭环。",
    screenshot: assets.showcase,
    cards: [
      ["Agent", "Claude Code Kimi Content Lead"],
      ["Issue", "RUN-3 / done"],
      ["Run", runId],
      ["Evidence", "scorecard + run log + secret scan"],
    ],
  },
  {
    kicker: "Evidence",
    title: "老板能看懂的可信度",
    subtitle: "结果不是一句模型输出，而是有评分、有证据、有安全边界的交付包。",
    metrics: [
      ["Deterministic score", claudeKimi.score],
      ["Corrected self-score", claudeKimi.selfScore],
      ["Evidence hits", claudeKimi.evidenceHits],
      ["Secret findings", secretScan.findingCount],
      ["Missing sections", claudeKimi.missingSections.length],
      ["Package SHA", `${packageSha.slice(0, 12)}...`],
    ],
    bullets: [
      "所有关键 claim 标记 Fact / Inference / Hypothesis",
      "MCP policy、ledger、secret scan 已纳入 evidence",
      "RUN-3 已 operator verified closeout",
    ],
  },
  {
    kicker: "Product Output",
    title: "不是只会写报告，也能服务产品展示",
    subtitle: "Labebe 的产品方向用真实视觉素材落地：学习塔、玩具厨房、烘焙套装、儿童房场景。",
    gallery: [
      [assets.learningTower, "Foldable Learning Tower"],
      [assets.kitchen, "Play Kitchen"],
      [assets.bakery, "Bakery Playset"],
      [assets.playroom, "Playroom Scene"],
    ],
  },
  {
    kicker: "Comparison",
    title: "同目标输出的判断",
    subtitle: "你关心的是 Kimi 走 Claude Code 兼容路径后的效果。结论：更适合做完整 board-pack。",
    compare: [
      ["Claude Code Kimi", "证据更密、结构更完整、控制面合成更强。适合高要求 demo 生成。"],
      ["Native Kimi", "产品审美更干净，表达更轻。适合作为人工审美参考。"],
      ["Practical use", "主线用 claudekimi 跑高标准 demo，保留 native Kimi 做 taste check。"],
    ],
  },
  {
    kicker: "Decision",
    title: "下一步应该做结果墙",
    subtitle: "当前这个视频证明一条高质量闭环。下一步要把 10-12 个 demo 做成结果优先的 Boss Gallery。",
    bullets: [
      "每个 demo 第一屏展示最终成果，不展示执行过程",
      "每个卡片绑定 Paperclip issue、evidence、验收状态",
      "打不开、渲染差、手机不合格的 demo 不进入老板版",
    ],
    footer: "入口：yogas2.tail594315.ts.net:8778/claude_kimi_showcase.html",
  },
];

function metricHtml(metrics = []) {
  return `<div class="metrics">${metrics.map(([label, value]) => `
    <div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>
  `).join("")}</div>`;
}

function bulletsHtml(bullets = []) {
  return `<ul class="bullets">${bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function slideHtml(slide, index) {
  const number = String(index + 1).padStart(2, "0");
  const body =
    slide.theme === "hero" ? `
      <div class="hero-layout">
        <div class="copy">
          <p class="kicker">${escapeHtml(slide.kicker)}</p>
          <h1>${escapeHtml(slide.title)}</h1>
          <p class="subtitle">${escapeHtml(slide.subtitle)}</p>
          ${metricHtml(slide.metrics)}
          <p class="note">${escapeHtml(slide.note)}</p>
        </div>
        <div class="image-hero"><img src="${slide.image}" alt=""></div>
      </div>`
    : slide.screenshot ? `
      <div class="split">
        <div class="copy">
          <p class="kicker">${escapeHtml(slide.kicker)}</p>
          <h1>${escapeHtml(slide.title)}</h1>
          <p class="subtitle">${escapeHtml(slide.subtitle)}</p>
          ${slide.bullets ? bulletsHtml(slide.bullets) : ""}
          ${slide.cards ? `<div class="cards">${slide.cards.map(([a, b]) => `<div><span>${escapeHtml(a)}</span><strong>${escapeHtml(b)}</strong></div>`).join("")}</div>` : ""}
        </div>
        <div class="screen"><img src="${slide.screenshot}" alt=""></div>
      </div>`
    : slide.flow ? `
      <div class="copy wide">
        <p class="kicker">${escapeHtml(slide.kicker)}</p>
        <h1>${escapeHtml(slide.title)}</h1>
        <p class="subtitle">${escapeHtml(slide.subtitle)}</p>
        <div class="flow">${slide.flow.map((item) => `<div>${escapeHtml(item)}</div>`).join("<span>→</span>")}</div>
        <p class="warning">${escapeHtml(slide.warning)}</p>
      </div>`
    : slide.gallery ? `
      <div class="copy top">
        <p class="kicker">${escapeHtml(slide.kicker)}</p>
        <h1>${escapeHtml(slide.title)}</h1>
        <p class="subtitle">${escapeHtml(slide.subtitle)}</p>
      </div>
      <div class="gallery">${slide.gallery.map(([src, label]) => `<figure><img src="${src}" alt=""><figcaption>${escapeHtml(label)}</figcaption></figure>`).join("")}</div>`
    : slide.compare ? `
      <div class="copy wide">
        <p class="kicker">${escapeHtml(slide.kicker)}</p>
        <h1>${escapeHtml(slide.title)}</h1>
        <p class="subtitle">${escapeHtml(slide.subtitle)}</p>
        <div class="compare">${slide.compare.map(([label, text]) => `<div><span>${escapeHtml(label)}</span><p>${escapeHtml(text)}</p></div>`).join("")}</div>
      </div>`
    : `
      <div class="copy wide">
        <p class="kicker">${escapeHtml(slide.kicker)}</p>
        <h1>${escapeHtml(slide.title)}</h1>
        <p class="subtitle">${escapeHtml(slide.subtitle)}</p>
        ${metricHtml(slide.metrics)}
        ${slide.bullets ? bulletsHtml(slide.bullets) : ""}
        ${slide.footer ? `<p class="footer-call">${escapeHtml(slide.footer)}</p>` : ""}
      </div>`;

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    :root {
      --ink: #17201b;
      --muted: #5c6b62;
      --paper: #fbfbf7;
      --panel: rgba(255,255,255,0.92);
      --line: #d9e0d8;
      --green: #245c42;
      --blue: #2f5f8f;
      --amber: #e4b84b;
      --clay: #b65b3d;
    }
    * { box-sizing: border-box; }
    body {
      width: 1920px;
      height: 1080px;
      margin: 0;
      overflow: hidden;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--paper);
      letter-spacing: 0;
    }
    .slide {
      position: relative;
      width: 1920px;
      height: 1080px;
      padding: 72px;
      background:
        linear-gradient(120deg, rgba(251,251,247,0.96), rgba(251,251,247,0.86)),
        radial-gradient(circle at 88% 8%, rgba(47,95,143,0.18), transparent 34%),
        radial-gradient(circle at 6% 92%, rgba(36,92,66,0.14), transparent 32%);
    }
    .brand {
      position: absolute;
      left: 72px;
      top: 42px;
      color: var(--green);
      font-size: 18px;
      font-weight: 900;
      text-transform: uppercase;
    }
    .num {
      position: absolute;
      right: 72px;
      top: 42px;
      color: var(--muted);
      font-size: 18px;
      font-weight: 800;
    }
    .hero-layout,
    .split {
      display: grid;
      grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
      gap: 54px;
      align-items: center;
      height: 100%;
      padding-top: 28px;
    }
    .copy {
      display: grid;
      gap: 26px;
      align-content: center;
      min-width: 0;
    }
    .copy.wide {
      width: min(1550px, 100%);
      height: 100%;
      margin: 0 auto;
      align-content: center;
    }
    .copy.top {
      gap: 18px;
      margin-top: 42px;
      margin-bottom: 36px;
    }
    .kicker {
      margin: 0;
      color: var(--green);
      font-size: 22px;
      font-weight: 950;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      max-width: 100%;
      font-size: 92px;
      line-height: 1.02;
      letter-spacing: 0;
    }
    .subtitle {
      margin: 0;
      max-width: 1080px;
      color: var(--muted);
      font-size: 34px;
      line-height: 1.38;
    }
    .note,
    .warning,
    .footer-call {
      margin: 8px 0 0;
      padding: 22px 26px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--muted);
      font-size: 26px;
      line-height: 1.38;
    }
    .warning {
      border-left: 8px solid var(--clay);
    }
    .image-hero,
    .screen {
      height: 820px;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 24px 80px rgba(23,32,27,0.16);
    }
    .image-hero img,
    .screen img {
      width: 100%;
      height: 100%;
      display: block;
      object-fit: cover;
    }
    .screen img { object-position: top center; }
    .metrics {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 18px;
    }
    .metric,
    .cards div,
    .compare div {
      padding: 24px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }
    .metric span,
    .cards span,
    .compare span {
      display: block;
      color: var(--muted);
      font-size: 20px;
      font-weight: 850;
      text-transform: uppercase;
    }
    .metric strong {
      display: block;
      margin-top: 10px;
      color: var(--green);
      font-size: 48px;
      line-height: 1;
    }
    .bullets {
      display: grid;
      gap: 18px;
      margin: 6px 0 0;
      padding: 0;
      list-style: none;
    }
    .bullets li {
      padding: 20px 24px;
      border-left: 8px solid var(--green);
      border-radius: 8px;
      background: var(--panel);
      color: #27362e;
      font-size: 28px;
      line-height: 1.32;
    }
    .cards {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }
    .cards strong {
      display: block;
      margin-top: 10px;
      color: var(--ink);
      font-size: 28px;
      line-height: 1.18;
      overflow-wrap: anywhere;
    }
    .flow {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      align-items: center;
      gap: 14px;
      margin-top: 22px;
    }
    .flow div {
      min-height: 170px;
      display: grid;
      place-items: center;
      padding: 24px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      font-size: 28px;
      font-weight: 850;
      line-height: 1.2;
      text-align: center;
      overflow-wrap: anywhere;
    }
    .flow span {
      display: none;
    }
    .gallery {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 22px;
    }
    figure {
      margin: 0;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 18px 52px rgba(23,32,27,0.12);
    }
    figure img {
      width: 100%;
      height: 590px;
      display: block;
      object-fit: cover;
    }
    figcaption {
      padding: 20px 22px;
      color: var(--green);
      font-size: 24px;
      font-weight: 900;
    }
    .compare {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 20px;
      margin-top: 14px;
    }
    .compare p {
      margin: 14px 0 0;
      color: var(--ink);
      font-size: 28px;
      line-height: 1.34;
    }
  </style>
</head>
<body>
  <section class="slide">
    <div class="brand">Paperclip Runtime Duel / Boss Video</div>
    <div class="num">${number} / ${String(slides.length).padStart(2, "0")}</div>
    ${body}
  </section>
</body>
</html>`;
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: "inherit",
    ...options,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} failed with status ${result.status}`);
}

const htmlFiles = [];
const slideFiles = [];

slides.forEach((slide, index) => {
  const base = `slide-${String(index + 1).padStart(2, "0")}`;
  const htmlPath = join(htmlDir, `${base}.html`);
  const pngPath = join(slideDir, `${base}.png`);
  writeFileSync(htmlPath, slideHtml(slide, index), "utf8");
  htmlFiles.push(htmlPath);
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
    "-t", "6.5",
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

const concatPath = join(videoDir, "segments.txt");
writeFileSync(
  concatPath,
  segmentFiles.map((file) => `file '${file.replaceAll("'", "'\\''")}'`).join("\n") + "\n",
  "utf8",
);

const videoPath = join(videoDir, "labebe_paperclip_boss_demo.mp4");
run("ffmpeg", [
  "-y",
  "-f", "concat",
  "-safe", "0",
  "-i", concatPath,
  "-c:v", "libx264",
  "-preset", "veryfast",
  "-crf", "18",
  "-c:a", "aac",
  "-b:a", "128k",
  "-pix_fmt", "yuv420p",
  "-movflags", "+faststart",
  videoPath,
]);

const posterPath = join(videoDir, "labebe_paperclip_boss_demo_poster.jpg");
run("ffmpeg", [
  "-y",
  "-i", videoPath,
  "-frames:v", "1",
  "-update", "1",
  "-q:v", "2",
  posterPath,
]);

const contactSheetPath = join(videoDir, "labebe_paperclip_boss_demo_contact_sheet.jpg");
run("ffmpeg", [
  "-y",
  "-i", videoPath,
  "-vf", "fps=1/6.5,scale=480:270,tile=4x2:padding=8:margin=8:color=white",
  "-frames:v", "1",
  "-update", "1",
  "-q:v", "3",
  contactSheetPath,
]);

const storyboard = `# Labebe Paperclip Boss Demo Video

Output: \`outputs/video/labebe_paperclip_boss_demo.mp4\`

Duration target: 52 seconds, 8 result-first slides.

## Story Arc

1. 先看结果，不看过程。
2. 最终结果页已经渲染。
3. Kimi 通过 Claude Code 兼容路径。
4. Paperclip 是 AI 团队控制台。
5. 可信度来自 scorecard、run evidence、secret scan。
6. 产品输出方向有真实视觉素材。
7. claudekimi 与 native Kimi 的同目标效果判断。
8. 下一步做 10-12 个结果优先 Boss Gallery demo。

## Verification

- Video: \`${videoPath}\`
- Poster: \`${posterPath}\`
- Contact sheet: \`${contactSheetPath}\`
- Slide PNGs and segments are generated intermediates during render and are not required for playback.
`;

writeFileSync(join(videoDir, "boss_video_storyboard.md"), storyboard, "utf8");

console.log(`video=${videoPath}`);
console.log(`poster=${posterPath}`);
console.log(`contactSheet=${contactSheetPath}`);
