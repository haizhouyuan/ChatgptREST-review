#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';

const [asin, outJson, outScreenshot, waitMsArg = '7000'] = process.argv.slice(2);

if (!asin || !outJson || !outScreenshot) {
  console.error('Usage: node amazon_browser_product_probe.mjs <ASIN> <out.json> <out.png> [waitMs]');
  process.exit(2);
}

const waitMs = Number(waitMsArg);
const port = 9900 + Math.floor(Math.random() * 500);
const profileDir = `/tmp/labebe-amazon-probe-${process.pid}-${Date.now()}`;
const url = `https://www.amazon.com/dp/${asin}`;

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
  const textOf = (sel) => {
    const el = document.querySelector(sel);
    return el ? (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim() : '';
  };
  const attrOf = (sel, attr) => {
    const el = document.querySelector(sel);
    return el ? (el.getAttribute(attr) || '') : '';
  };
  const bodyText = (document.body.innerText || '').replace(/\\r/g, '');
  const match = (pattern) => {
    const m = bodyText.match(pattern);
    return m ? m[1].trim() : '';
  };
  const imgs = Array.from(document.querySelectorAll('img'))
    .map((img) => ({
      id: img.id || '',
      alt: img.alt || '',
      src: img.currentSrc || img.src || img.getAttribute('data-src') || '',
      width: img.naturalWidth || img.width || 0,
      height: img.naturalHeight || img.height || 0,
    }))
    .filter((img) => img.src && !/sprite|transparent|grey-pixel|logo|nav-/i.test(img.src))
    .filter((img, idx, arr) => arr.findIndex((x) => x.src === img.src) === idx)
    .slice(0, 40);
  const bullets = Array.from(document.querySelectorAll('#feature-bullets li, #feature-bullets span.a-list-item'))
    .map((el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim())
    .filter(Boolean)
    .slice(0, 12);
  return {
    captured_at: new Date().toISOString(),
    url: location.href,
    title: textOf('#productTitle') || document.title,
    document_title: document.title,
    byline: textOf('#bylineInfo'),
    brand_store_text: textOf('#bylineInfo') || match(/Visit the ([^\\n]+ Store)/),
    price: textOf('#corePriceDisplay_desktop_feature_div .a-price .a-offscreen') || textOf('.a-price .a-offscreen') || match(/(\\$\\d+\\.\\d\\d)/),
    rating_text: attrOf('#acrPopover', 'title') || match(/(\\d\\.\\d out of 5 stars)/),
    review_count_text: textOf('#acrCustomerReviewText') || match(/out of 5 stars\\s+\\(?\\s*([\\d,]+)\\)?/),
    bought_past_month: textOf('#social-proofing-faceout-title-tk_bought') || match(/([\\d,]+\\+ bought in past month)/),
    ships_from: match(/Ships from\\n([^\\n]+)/),
    sold_by: match(/Sold by\\n([^\\n]+)/),
    availability: textOf('#availability'),
    breadcrumbs: Array.from(document.querySelectorAll('#wayfinding-breadcrumbs_feature_div a'))
      .map((el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim())
      .filter(Boolean),
    bullets,
    image_count: imgs.length,
    images: imgs,
    page_state: {
      body_text_len: bodyText.length,
      captcha_like: /captcha|enter the characters|robot check|sorry, we just need to make sure/i.test(bodyText),
      blank_like: bodyText.length < 200,
      horizontal_overflow: document.documentElement.scrollWidth > innerWidth + 2 || document.body.scrollWidth > innerWidth + 2,
    },
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
    outJson,
    outScreenshot,
    title: data.title,
    price: data.price,
    rating: data.rating_text,
    reviews: data.review_count_text,
    sold_by: data.sold_by,
    image_count: data.image_count,
    page_state: data.page_state,
  }, null, 2));
  client.close();
} finally {
  chrome.kill('SIGTERM');
}
