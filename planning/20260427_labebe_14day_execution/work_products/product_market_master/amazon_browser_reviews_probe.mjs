#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';

const [asin, outJson, outScreenshot, waitMsArg = '9000'] = process.argv.slice(2);

if (!asin || !outJson || !outScreenshot) {
  console.error('Usage: node amazon_browser_reviews_probe.mjs <ASIN> <out.json> <out.png> [waitMs]');
  process.exit(2);
}

const waitMs = Number(waitMsArg);
const port = 10400 + Math.floor(Math.random() * 500);
const profileDir = `/tmp/labebe-amazon-reviews-${process.pid}-${Date.now()}`;
const url = `https://www.amazon.com/product-reviews/${asin}?sortBy=recent&reviewerType=all_reviews`;

const chrome = spawn('/usr/bin/google-chrome', [
  '--headless=new',
  '--no-sandbox',
  '--disable-gpu',
  '--disable-dev-shm-usage',
  `--user-data-dir=${profileDir}`,
  `--remote-debugging-port=${port}`,
  'about:blank',
], { stdio: 'ignore' });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function fetchJson(endpoint) {
  for (let i = 0; i < 80; i += 1) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}${endpoint}`);
      if (res.ok) return res.json();
    } catch {
      // Chrome is still starting.
    }
    await sleep(100);
  }
  throw new Error('Chrome remote debugging endpoint did not start');
}

function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  ws.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    if (data.id && pending.has(data.id)) {
      pending.get(data.id)(data);
      pending.delete(data.id);
    }
  });
  const ready = new Promise((resolve) => ws.addEventListener('open', resolve, { once: true }));
  return {
    ready,
    send(method, params = {}) {
      const msg = { id: ++id, method, params };
      return new Promise((resolve) => {
        const timer = setTimeout(() => {
          pending.delete(msg.id);
          resolve({ error: { message: `CDP timeout: ${method}` } });
        }, 15000);
        pending.set(msg.id, (data) => {
          clearTimeout(timer);
          resolve(data);
        });
        ws.send(JSON.stringify(msg));
      });
    },
    close() {
      ws.close();
    },
  };
}

const extractExpression = `(() => {
  const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim();
  const textOf = (root, sel) => {
    const el = root.querySelector(sel);
    return clean(el ? (el.innerText || el.textContent || '') : '');
  };
  const attrOf = (root, sel, attr) => {
    const el = root.querySelector(sel);
    return clean(el ? (el.getAttribute(attr) || '') : '');
  };
  const bodyText = document.body.innerText || '';
  const cards = Array.from(document.querySelectorAll('[data-hook="review"], .review, div[id^="customer_review-"]')).slice(0, 20);
  const reviews = cards.map((card, idx) => ({
    index: idx + 1,
    review_id: card.id || '',
    author: textOf(card, '.a-profile-name'),
    rating_text: attrOf(card, '[data-hook="review-star-rating"], [data-hook="cmps-review-star-rating"], .review-rating', 'aria-label')
      || textOf(card, '[data-hook="review-star-rating"], [data-hook="cmps-review-star-rating"], .review-rating'),
    title: textOf(card, '[data-hook="review-title"], .review-title'),
    date: textOf(card, '[data-hook="review-date"], .review-date'),
    verified: textOf(card, '[data-hook="avp-badge"], .a-size-mini.a-color-state'),
    body: textOf(card, '[data-hook="review-body"], .review-text'),
    helpful: textOf(card, '[data-hook="helpful-vote-statement"]'),
  })).filter((r) => r.title || r.body || r.rating_text);
  return {
    captured_at: new Date().toISOString(),
    url: location.href,
    document_title: document.title,
    heading: clean(document.querySelector('h1, h2')?.innerText || ''),
    body_text_len: bodyText.length,
    captcha_like: /captcha|enter the characters|robot check|sorry, we just need to make sure/i.test(bodyText),
    blank_like: bodyText.length < 200,
    review_count_extracted: reviews.length,
    reviews,
    visible_text_sample: clean(bodyText).slice(0, 2500),
  };
})()`;

try {
  const tabs = await fetchJson('/json/list');
  const tab = (Array.isArray(tabs) ? tabs : [tabs]).find((item) => item.type === 'page') || tabs[0];
  const client = connect(tab.webSocketDebuggerUrl);
  await client.ready;
  await client.send('Page.enable');
  await client.send('Runtime.enable');
  await client.send('Network.enable');
  await client.send('Network.setUserAgentOverride', {
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    acceptLanguage: 'en-US,en;q=0.9',
    platform: 'Linux x86_64',
  });
  await client.send('Emulation.setDeviceMetricsOverride', {
    width: 1366,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await client.send('Page.navigate', { url });
  await sleep(waitMs);
  const extraction = await client.send('Runtime.evaluate', {
    expression: extractExpression,
    returnByValue: true,
  });
  const data = extraction?.result?.result?.value || {
    captured_at: new Date().toISOString(),
    url,
    error: extraction?.error || extraction?.result?.exceptionDetails || 'empty extraction',
  };
  const shot = await client.send('Page.captureScreenshot', {
    format: 'png',
    fromSurface: true,
    captureBeyondViewport: false,
  });
  await mkdir(dirname(outJson), { recursive: true });
  await mkdir(dirname(outScreenshot), { recursive: true });
  await writeFile(outJson, JSON.stringify(data, null, 2), 'utf8');
  if (shot?.result?.data) {
    await writeFile(outScreenshot, Buffer.from(shot.result.data, 'base64'));
  }
  console.log(JSON.stringify({
    asin,
    review_count_extracted: data.review_count_extracted,
    captcha_like: data.captcha_like,
    blank_like: data.blank_like,
    heading: data.heading,
    outJson,
    outScreenshot,
  }, null, 2));
  client.close();
} finally {
  chrome.kill('SIGTERM');
}
