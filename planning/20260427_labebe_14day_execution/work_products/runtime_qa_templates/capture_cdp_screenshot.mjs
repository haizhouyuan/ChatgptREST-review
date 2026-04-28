#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';

const [url, outputPath, widthArg, heightArg, mobileArg = 'false'] = process.argv.slice(2);

if (!url || !outputPath || !widthArg || !heightArg) {
  console.error('Usage: node capture_cdp_screenshot.mjs <url> <output.png> <width> <height> [mobile]');
  process.exit(2);
}

const width = Number(widthArg);
const height = Number(heightArg);
const mobile = mobileArg === 'true';
const port = 9300 + Math.floor(Math.random() * 500);
const profileDir = `/tmp/labebe-cdp-${process.pid}-${Date.now()}`;

const chrome = spawn('/usr/bin/google-chrome', [
  '--headless=new',
  '--no-sandbox',
  '--disable-gpu',
  '--hide-scrollbars',
  `--user-data-dir=${profileDir}`,
  `--remote-debugging-port=${port}`,
  'about:blank',
], { stdio: 'ignore' });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function fetchJson(endpoint) {
  for (let i = 0; i < 40; i += 1) {
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
        }, 7000);
        pending.set(msg.id, resolve);
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

try {
  const tabs = await fetchJson('/json/list');
  const tab = (Array.isArray(tabs) ? tabs : [tabs]).find((item) => item.type === 'page') || tabs[0];
  const client = connect(tab.webSocketDebuggerUrl);
  await client.ready;
  await client.send('Page.enable');
  await client.send('Runtime.enable');
  await client.send('Emulation.setDeviceMetricsOverride', {
    width,
    height,
    deviceScaleFactor: mobile ? 2 : 1,
    mobile,
  });
  await client.send('Page.navigate', { url });
  await sleep(1400);
  const metrics = await client.send('Runtime.evaluate', {
    expression: `(() => ({
      url: location.href,
      innerWidth,
      innerHeight,
      docScrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      docScrollHeight: document.documentElement.scrollHeight,
      horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 2 || document.body.scrollWidth > innerWidth + 2
    }))()`,
    returnByValue: true,
  });
  const shot = await client.send('Page.captureScreenshot', {
    format: 'png',
    fromSurface: true,
    captureBeyondViewport: false,
  });
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, Buffer.from(shot.result.data, 'base64'));
  console.log(JSON.stringify(metrics.result.result.value, null, 2));
  client.close();
} finally {
  chrome.kill('SIGTERM');
}
