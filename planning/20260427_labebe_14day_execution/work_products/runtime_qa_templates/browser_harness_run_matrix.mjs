#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const [matrixPath, outputDir] = process.argv.slice(2);

if (!matrixPath || !outputDir) {
  console.error('Usage: node browser_harness_run_matrix.mjs <matrix.json> <output-dir>');
  process.exit(2);
}

const scriptPath = fileURLToPath(new URL('./browser_harness_capture.mjs', import.meta.url));
const matrix = JSON.parse(await readFile(matrixPath, 'utf8'));
const baseUrl = matrix.baseUrl || '';
const captures = matrix.captures || [];

if (!captures.length) {
  console.error('Matrix must contain a non-empty captures array.');
  process.exit(2);
}

function cleanName(value) {
  return String(value || 'capture')
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80) || 'capture';
}

function resolveUrl(value) {
  if (/^https?:\/\//i.test(value)) return value;
  return `${baseUrl.replace(/\/$/, '')}/${String(value || '/').replace(/^\//, '')}`;
}

function runCapture(args) {
  return new Promise((resolveRun) => {
    const child = spawn(process.execPath, [scriptPath, ...args], {
      stdio: ['ignore', 'pipe', 'pipe'],
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
      resolveRun({ code, stdout, stderr, parsed });
    });
  });
}

await mkdir(outputDir, { recursive: true });

const startedAt = new Date().toISOString();
const results = [];

for (const capture of captures) {
  const name = cleanName(capture.name || basename(capture.url || 'capture'));
  const viewport = capture.viewport || {};
  const width = Number(capture.width || viewport.width || 1440);
  const height = Number(capture.height || viewport.height || 1100);
  const mobile = Boolean(capture.mobile || viewport.mobile);
  const outputPath = resolve(outputDir, capture.outputPath || `${name}.png`);
  await mkdir(dirname(outputPath), { recursive: true });

  const url = resolveUrl(capture.url || '/');
  const actionScript = capture.actionScript || '';
  const captureMode = capture.captureMode || 'viewport';
  const run = await runCapture([
    url,
    outputPath,
    String(width),
    String(height),
    mobile ? 'true' : 'false',
    actionScript,
    captureMode,
  ]);

  results.push({
    name,
    url,
    outputPath,
    metricsPath: run.parsed?.metricsPath || `${outputPath}.metrics.json`,
    width,
    height,
    mobile,
    captureMode,
    exitCode: run.code,
    ok: run.code === 0 && Boolean(run.parsed) && !run.parsed.horizontalOverflow && !run.parsed.likelyBlank && !run.parsed.hasConsoleErrors,
    horizontalOverflow: run.parsed?.horizontalOverflow ?? null,
    likelyBlank: run.parsed?.likelyBlank ?? null,
    hasConsoleErrors: run.parsed?.hasConsoleErrors ?? null,
    hasNetworkFailures: run.parsed?.hasNetworkFailures ?? null,
    visibleTextLength: run.parsed?.visibleTextLength ?? null,
    elementCount: run.parsed?.elementCount ?? null,
    stderr: run.stderr.trim(),
  });
}

const finishedAt = new Date().toISOString();
const report = {
  matrixPath,
  outputDir,
  startedAt,
  finishedAt,
  total: results.length,
  passed: results.filter((item) => item.ok).length,
  failed: results.filter((item) => !item.ok).length,
  results,
};

const reportJsonPath = join(outputDir, 'browser_harness_matrix_report.json');
const reportMdPath = join(outputDir, 'browser_harness_matrix_report.md');

await writeFile(reportJsonPath, JSON.stringify(report, null, 2));

const rows = results.map((item) => (
  `| ${item.ok ? 'pass' : 'review'} | ${item.name} | ${item.width}x${item.height}${item.mobile ? ' mobile' : ''} | overflow=${item.horizontalOverflow} | blank=${item.likelyBlank} | console=${item.hasConsoleErrors} | ${item.outputPath} |`
));

await writeFile(reportMdPath, [
  '# Browser Harness Matrix Report',
  '',
  `Generated: ${finishedAt}`,
  '',
  `Source matrix: \`${matrixPath}\``,
  '',
  `Pass: ${report.passed} / ${report.total}`,
  '',
  '| Status | Capture | Viewport | Overflow | Blank | Console | Screenshot |',
  '|---|---|---:|---|---|---|---|',
  ...rows,
  '',
  'Acceptance rule: pass means command exit code 0, parsed metrics exist, no horizontal overflow, not likely blank, and no captured console error.',
  '',
].join('\n'));

console.log(JSON.stringify(report, null, 2));
