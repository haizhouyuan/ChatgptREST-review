#!/usr/bin/env node
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const outputs = join(root, "outputs");
const evidence = join(outputs, "evidence");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function pandocToHtml(markdownPath) {
  const result = spawnSync("pandoc", ["--from=gfm", "--to=html", markdownPath], {
    encoding: "utf8",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(result.stderr || `pandoc failed with status ${result.status}`);
  }
  return result.stdout;
}

function loadScorecard(lane) {
  const scorecard = JSON.parse(readFileSync(join(evidence, "scorecard.json"), "utf8"));
  return scorecard.lanes[lane];
}

function pageShell({ title, subtitle, eyebrow, bodyHtml, kind, primaryHref, primaryLabel }) {
  const score = kind === "result" ? loadScorecard("claudeKimi") : null;
  const paperclipIssueId = "5521d6b7-b772-45b7-b247-904a20ad9e3a";
  const runId = "8cb4fcd5-944b-4976-868e-fdc28c74c23d";
  const sha = "8422aec2b2a0299700038481bf1dedbcd2f5e6291fb08bf13eb6ea000516b404";

  const resultMetrics = score
    ? `<div class="metrics" aria-label="Result metrics">
        <div><strong>${score.score}</strong><span>deterministic score</span></div>
        <div><strong>${score.selfScore}</strong><span>corrected self-score</span></div>
        <div><strong>${score.evidenceHits}</strong><span>evidence hits</span></div>
        <div><strong>${score.missingSections.length}</strong><span>missing sections</span></div>
      </div>`
    : "";

  const outcomeBand = kind === "result"
    ? `<section class="outcome">
        <div>
          <p class="tag">Result First</p>
          <h2>这就是要先展示的结果</h2>
          <p>Claude Code Kimi lane 已经产出完整 boss demo pack。结果页先给观众看结论、评分、运行事实和可点击证据；完整报告排版在下方，不再裸开 Markdown。</p>
        </div>
        <div class="facts">
          <p><span>Paperclip issue</span><strong>RUN-3 · done</strong></p>
          <p><span>Successful run</span><strong>${runId}</strong></p>
          <p><span>Model route</span><strong>claudekimi → kimi-for-coding</strong></p>
          <p><span>Package SHA256</span><code>${sha}</code></p>
        </div>
      </section>`
    : `<section class="outcome">
        <div>
          <p class="tag">Comparison</p>
          <h2>对比结论先行</h2>
          <p>这个页面把同任务输出对比渲染成 HTML，避免在展示时打开 raw Markdown。</p>
        </div>
      </section>`;

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #17201b;
      --muted: #5d6a61;
      --paper: #fbfbf7;
      --panel: #ffffff;
      --line: #d9e0d8;
      --green: #245c42;
      --green-soft: #e7f1e8;
      --blue: #2f5f8f;
      --blue-soft: #e8f0f7;
      --clay: #b65b3d;
      --amber: #e2b648;
    }

    * { box-sizing: border-box; }

    html {
      scroll-behavior: smooth;
      overflow-x: hidden;
    }

    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--paper);
      letter-spacing: 0;
      overflow-x: hidden;
    }

    a { color: var(--blue); }

    .topbar {
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 56px;
      padding: 10px clamp(16px, 4vw, 42px);
      border-bottom: 1px solid var(--line);
      background: rgba(251, 251, 247, 0.94);
      backdrop-filter: blur(10px);
      min-width: 0;
      max-width: 100vw;
    }

    .topbar strong {
      color: var(--green);
      font-size: 13px;
      text-transform: uppercase;
    }

    .topbar nav {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
      min-width: 0;
    }

    .topbar a,
    .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 36px;
      padding: 8px 11px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--green);
      text-decoration: none;
      font-size: 13px;
      font-weight: 800;
      white-space: nowrap;
    }

    .button.primary {
      border-color: var(--green);
      background: var(--green);
      color: #fff;
    }

    .hero {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(340px, 0.62fr);
      min-height: 64dvh;
      border-bottom: 1px solid var(--line);
      background: #f4f6ee;
      min-width: 0;
      max-width: 100vw;
    }

    .hero-copy {
      display: grid;
      align-content: center;
      gap: 22px;
      padding: clamp(28px, 5vw, 72px);
      min-width: 0;
    }

    .eyebrow,
    .tag {
      margin: 0;
      color: var(--green);
      font-size: 12px;
      font-weight: 900;
      text-transform: uppercase;
    }

    h1 {
      margin: 0;
      max-width: 980px;
      font-size: clamp(38px, 6vw, 76px);
      line-height: 1.02;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }

    .subtitle {
      margin: 0;
      max-width: 820px;
      color: var(--muted);
      font-size: clamp(17px, 2vw, 22px);
      line-height: 1.52;
      overflow-wrap: anywhere;
      word-break: break-word;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .hero-card {
      display: grid;
      align-content: end;
      gap: 16px;
      padding: clamp(22px, 4vw, 44px);
      border-left: 1px solid var(--line);
      background:
        linear-gradient(rgba(255,255,255,0.76), rgba(255,255,255,0.9)),
        url("showpiece_assets/ai-studio-hero.jpg") center / cover;
      min-width: 0;
    }

    .hero-card-inner {
      padding: 18px;
      border: 1px solid rgba(255,255,255,0.76);
      border-radius: 8px;
      background: rgba(255,255,255,0.9);
      box-shadow: 0 16px 45px rgba(29, 43, 34, 0.12);
    }

    .hero-card-inner h2 {
      margin-top: 0;
      font-size: 24px;
    }

    .hero-card-inner p {
      color: var(--muted);
      line-height: 1.5;
    }

    .metrics {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    .metrics div {
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }

    .metrics strong {
      display: block;
      color: var(--green);
      font-size: 34px;
      line-height: 1;
    }

    .metrics span {
      display: block;
      margin-top: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 760;
    }

    main {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 30px 0 64px;
    }

    .outcome {
      display: grid;
      grid-template-columns: minmax(0, 0.95fr) minmax(320px, 0.75fr);
      gap: 18px;
      align-items: stretch;
      margin-bottom: 24px;
      padding-bottom: 28px;
      border-bottom: 1px solid var(--line);
    }

    .outcome > div {
      min-width: 0;
      padding: 20px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }

    .outcome h2 {
      margin: 8px 0 10px;
      font-size: clamp(26px, 3vw, 40px);
      line-height: 1.08;
    }

    .outcome p {
      margin: 0;
      color: var(--muted);
      line-height: 1.58;
    }

    .facts {
      display: grid;
      gap: 8px;
    }

    .facts p {
      display: grid;
      gap: 4px;
      margin: 0;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--line);
    }

    .facts p:last-child { border-bottom: 0; }
    .facts span { color: var(--muted); font-size: 12px; font-weight: 780; }
    .facts strong { font-size: 15px; overflow-wrap: anywhere; }

    article.report {
      padding: clamp(18px, 4vw, 36px);
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }

    .report h1,
    .report h2,
    .report h3,
    .report h4 {
      letter-spacing: 0;
      scroll-margin-top: 80px;
    }

    .report h1 {
      font-size: clamp(30px, 4vw, 48px);
      line-height: 1.08;
    }

    .report h2 {
      margin-top: 42px;
      padding-top: 20px;
      border-top: 1px solid var(--line);
      font-size: clamp(24px, 3vw, 34px);
      line-height: 1.12;
    }

    .report h3 {
      margin-top: 28px;
      font-size: 21px;
    }

    .report p,
    .report li {
      color: #2e3932;
      font-size: 16px;
      line-height: 1.68;
    }

    .report blockquote {
      margin: 22px 0;
      padding: 16px 18px;
      border-left: 4px solid var(--green);
      border-radius: 8px;
      background: var(--green-soft);
    }

    .report blockquote p { margin: 0; }

    .report table {
      display: block;
      width: 100%;
      overflow-x: auto;
      border-collapse: collapse;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }

    .report th,
    .report td {
      padding: 11px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 14px;
      line-height: 1.48;
    }

    .report th {
      color: var(--green);
      background: #f4f7f1;
      font-weight: 860;
    }

    .report pre {
      overflow-x: auto;
      padding: 16px;
      border-radius: 8px;
      background: #17201b;
      color: #eef5ef;
      font-size: 13px;
      line-height: 1.5;
    }

    code {
      padding: 2px 5px;
      border-radius: 6px;
      background: #eef2ee;
      color: #24342a;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.92em;
      overflow-wrap: anywhere;
    }

    pre code {
      padding: 0;
      background: transparent;
      color: inherit;
      overflow-wrap: normal;
    }

    @media (max-width: 940px) {
      .hero,
      .outcome {
        grid-template-columns: 1fr;
      }

      .hero-card {
        min-height: 360px;
        border-left: 0;
        border-top: 1px solid var(--line);
      }
    }

    @media (max-width: 620px) {
      .topbar {
        align-items: flex-start;
        flex-direction: column;
        padding: 10px 12px;
        width: 100vw;
        max-width: 100vw;
      }

      .topbar nav {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        justify-content: stretch;
        width: 100%;
        max-width: calc(100vw - 24px);
      }

      .topbar a {
        white-space: normal;
        min-width: 0;
        padding: 8px 6px;
        text-align: center;
      }

      .hero-copy {
        padding: 24px;
        width: 100vw;
        max-width: 100vw;
      }

      .subtitle,
      .hero-card-inner p,
      .outcome p {
        max-width: calc(100vw - 48px);
        word-break: break-all;
      }

      .hero-card {
        width: 100vw;
        max-width: 100vw;
      }

      h1 {
        font-size: clamp(30px, 8.6vw, 36px);
        line-height: 1.08;
      }

      .actions {
        display: grid;
      }

      .button {
        white-space: normal;
        text-align: center;
      }

      .metrics {
        grid-template-columns: 1fr;
      }

      main {
        width: min(100% - 24px, 1180px);
      }

      article.report {
        padding: 16px;
      }

      .report p,
      .report li {
        font-size: 15px;
      }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <strong>${escapeHtml(eyebrow)}</strong>
    <nav>
      <a href="claude_kimi_showcase.html">展示总览</a>
      <a href="${escapeHtml(primaryHref)}">${escapeHtml(primaryLabel)}</a>
      <a data-paperclip-issue href="http://127.0.0.1:3100/issues/${paperclipIssueId}">Paperclip RUN-3</a>
    </nav>
  </header>

  <section class="hero">
    <div class="hero-copy">
      <p class="eyebrow">${escapeHtml(eyebrow)}</p>
      <h1>${escapeHtml(title)}</h1>
      <p class="subtitle">${escapeHtml(subtitle)}</p>
      <div class="actions">
        <a class="button primary" href="#result">看结果正文</a>
        <a class="button" href="evidence/scorecard.json">评分证据</a>
        <a class="button" href="evidence/claudeKimi_run.json">运行证据</a>
      </div>
    </div>
    <aside class="hero-card">
      <div class="hero-card-inner">
        <h2>验收摘要</h2>
        <p>结果页已由 Markdown 渲染为 HTML，保留表格、代码块、引用和 evidence 链接阅读体验。</p>
        ${resultMetrics}
      </div>
    </aside>
  </section>

  <main>
    ${outcomeBand}
    <article id="result" class="report">
      ${bodyHtml}
    </article>
  </main>

  <script>
    const issueId = "${paperclipIssueId}";
    const host = window.location.hostname && window.location.hostname !== "" ? window.location.hostname : "127.0.0.1";
    const paperclipUrl = host.endsWith(".ts.net")
      ? "https://" + host + ":9447/issues/" + issueId
      : "http://" + host + ":3100/issues/" + issueId;
    document.querySelectorAll("[data-paperclip-issue]").forEach((node) => {
      node.setAttribute("href", paperclipUrl);
      if (node.tagName === "A") node.textContent = "Paperclip RUN-3";
    });
  </script>
</body>
</html>
`;
}

function renderPage({ input, output, title, subtitle, eyebrow, kind, primaryHref, primaryLabel }) {
  const bodyHtml = pandocToHtml(join(outputs, input));
  const html = pageShell({ title, subtitle, eyebrow, bodyHtml, kind, primaryHref, primaryLabel });
  writeFileSync(join(outputs, output), html, "utf8");
  console.log(`rendered ${output}`);
}

renderPage({
  input: "claude_kimi_code_demo.md",
  output: "claude_kimi_code_demo_rendered.html",
  title: "渲染结果页",
  subtitle: "最终 demo pack 已渲染。先看结论、评分和运行事实，再看完整正文。",
  eyebrow: "Paperclip Runtime Duel / Result",
  kind: "result",
  primaryHref: "claude_kimi_code_demo.md",
  primaryLabel: "Raw Markdown",
});

renderPage({
  input: "claude_kimi_comparison.md",
  output: "claude_kimi_comparison_rendered.html",
  title: "同任务效果对比",
  subtitle: "对比 Claude Code Kimi 与之前同目标输出的结果差异，采用渲染后的展示格式。",
  eyebrow: "Paperclip Runtime Duel / Comparison",
  kind: "comparison",
  primaryHref: "claude_kimi_comparison.md",
  primaryLabel: "Raw Markdown",
});
