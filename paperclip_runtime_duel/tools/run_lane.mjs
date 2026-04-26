#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";

const ROOT = "/vol1/1000/projects/toyresearch/paperclip_runtime_duel";
const STATE_PATH = path.join(ROOT, "state.json");
const lane = process.argv[2];

if (!["claude", "kimi"].includes(lane)) {
  console.error("Usage: node tools/run_lane.mjs <claude|kimi>");
  process.exit(2);
}

const state = JSON.parse(await fs.readFile(STATE_PATH, "utf8"));
const API = state.apiUrl || process.env.PAPERCLIP_API_URL || "http://127.0.0.1:3100";
const agentId = state.agents[lane];
const issueId = state.issues[lane];
const outputPath = state.outputPaths[lane];

async function api(pathname, options = {}) {
  const res = await fetch(`${API}${pathname}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new Error(`${options.method || "GET"} ${pathname} failed ${res.status}: ${text}`);
  }
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

function terminal(status) {
  return ["succeeded", "failed", "cancelled", "timed_out"].includes(status);
}

async function findRun(initialRunId) {
  if (initialRunId) {
    const run = await api(`/api/heartbeat-runs/${initialRunId}`).catch(() => null);
    if (run) return run;
  }
  const runs = await api(`/api/companies/${state.companyId}/heartbeat-runs?agentId=${agentId}&limit=20`);
  return runs.find((run) => {
    const ctx = run.contextSnapshot || {};
    return ctx.issueId === issueId || ctx.taskId === issueId;
  }) || runs[0] || null;
}

const wake = await api(`/api/agents/${agentId}/wakeup`, {
  method: "POST",
  body: JSON.stringify({
    source: "on_demand",
    triggerDetail: "manual",
    reason: "runtime_duel_manual_start",
    payload: { issueId, lane },
    idempotencyKey: `runtime-duel-${lane}-${Date.now()}`,
    forceFreshSession: true,
  }),
});

let run = wake?.id ? wake : null;
console.log(JSON.stringify({ lane, wake }, null, 2));

const started = Date.now();
let lastStatus = "";
while (Date.now() - started < 20 * 60 * 1000) {
  await new Promise((resolve) => setTimeout(resolve, 5000));
  run = await findRun(run?.id);
  if (!run) continue;
  if (run.status !== lastStatus) {
    console.log(`[${lane}] run ${run.id} status=${run.status}`);
    lastStatus = run.status;
  }
  if (terminal(run.status)) break;
}

if (!run) throw new Error(`No heartbeat run found for lane ${lane}`);
const issue = await api(`/api/issues/${issueId}`);
const comments = await api(`/api/issues/${issueId}/comments?order=asc`);
const artifact = await fileInfo(outputPath);
const log = await api(`/api/heartbeat-runs/${run.id}/log?offset=0&limitBytes=120000`).catch((err) => ({ error: err.message }));
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
  },
  artifact,
  latestComment: comments.at(-1) || null,
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

if (run.status !== "succeeded") {
  throw new Error(`${lane} run did not succeed: ${run.status}`);
}
if (issue.status !== "done") {
  throw new Error(`${lane} issue not done: ${issue.status}`);
}
if (!artifact.exists || artifact.size < 1000) {
  throw new Error(`${lane} artifact missing or too small: ${JSON.stringify(artifact)}`);
}
