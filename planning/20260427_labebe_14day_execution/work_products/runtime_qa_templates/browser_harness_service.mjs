#!/usr/bin/env node
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { mkdtemp, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const host = process.env.BROWSER_HARNESS_HOST || '127.0.0.1';
const port = Number(process.env.BROWSER_HARNESS_PORT || process.argv[2] || 8789);
const token = process.env.BROWSER_HARNESS_TOKEN || '';
const maxBodyBytes = Number(process.env.BROWSER_HARNESS_MAX_BODY_BYTES || 1_000_000);
const baseDir = dirname(fileURLToPath(import.meta.url));
const captureScript = resolve(baseDir, 'browser_harness_capture.mjs');
const matrixScript = resolve(baseDir, 'browser_harness_run_matrix.mjs');

function sendJson(res, status, body) {
  const payload = JSON.stringify(body, null, 2);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(payload),
  });
  res.end(payload);
}

function isAuthorized(req) {
  if (!token) return true;
  return req.headers.authorization === `Bearer ${token}`;
}

function readBody(req) {
  return new Promise((resolveRead, rejectRead) => {
    let total = 0;
    const chunks = [];
    req.on('data', (chunk) => {
      total += chunk.length;
      if (total > maxBodyBytes) {
        rejectRead(new Error('Request body too large'));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => {
      try {
        const raw = Buffer.concat(chunks).toString('utf8') || '{}';
        resolveRead(JSON.parse(raw));
      } catch (error) {
        rejectRead(new Error(`Invalid JSON body: ${error.message}`));
      }
    });
    req.on('error', rejectRead);
  });
}

function validateUrl(url) {
  if (!/^https?:\/\//i.test(String(url || ''))) {
    throw new Error('Only http(s) URLs are accepted by the service API.');
  }
}

function runNodeScript(script, args) {
  return new Promise((resolveRun) => {
    const child = spawn(process.execPath, [script, ...args], {
      stdio: ['ignore', 'pipe', 'pipe'],
      env: process.env,
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });
    child.on('close', (code) => {
      let parsed = null;
      try {
        parsed = JSON.parse(stdout);
      } catch {
        parsed = null;
      }
      resolveRun({ exitCode: code, stdout, stderr, parsed });
    });
  });
}

function captureSchema() {
  return {
    purpose: 'Browser Harness QA/evidence service. Local deterministic capture only.',
    auth: token ? 'Authorization: Bearer <BROWSER_HARNESS_TOKEN>' : 'disabled for localhost dev',
    endpoints: {
      'GET /health': 'service health and boundary flags',
      'GET /schema': 'request/response schema',
      'POST /capture': {
        required: ['url', 'outputPath'],
        optional: ['width', 'height', 'mobile', 'actionScript', 'captureMode'],
      },
      'POST /matrix': {
        required: ['outputDir', 'matrixPath or matrix'],
      },
    },
    boundaries: [
      'does not manage authenticated sessions',
      'does not submit ChatGPT/Gemini/Pro jobs',
      'does not decide design direction',
      'does not publish or edit code',
      'uses a fresh temporary Chrome profile per capture',
    ],
  };
}

async function handleCapture(body) {
  validateUrl(body.url);
  if (!body.outputPath) throw new Error('capture requires outputPath');
  const width = Number(body.width || body.viewport?.width || 1440);
  const height = Number(body.height || body.viewport?.height || 1100);
  const mobile = Boolean(body.mobile || body.viewport?.mobile);
  const captureMode = body.captureMode || 'viewport';
  const actionScript = body.actionScript || '';
  const outputPath = resolve(String(body.outputPath));
  const run = await runNodeScript(captureScript, [
    String(body.url),
    outputPath,
    String(width),
    String(height),
    mobile ? 'true' : 'false',
    actionScript,
    captureMode,
  ]);
  return {
    ok: run.exitCode === 0 && Boolean(run.parsed),
    exitCode: run.exitCode,
    parsed: run.parsed,
    stderr: run.stderr.trim(),
    stdoutPreview: run.parsed ? null : run.stdout.slice(0, 2000),
  };
}

async function handleMatrix(body) {
  if (!body.outputDir) throw new Error('matrix requires outputDir');
  let matrixPath = body.matrixPath ? resolve(String(body.matrixPath)) : '';
  if (!matrixPath) {
    if (!body.matrix || typeof body.matrix !== 'object') {
      throw new Error('matrix requires matrixPath or matrix object');
    }
    const tmp = await mkdtemp(`${tmpdir()}/browser-harness-matrix-`);
    matrixPath = resolve(tmp, 'matrix.json');
    await writeFile(matrixPath, JSON.stringify(body.matrix, null, 2));
  }
  const outputDir = resolve(String(body.outputDir));
  const run = await runNodeScript(matrixScript, [matrixPath, outputDir]);
  return {
    ok: run.exitCode === 0 && Boolean(run.parsed),
    exitCode: run.exitCode,
    parsed: run.parsed,
    stderr: run.stderr.trim(),
    stdoutPreview: run.parsed ? null : run.stdout.slice(0, 2000),
  };
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url || '/', `http://${host}:${port}`);
    if (!isAuthorized(req)) {
      sendJson(res, 401, { ok: false, error: 'Unauthorized' });
      return;
    }

    if (req.method === 'GET' && url.pathname === '/health') {
      sendJson(res, 200, {
        ok: true,
        service: 'browser-harness-p0',
        host,
        port,
        authRequired: Boolean(token),
        boundary: 'QA/evidence support only',
      });
      return;
    }

    if (req.method === 'GET' && url.pathname === '/schema') {
      sendJson(res, 200, { ok: true, schema: captureSchema() });
      return;
    }

    if (req.method === 'POST' && url.pathname === '/capture') {
      const body = await readBody(req);
      sendJson(res, 200, await handleCapture(body));
      return;
    }

    if (req.method === 'POST' && url.pathname === '/matrix') {
      const body = await readBody(req);
      sendJson(res, 200, await handleMatrix(body));
      return;
    }

    sendJson(res, 404, { ok: false, error: 'Not found' });
  } catch (error) {
    sendJson(res, 400, { ok: false, error: error.message });
  }
});

server.listen(port, host, () => {
  console.log(JSON.stringify({
    ok: true,
    service: 'browser-harness-p0',
    url: `http://${host}:${port}`,
    authRequired: Boolean(token),
  }));
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    server.close(() => process.exit(0));
  });
}
