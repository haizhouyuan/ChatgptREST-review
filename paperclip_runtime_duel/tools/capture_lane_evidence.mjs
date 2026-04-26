#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";

const ROOT = "/vol1/1000/projects/toyresearch/paperclip_runtime_duel";
const STATE_PATH = path.join(ROOT, "state.json");
const lane = process.argv[2];

if (!["claude", "kimi", "claudeKimi"].includes(lane)) {
  console.error("Usage: node tools/capture_lane_evidence.mjs <claude|kimi|claudeKimi>");
  process.exit(2);
}

const state = JSON.parse(await fs.readFile(STATE_PATH, "utf8"));
const API = state.apiUrl || process.env.PAPERCLIP_API_URL || "http://127.0.0.1:3100";
const agentId = state.agents[lane];
const issueId = state.issues[lane];
const outputPath = state.outputPaths[lane];

async function api(pathname) {
  const res = await fetch(`${API}${pathname}`);
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) throw new Error(`GET ${pathname} failed ${res.status}: ${text}`);
  return body;
}

async function fileInfo(file) {
  try {
    const stat = await fs.stat(file);
    return { exists: true, size: stat.size, mtime: stat.mtime.toISOString() };
  } catch {
    return { exists: false, size: 0, mtime: null };
  }
}

const runs = await api(`/api/companies/${state.companyId}/heartbeat-runs?agentId=${agentId}&limit=50`);
const run = runs.find((entry) => {
  const ctx = entry.contextSnapshot || {};
  return ctx.issueId === issueId || ctx.taskId === issueId;
}) || runs[0] || null;
if (!run) throw new Error(`No heartbeat run found for lane ${lane}`);

const issue = await api(`/api/issues/${issueId}`);
const comments = await api(`/api/issues/${issueId}/comments?order=asc`);
const artifact = await fileInfo(outputPath);
const log = await api(`/api/heartbeat-runs/${run.id}/log?offset=0&limitBytes=160000`).catch((err) => ({ error: err.message }));
const evidence = {
  lane,
  checkedAt: new Date().toISOString(),
  companyId: state.companyId,
  agentId,
  issueId,
  run,
  issue: {
    id: issue.id,
    identifier: issue.identifier,
    title: issue.title,
    status: issue.status,
    priority: issue.priority,
    assigneeAgentId: issue.assigneeAgentId,
    completedAt: issue.completedAt,
  },
  artifact,
  latestComment: comments.at(-1) || null,
  comments: comments.map((comment) => ({
    id: comment.id,
    authorAgentId: comment.authorAgentId,
    createdByRunId: comment.createdByRunId,
    createdAt: comment.createdAt,
    bodyPreview: String(comment.body || "").slice(0, 1000),
  })),
  log,
};

const evidencePath = path.join(ROOT, "outputs", "evidence", `${lane}_run.json`);
await fs.writeFile(evidencePath, `${JSON.stringify(evidence, null, 2)}\n`);
console.log(JSON.stringify({
  lane,
  runStatus: run.status,
  issueStatus: issue.status,
  artifact,
  evidencePath,
}, null, 2));
