#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";

const ROOT = "/vol1/1000/projects/toyresearch/paperclip_runtime_duel";
const STATE_PATH = path.join(ROOT, "state.json");
const lane = process.argv[2];

if (!["claude", "kimi", "claudeKimi"].includes(lane)) {
  console.error("Usage: node tools/close_lane_issue.mjs <claude|kimi|claudeKimi>");
  process.exit(2);
}

const state = JSON.parse(await fs.readFile(STATE_PATH, "utf8"));
const API = state.apiUrl || process.env.PAPERCLIP_API_URL || "http://127.0.0.1:3100";
const issueId = state.issues[lane];
const agentId = state.agents[lane];
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
  const stat = await fs.stat(file);
  return { path: file, size: stat.size, mtime: stat.mtime.toISOString() };
}

const artifact = await fileInfo(outputPath);
if (artifact.size < 1000) {
  throw new Error(`Artifact is too small for closeout: ${JSON.stringify(artifact)}`);
}

const runs = await api(`/api/companies/${state.companyId}/heartbeat-runs?agentId=${agentId}&limit=20`);
const run = runs.find((entry) => {
  const ctx = entry.contextSnapshot || {};
  return ctx.issueId === issueId || ctx.taskId === issueId;
}) || runs[0];
if (!run || run.status !== "succeeded") {
  throw new Error(`Latest lane run did not succeed: ${run ? run.status : "missing"}`);
}

const comment = [
  `Operator-verified closeout for ${lane}.`,
  "",
  `Run: ${run.id} (${run.status})`,
  `Artifact: ${artifact.path}`,
  `Size: ${artifact.size} bytes`,
  "",
  "Reason: the artifact exists and the heartbeat run succeeded. This closeout is explicit because Paperclip's `claude_local` adapter writes the final assistant answer as a comment but does not automatically transition issue status to `done`.",
].join("\n");

const issue = await api(`/api/issues/${issueId}`, {
  method: "PATCH",
  body: JSON.stringify({ status: "done", comment }),
});

const evidence = {
  lane,
  closedAt: new Date().toISOString(),
  issueId,
  issueStatus: issue.status,
  run: { id: run.id, status: run.status },
  artifact,
  commentId: issue.comment?.id || null,
};

const outPath = path.join(ROOT, "outputs", "evidence", `${lane}_operator_closeout.json`);
await fs.writeFile(outPath, `${JSON.stringify(evidence, null, 2)}\n`);
console.log(JSON.stringify(evidence, null, 2));
