#!/usr/bin/env node
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';

const apiBase = process.env.PAPERCLIP_API_BASE || 'http://127.0.0.1:3100/api';
const companyId = process.env.PAPERCLIP_COMPANY_ID || '1cb6d439-2bdf-4f63-ad9a-b5326d5546df';
const projectId = process.env.PAPERCLIP_PROJECT_ID || '361859e3-baa5-4946-ae84-34a5d1c2ab5e';
const root = resolve('/vol1/1000/projects/toyresearch');
const mapPath = resolve(root, 'planning/20260427_labebe_14day_execution/work_products/boss_gallery_v0/boss_gallery_issue_evidence_map.csv');
const staticMapPath = resolve(root, 'paperclip_runtime_duel/outputs/boss_gallery_v0/boss_gallery_issue_evidence_map.csv');
const reportPath = resolve(root, 'planning/20260427_labebe_14day_execution/work_products/boss_gallery_v0/boss_gallery_paperclip_binding_report.md');

const issueBindings = {
  'LAB-BG-A': { identifier: 'LAB-2', id: 'a1e244f8-b57b-4375-961a-c3a3afe94700', title: 'EPIC 2 - Product Opportunity Radar' },
  'LAB-BG-B': { identifier: 'LAB-3', id: '45807314-df5d-4855-9cdd-9ed1a6d1ff02', title: 'EPIC 3 - VOC to Product Concept' },
  'LAB-BG-C': { identifier: 'LAB-4', id: '227c4590-c47b-40ff-8792-82ca4ec6bba8', title: 'EPIC 4 - Sketch-to-Concept Lab' },
  'LAB-BG-D': { identifier: 'LAB-5', id: 'b69154fd-e3eb-4910-a63d-ef9d480a5a64', title: 'EPIC 5 - Custom Toy Kitchen Builder' },
  'LAB-BG-E': { identifier: 'LAB-7', id: 'a2508878-eeb2-4ee3-a5d4-6ed5c5674e9d', title: 'EPIC 7 - DFM / Safety / Cost Preflight' },
  'LAB-BG-F': { identifier: 'LAB-8', id: '812018a6-1f22-4c31-9cbd-8ae42a500ba5', title: 'EPIC 8 - Concept-to-Market Asset Matrix' },
};

const bossDemoIssue = { identifier: 'LAB-9', id: '68edbe40-7f7e-45fb-beed-e9f6e234539c', title: 'EPIC 9 - Boss Demo Production' };

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];
    if (quoted) {
      if (char === '"' && next === '"') {
        field += '"';
        i += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ',') {
      row.push(field);
      field = '';
    } else if (char === '\n') {
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
    } else if (char !== '\r') {
      field += char;
    }
  }
  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }
  const [headers, ...data] = rows;
  return data.filter((cells) => cells.some(Boolean)).map((cells) => Object.fromEntries(headers.map((header, index) => [header, cells[index] || ''])));
}

function csvEscape(value) {
  const text = String(value ?? '');
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function toCsv(rows, headers) {
  return [
    headers.join(','),
    ...rows.map((row) => headers.map((header) => csvEscape(row[header])).join(',')),
  ].join('\n') + '\n';
}

async function paperclip(method, path, body) {
  const response = await fetch(`${apiBase}${path}`, {
    method,
    headers: { 'content-type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!response.ok) {
    throw new Error(`${method} ${path} failed ${response.status}: ${text}`);
  }
  return data;
}

function evidenceBody(row, binding) {
  return `# Boss Gallery Evidence Binding

Local demo row: \`${row.issue_id}\`
Paperclip issue: \`${binding.identifier}\` / \`${binding.id}\`
Project: \`${projectId}\`

## Demo Track

${row.demo_track}

## Evidence ID

${row.evidence_id}

## Business Question

${row.business_question}

## Key Inputs

${row.key_inputs}

## Key Outputs

${row.key_outputs}

## Claim Gate

${row.claim_gate}

## Required Next Review

${row.required_next_review}

## Evidence Paths

- Static Boss Gallery: \`paperclip_runtime_duel/outputs/boss_gallery_v0/index.html\`
- Issue/evidence map: \`planning/20260427_labebe_14day_execution/work_products/boss_gallery_v0/boss_gallery_issue_evidence_map.csv\`
- Claim ledger: \`planning/20260427_labebe_14day_execution/work_products/boss_gallery_v0/boss_gallery_claim_ledger.csv\`
- Browser Harness smoke: \`qa/browser-harness-p0-smoke-20260428/browser_harness_matrix_report.md\`
- Boss Gallery desktop video: \`paperclip_runtime_duel/outputs/boss_gallery_v0/labebe_boss_gallery_walkthrough.mp4\`
- Boss Gallery mobile video: \`paperclip_runtime_duel/outputs/boss_gallery_v0/labebe_boss_gallery_walkthrough_mobile.mp4\`

## Boundary

This document binds the Boss Gallery row to an existing Paperclip issue. It does
not mark the issue done, does not approve external publication, and does not
override the Claim Gate.
`;
}

function indexBody(rows) {
  const table = rows.map((row) => {
    const binding = issueBindings[row.issue_id];
    return `| ${row.issue_id} | ${row.demo_track} | ${binding.identifier} | ${row.evidence_id} | ${row.claim_gate} |`;
  }).join('\n');
  return `# Boss Gallery Issue Index

This document links the internal Boss Gallery A-F demo tracks to existing
Paperclip issues in the Labebe AI Design Studio company.

Company: \`${companyId}\`
Project: \`${projectId}\`

| Local Row | Demo Track | Paperclip Issue | Evidence ID | Claim Gate |
|---|---|---|---|---|
${table}

## Shared Evidence

- Static Boss Gallery: \`paperclip_runtime_duel/outputs/boss_gallery_v0/index.html\`
- Issue/evidence map: \`planning/20260427_labebe_14day_execution/work_products/boss_gallery_v0/boss_gallery_issue_evidence_map.csv\`
- Claim ledger: \`planning/20260427_labebe_14day_execution/work_products/boss_gallery_v0/boss_gallery_claim_ledger.csv\`
- Browser Harness P0 smoke: \`qa/browser-harness-p0-smoke-20260428/browser_harness_matrix_report.md\`
- Desktop walkthrough: \`paperclip_runtime_duel/outputs/boss_gallery_v0/labebe_boss_gallery_walkthrough.mp4\`
- Mobile walkthrough: \`paperclip_runtime_duel/outputs/boss_gallery_v0/labebe_boss_gallery_walkthrough_mobile.mp4\`

## Boundary

The Boss Gallery remains an internal AI application result surface. It must stay
separate from the consumer DTC website and every generated output remains gated
by brand, claim, commerce, safety/DFM, and media-rights review as applicable.
`;
}

const rows = parseCsv(await readFile(mapPath, 'utf8'));
for (const row of rows) {
  const binding = issueBindings[row.issue_id];
  if (!binding) throw new Error(`No Paperclip binding for ${row.issue_id}`);
  row.status = 'bound_to_existing_paperclip_issue';
  row.live_paperclip_issue = `${binding.identifier} | ${binding.id}`;
  await paperclip('PUT', `/issues/${binding.id}/documents/boss_gallery_evidence`, {
    title: 'Boss Gallery Evidence Binding',
    format: 'markdown',
    body: evidenceBody(row, binding),
  });
}

await paperclip('PUT', `/issues/${bossDemoIssue.id}/documents/boss_gallery_index`, {
  title: 'Boss Gallery Issue Index',
  format: 'markdown',
  body: indexBody(rows),
});

await paperclip('POST', `/issues/${bossDemoIssue.id}/comments`, {
  body: [
    'Boss Gallery evidence map has been bound to existing Labebe Paperclip issues.',
    '',
    '- Demo A -> LAB-2',
    '- Demo B -> LAB-3',
    '- Demo C -> LAB-4',
    '- Demo D -> LAB-5',
    '- Demo E -> LAB-7',
    '- Demo F -> LAB-8',
    '',
    'The mapping is evidence-only and does not approve publication or close any issue.',
  ].join('\n'),
});

const headers = Object.keys(parseCsv(await readFile(mapPath, 'utf8'))[0]);
await writeFile(mapPath, toCsv(rows, headers));
await mkdir(dirname(staticMapPath), { recursive: true });
await writeFile(staticMapPath, toCsv(rows, headers));

const verifiedDocs = [];
for (const row of rows) {
  const binding = issueBindings[row.issue_id];
  const doc = await paperclip('GET', `/issues/${binding.id}/documents/boss_gallery_evidence`);
  verifiedDocs.push({ localIssueId: row.issue_id, paperclipIssue: binding.identifier, issueId: binding.id, documentKey: doc.key, revisionId: doc.currentRevisionId || doc.revisionId || null });
}
const indexDoc = await paperclip('GET', `/issues/${bossDemoIssue.id}/documents/boss_gallery_index`);

const report = `# Boss Gallery Paperclip Binding Report

Generated: ${new Date().toISOString()}

Company: \`${companyId}\`
Project: \`${projectId}\`

## Result

- Bound six Boss Gallery demo rows to existing Paperclip issues.
- Created/updated \`boss_gallery_evidence\` document on each mapped issue.
- Created/updated \`boss_gallery_index\` document on \`${bossDemoIssue.identifier}\`.
- Added a comment to \`${bossDemoIssue.identifier}\`.
- Updated local and static CSV maps with live Paperclip issue references.

## Bindings

| Local Row | Paperclip Issue | Issue UUID | Document |
|---|---|---|---|
${verifiedDocs.map((item) => `| ${item.localIssueId} | ${item.paperclipIssue} | ${item.issueId} | ${item.documentKey} |`).join('\n')}

Index document: \`${indexDoc.key}\` on \`${bossDemoIssue.identifier}\`.

## Boundary

This is evidence binding only. It does not mark issues done, does not approve
external publication, and does not bypass the Claim Gate.
`;

await writeFile(reportPath, report);
console.log(JSON.stringify({ ok: true, reportPath, verifiedDocs, indexDocument: indexDoc.key }, null, 2));
