#!/usr/bin/env node
import { spawn, spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const root = resolve('/vol1/1000/projects/toyresearch');
const url = process.env.BOSS_GALLERY_URL || 'http://fnos.dandanbaba.xyz:8778/boss_gallery_v0/index.html';
const outDir = resolve(root, 'paperclip_runtime_duel/outputs/boss_gallery_v0');
const frameDir = resolve(outDir, 'walkthrough_frames');
const desktopOutput = resolve(outDir, 'labebe_boss_gallery_walkthrough.mp4');
const desktopPoster = resolve(outDir, 'labebe_boss_gallery_walkthrough_poster.jpg');
const desktopContact = resolve(outDir, 'labebe_boss_gallery_walkthrough_contact_sheet.jpg');
const mobileOutput = resolve(outDir, 'labebe_boss_gallery_walkthrough_mobile.mp4');
const mobilePoster = resolve(outDir, 'labebe_boss_gallery_walkthrough_mobile_poster.jpg');
const mobileContact = resolve(outDir, 'labebe_boss_gallery_walkthrough_mobile_contact_sheet.jpg');
const desktopList = resolve(outDir, 'boss_gallery_walkthrough_frames.txt');
const mobileList = resolve(outDir, 'boss_gallery_walkthrough_mobile_frames.txt');

mkdirSync(frameDir, { recursive: true });

const sleep = (ms) => new Promise((resolveSleep) => setTimeout(resolveSleep, ms));

async function fetchJson(port, endpoint) {
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
  const ready = new Promise((resolveReady) => ws.addEventListener('open', resolveReady, { once: true }));
  return {
    ready,
    send(method, params = {}) {
      const msg = { id: ++id, method, params };
      return new Promise((resolveSend) => {
        const timer = setTimeout(() => {
          pending.delete(msg.id);
          resolveSend({ error: { message: `CDP timeout: ${method}` } });
        }, 9000);
        pending.set(msg.id, (data) => {
          clearTimeout(timer);
          resolveSend(data);
        });
        ws.send(JSON.stringify(msg));
      });
    },
    close() {
      ws.close();
    },
  };
}

async function captureFrames({ prefix, width, height, mobile, positions }) {
  const port = 9400 + Math.floor(Math.random() * 400);
  const profileDir = `/tmp/labebe-boss-gallery-cdp-${process.pid}-${Date.now()}-${prefix}`;
  const chrome = spawn('/usr/bin/google-chrome', [
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--hide-scrollbars',
    `--user-data-dir=${profileDir}`,
    `--remote-debugging-port=${port}`,
    'about:blank',
  ], { stdio: 'ignore' });

  try {
    const tabs = await fetchJson(port, '/json/list');
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
    await sleep(1600);
    const metrics = await client.send('Runtime.evaluate', {
      expression: `(() => ({
        url: location.href,
        innerWidth,
        innerHeight,
        scrollHeight: document.documentElement.scrollHeight,
        horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 2 || document.body.scrollWidth > innerWidth + 2
      }))()`,
      returnByValue: true,
    });
    const scrollHeight = metrics.result.result.value.scrollHeight;
    const maxY = Math.max(0, scrollHeight - height);
    const framePaths = [];
    for (const [idx, pct] of positions.entries()) {
      const y = Math.round(maxY * pct);
      await client.send('Runtime.evaluate', { expression: `window.scrollTo(0, ${y})` });
      await sleep(500);
      const shot = await client.send('Page.captureScreenshot', {
        format: 'png',
        fromSurface: true,
        captureBeyondViewport: false,
      });
      const frame = resolve(frameDir, `${prefix}_${String(idx + 1).padStart(2, '0')}.png`);
      writeFileSync(frame, Buffer.from(shot.result.data, 'base64'));
      framePaths.push(frame);
    }
    client.close();
    return { metrics: metrics.result.result.value, framePaths };
  } finally {
    chrome.kill('SIGTERM');
  }
}

function writeConcatList(file, frames, duration) {
  writeFileSync(
    file,
    frames.map((frame) => `file '${frame}'\nduration ${duration}`).join('\n') + `\nfile '${frames.at(-1)}'\n`,
  );
}

function render({ list, frames, output, poster, contact, width, height, duration, contactTile }) {
  writeConcatList(list, frames, duration);
  const filter =
    `scale=${width}:${height}:force_original_aspect_ratio=decrease,` +
    `pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2:color=0x101915,` +
    'format=yuv420p';
  const video = spawnSync('ffmpeg', [
    '-y',
    '-f',
    'concat',
    '-safe',
    '0',
    '-i',
    list,
    '-vf',
    filter,
    '-r',
    '30',
    '-c:v',
    'libx264',
    '-pix_fmt',
    'yuv420p',
    output,
  ], { stdio: 'inherit' });
  if (video.status !== 0) process.exit(video.status ?? 1);
  spawnSync('ffmpeg', ['-y', '-i', output, '-frames:v', '1', '-q:v', '2', '-update', '1', poster], { stdio: 'inherit' });
  spawnSync('ffmpeg', ['-y', '-i', output, '-vf', contactTile, '-frames:v', '1', '-q:v', '2', '-update', '1', contact], { stdio: 'inherit' });
}

const desktop = await captureFrames({
  prefix: 'desktop',
  width: 1440,
  height: 1000,
  mobile: false,
  positions: [0, 0.18, 0.38, 0.58, 0.78, 1],
});

const mobile = await captureFrames({
  prefix: 'mobile',
  width: 390,
  height: 900,
  mobile: true,
  positions: [0, 0.14, 0.28, 0.42, 0.56, 0.7, 0.84, 1],
});

render({
  list: desktopList,
  frames: desktop.framePaths,
  output: desktopOutput,
  poster: desktopPoster,
  contact: desktopContact,
  width: 1920,
  height: 1080,
  duration: 7,
  contactTile: 'fps=1/7,scale=300:-1,tile=6x1:padding=10:margin=10:color=0x101915',
});

render({
  list: mobileList,
  frames: mobile.framePaths,
  output: mobileOutput,
  poster: mobilePoster,
  contact: mobileContact,
  width: 1080,
  height: 1920,
  duration: 5,
  contactTile: 'fps=1/5,scale=190:-1,tile=8x1:padding=10:margin=10:color=0x101915',
});

console.log(JSON.stringify({
  url,
  desktopMetrics: desktop.metrics,
  mobileMetrics: mobile.metrics,
  desktopOutput,
  desktopPoster,
  desktopContact,
  mobileOutput,
  mobilePoster,
  mobileContact,
}, null, 2));
