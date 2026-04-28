#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, extname } from 'node:path';

const [url, outputPath, widthArg, heightArg, mobileArg = 'false', actionScript = '', captureMode = 'viewport'] = process.argv.slice(2);

if (!url || !outputPath || !widthArg || !heightArg) {
  console.error('Usage: node browser_harness_capture.mjs <url> <output.png> <width> <height> [mobile] [actionScript] [viewport|full]');
  process.exit(2);
}

const width = Number(widthArg);
const height = Number(heightArg);
const mobile = mobileArg === 'true';
const port = 9800 + Math.floor(Math.random() * 500);
const profileDir = `/tmp/labebe-harness-${process.pid}-${Date.now()}`;

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
  for (let i = 0; i < 50; i += 1) {
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
  const events = {
    console: [],
    exceptions: [],
    log: [],
    networkFailures: [],
  };
  ws.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    if (data.id && pending.has(data.id)) {
      pending.get(data.id)(data);
      pending.delete(data.id);
      return;
    }
    if (data.method === 'Runtime.consoleAPICalled') {
      events.console.push({
        type: data.params?.type || 'log',
        text: (data.params?.args || []).map((arg) => arg.value ?? arg.description ?? '').join(' ').slice(0, 1000),
        timestamp: data.params?.timestamp || null,
      });
    } else if (data.method === 'Runtime.exceptionThrown') {
      events.exceptions.push({
        text: data.params?.exceptionDetails?.text || 'exception',
        description: data.params?.exceptionDetails?.exception?.description || null,
        lineNumber: data.params?.exceptionDetails?.lineNumber ?? null,
        columnNumber: data.params?.exceptionDetails?.columnNumber ?? null,
      });
    } else if (data.method === 'Log.entryAdded') {
      events.log.push({
        level: data.params?.entry?.level || 'unknown',
        source: data.params?.entry?.source || 'unknown',
        text: (data.params?.entry?.text || '').slice(0, 1000),
        url: data.params?.entry?.url || null,
      });
    } else if (data.method === 'Network.loadingFailed') {
      events.networkFailures.push({
        requestId: data.params?.requestId || null,
        errorText: data.params?.errorText || null,
        type: data.params?.type || null,
        blockedReason: data.params?.blockedReason || null,
      });
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
        }, 9000);
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
    events,
  };
}

const metricsExpression = `(() => {
  const visibleText = document.body.innerText.slice(0, 5000);
  const buttons = [...document.querySelectorAll('button, a')].slice(0, 80).map((el) => ({
    tag: el.tagName.toLowerCase(),
    text: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 80),
    href: el.getAttribute('href') || null
  }));
  return {
    url: location.href,
    title: document.title,
    innerWidth,
    innerHeight,
    docScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    docScrollHeight: document.documentElement.scrollHeight,
    horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 2 || document.body.scrollWidth > innerWidth + 2,
    elementCount: document.querySelectorAll('*').length,
    imageCount: document.images.length,
    incompleteImages: [...document.images].filter((img) => !img.complete || img.naturalWidth === 0).length,
    visibleTextLength: document.body.innerText.trim().length,
    likelyBlank: document.querySelectorAll('*').length < 20 && document.body.innerText.trim().length < 80,
    visibleText,
    buttons
  };
})()`;

function sidecarPathFor(path) {
  const ext = extname(path);
  if (!ext) return `${path}.metrics.json`;
  return `${path.slice(0, -ext.length)}.metrics.json`;
}

function isIgnorableLogEntry(entry) {
  const url = entry.url || '';
  const text = entry.text || '';
  return url.endsWith('/favicon.ico') && /404|File not found/i.test(text);
}

try {
  const tabs = await fetchJson('/json/list');
  const tab = (Array.isArray(tabs) ? tabs : [tabs]).find((item) => item.type === 'page') || tabs[0];
  const client = connect(tab.webSocketDebuggerUrl);
  await client.ready;
  await client.send('Page.enable');
  await client.send('Runtime.enable');
  await client.send('Log.enable');
  await client.send('Network.enable');
  await client.send('Emulation.setDeviceMetricsOverride', {
    width,
    height,
    deviceScaleFactor: mobile ? 2 : 1,
    mobile,
  });
  await client.send('Page.navigate', { url });
  await sleep(1500);
  if (actionScript) {
    await client.send('Runtime.evaluate', {
      expression: `(async () => { ${actionScript} })()`,
      awaitPromise: true,
      returnByValue: true,
    });
    await sleep(700);
  }
  const metrics = await client.send('Runtime.evaluate', {
    expression: metricsExpression,
    returnByValue: true,
  });
  const captureParams = {
    format: 'png',
    fromSurface: true,
    captureBeyondViewport: captureMode === 'full',
  };
  if (captureMode === 'viewport') {
    captureParams.captureBeyondViewport = false;
  }
  const shot = await client.send('Page.captureScreenshot', {
    ...captureParams,
  });
  const payload = {
    ...metrics.result.result.value,
    captureMode,
    consoleMessages: client.events.console,
    exceptions: client.events.exceptions,
    logEntries: client.events.log,
    blockingLogEntries: client.events.log.filter((entry) => entry.level === 'error' && !isIgnorableLogEntry(entry)),
    networkFailures: client.events.networkFailures,
    hasConsoleErrors: client.events.exceptions.length > 0 || client.events.log.some((entry) => entry.level === 'error' && !isIgnorableLogEntry(entry)),
    hasNetworkFailures: client.events.networkFailures.length > 0,
    screenshotPath: outputPath,
    metricsPath: sidecarPathFor(outputPath),
    capturedAt: new Date().toISOString(),
  };
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, Buffer.from(shot.result.data, 'base64'));
  await writeFile(payload.metricsPath, JSON.stringify(payload, null, 2));
  console.log(JSON.stringify(payload, null, 2));
  client.close();
} finally {
  chrome.kill('SIGTERM');
}
