#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';

const [inputCsv, outJson, outCsv, shotDir, limitArg = '12', delayMsArg = '5000'] = process.argv.slice(2);

if (!inputCsv || !outJson || !outCsv || !shotDir) {
  console.error('Usage: node amazon_browser_search_candidates.mjs <product_master.csv> <out.json> <out.csv> <shot_dir> [limit] [delayMs]');
  process.exit(2);
}

const limit = Number(limitArg);
const delayMs = Number(delayMsArg);
const port = 10400 + Math.floor(Math.random() * 500);
const profileDir = `/tmp/labebe-amazon-search-${process.pid}-${Date.now()}`;

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

function parseCsvLine(line) {
  const values = [];
  let value = '';
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') {
        value += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = false;
      } else {
        value += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ',') {
      values.push(value);
      value = '';
    } else {
      value += ch;
    }
  }
  values.push(value);
  return values;
}

function parseCsv(text) {
  const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/).filter(Boolean);
  const headers = parseCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    return Object.fromEntries(headers.map((header, idx) => [header, values[idx] || '']));
  });
}

function csvEscape(value) {
  const s = String(value ?? '');
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

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
        }, 20000);
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
  const titleFromCard = (card) => {
    const h2Texts = Array.from(card.querySelectorAll('h2 span, h2 a span, [data-cy="title-recipe-title"] span'))
      .map((el) => clean(el.innerText || el.textContent || ''))
      .filter(Boolean)
      .filter((text) => !/^(sponsored|labebe)$/i.test(text));
    return h2Texts[0] || h2Texts.join(' ') || '';
  };
  const reviewCountFromCard = (card) => {
    const text = clean(card.innerText || card.textContent || '');
    const afterStars = text.match(/out of 5 stars\\s*\\(?([\\d,]+)\\)?/i);
    if (afterStars) return afterStars[1];
    const explicit = Array.from(card.querySelectorAll('a[href*="customerReviews"] span, a[href*="#customerReviews"] span, a[aria-label*="ratings"]'))
      .map((el) => clean(el.getAttribute('aria-label') || el.innerText || el.textContent || ''))
      .map((text) => {
        const m = text.match(/([\\d,]+)\\s+(?:ratings?|reviews?)/i) || text.match(/^([\\d,]+)$/);
        return m ? m[1] : '';
      })
      .find(Boolean);
    return explicit || '';
  };
  const bodyText = clean(document.body.innerText || '');
  const results = Array.from(document.querySelectorAll('[data-component-type="s-search-result"][data-asin]'))
    .map((card, rank) => {
      const asin = card.getAttribute('data-asin') || '';
      const linkEl = card.querySelector('h2 a, a[href*="/dp/"], a[href*="/gp/product/"]');
      const imgEl = card.querySelector('img.s-image');
      const priceEl = card.querySelector('.a-price .a-offscreen');
      const ratingEl = card.querySelector('[aria-label*="out of 5 stars"], .a-icon-alt');
      return {
        rank: rank + 1,
        asin,
        title: titleFromCard(card),
        url: linkEl ? new URL(linkEl.getAttribute('href') || '', location.origin).href.split('/ref=')[0] : '',
        image: imgEl ? (imgEl.currentSrc || imgEl.src || '') : '',
        price: clean(priceEl?.innerText || priceEl?.textContent || ''),
        rating_text: clean(ratingEl?.getAttribute('aria-label') || ratingEl?.innerText || ratingEl?.textContent || ''),
        review_count_text: reviewCountFromCard(card),
      };
    })
    .filter((row) => row.asin || row.title)
    .slice(0, 8);
  return {
    captured_at: new Date().toISOString(),
    url: location.href,
    document_title: document.title,
    results,
    page_state: {
      body_text_len: bodyText.length,
      captcha_like: /captcha|enter the characters|robot check|sorry, we just need to make sure/i.test(bodyText),
      blank_like: bodyText.length < 200,
      result_count: results.length,
      horizontal_overflow: document.documentElement.scrollWidth > innerWidth + 2 || document.body.scrollWidth > innerWidth + 2,
    },
  };
})()`;

function pickRows(rows, n) {
  const useful = rows.filter((row) => {
    const scope = row.catalog_scope || '';
    const slug = row.sku_id || row.canonical_slug || row.slug || '';
    return !slug.endsWith('-eu') && scope !== 'regional_variant';
  });
  const reviewRich = useful
    .filter((row) => Number(row.review_count_visible || 0) > 0)
    .sort((a, b) => Number(b.review_count_visible || 0) - Number(a.review_count_visible || 0));
  const pushWalkers = useful.filter((row) => /push-walker/i.test(row.sku_id || row.canonical_slug || row.title_clean || ''));
  const combined = [...reviewRich, ...pushWalkers, ...useful];
  const seen = new Set();
  return combined.filter((row) => {
    const id = row.sku_id || row.canonical_slug || row.slug || row.title_clean;
    if (!id || seen.has(id)) return false;
    seen.add(id);
    return true;
  }).slice(0, n);
}

try {
  const rows = pickRows(parseCsv(await readFile(inputCsv, 'utf8')), limit);
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

  await mkdir(dirname(outJson), { recursive: true });
  await mkdir(dirname(outCsv), { recursive: true });
  await mkdir(shotDir, { recursive: true });

  const all = [];
  for (const row of rows) {
    const sku = row.sku_id || row.canonical_slug || row.slug;
    const title = row.title_clean || row.title || sku;
    const query = `labebe ${title}`;
    const url = `https://www.amazon.com/s?k=${encodeURIComponent(query)}`;
    let data = null;
    for (let attempt = 1; attempt <= 2; attempt += 1) {
      await client.send('Page.navigate', { url });
      await sleep(delayMs + (attempt - 1) * 2500);
      const extraction = await client.send('Runtime.evaluate', {
        expression: extractExpression,
        returnByValue: true,
      });
      data = extraction?.result?.result?.value || {
        captured_at: new Date().toISOString(),
        url,
        error: extraction?.error || extraction?.result?.exceptionDetails || 'empty extraction',
        results: [],
        page_state: {},
      };
      data.attempt = attempt;
      if (!data.page_state?.blank_like && data.page_state?.body_text_len > 200) break;
    }
    data.query = query;
    data.sku_id = sku;
    data.dtc_title = title;
    data.dtc_price = row.price_current || '';
    data.dtc_review_count_visible = row.review_count_visible || '';
    const shot = await client.send('Page.captureScreenshot', {
      format: 'png',
      fromSurface: true,
      captureBeyondViewport: false,
    });
    const shotPath = join(shotDir, `${sku}.png`);
    if (shot?.result?.data) {
      await writeFile(shotPath, Buffer.from(shot.result.data, 'base64'));
      data.screenshot = shotPath;
    }
    all.push(data);
    console.log(JSON.stringify({
      sku,
      query,
      result_count: data.page_state?.result_count || 0,
      captcha_like: Boolean(data.page_state?.captcha_like),
      top: data.results?.[0] || null,
    }));
  }

  await writeFile(outJson, JSON.stringify({
    generated_at: new Date().toISOString(),
    inputCsv,
    limit,
    delayMs,
    searched_count: all.length,
    searches: all,
  }, null, 2), 'utf8');

  const flat = [];
  for (const search of all) {
    for (const result of search.results || []) {
      flat.push({
        sku_id: search.sku_id,
        dtc_title: search.dtc_title,
        dtc_price: search.dtc_price,
        dtc_review_count_visible: search.dtc_review_count_visible,
        query: search.query,
        amazon_rank: result.rank,
        asin: result.asin,
        amazon_title: result.title,
        amazon_price: result.price,
        amazon_rating_text: result.rating_text,
        amazon_review_count_text: result.review_count_text,
        amazon_url: result.url,
        amazon_image: result.image,
        screenshot: search.screenshot || '',
        page_captcha_like: search.page_state?.captcha_like || false,
        page_result_count: search.page_state?.result_count || 0,
      });
    }
  }
  const headers = [
    'sku_id',
    'dtc_title',
    'dtc_price',
    'dtc_review_count_visible',
    'query',
    'amazon_rank',
    'asin',
    'amazon_title',
    'amazon_price',
    'amazon_rating_text',
    'amazon_review_count_text',
    'amazon_url',
    'amazon_image',
    'screenshot',
    'page_captcha_like',
    'page_result_count',
  ];
  await writeFile(
    outCsv,
    `${headers.join(',')}\n${flat.map((row) => headers.map((header) => csvEscape(row[header])).join(',')).join('\n')}\n`,
    'utf8',
  );

  console.log(JSON.stringify({ outJson, outCsv, searched_count: all.length, candidate_rows: flat.length }, null, 2));
  client.close();
} finally {
  chrome.kill('SIGTERM');
}
