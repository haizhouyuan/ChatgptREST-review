#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";

const ROOT = "/vol1/1000/projects/toyresearch/paperclip_runtime_duel";
const EVIDENCE = path.join(ROOT, "outputs", "evidence");
const STATE = JSON.parse(await fs.readFile(path.join(ROOT, "state.json"), "utf8"));
const API = STATE.apiUrl || "http://127.0.0.1:3100";

async function api(pathname) {
  const res = await fetch(`${API}${pathname}`);
  const text = await res.text();
  if (!res.ok) throw new Error(`GET ${pathname} failed ${res.status}: ${text}`);
  return text ? JSON.parse(text) : null;
}

function redactValue(value) {
  if (typeof value === "string") {
    if (/sk-[A-Za-z0-9_-]{12,}/.test(value)) return "***REDACTED_SECRET_PATTERN***";
    if (/Bearer\s+[A-Za-z0-9._-]{12,}/i.test(value)) return "Bearer ***REDACTED***";
    return value;
  }
  if (Array.isArray(value)) return value.map(redactValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, val]) => {
      if (/^(?:raw|cached)?(?:Input|Output)Tokens$|^inputTokens$|^outputTokens$|^cachedInputTokens$|^rawCachedInputTokens$/i.test(key) && typeof val === "number") {
        return [key, val];
      }
      if (/(api[-_]?key|token|secret|password|authorization|credential|private[-_]?key)/i.test(key)) {
        return [key, "***REDACTED_KEY***"];
      }
      return [key, redactValue(val)];
    }));
  }
  return value;
}

async function writeJson(file, data) {
  await fs.writeFile(path.join(EVIDENCE, file), `${JSON.stringify(data, null, 2)}\n`);
}

async function sha256File(file) {
  const data = await fs.readFile(file);
  return crypto.createHash("sha256").update(data).digest("hex");
}

async function fileInfo(file) {
  const stat = await fs.stat(file);
  return {
    path: file,
    size: stat.size,
    sha256: await sha256File(file),
    mtime: stat.mtime.toISOString(),
  };
}

async function existingFiles(files) {
  const out = [];
  for (const file of files) {
    try {
      await fs.stat(file);
      out.push(file);
    } catch {
      // Optional boss-demo artifacts are exported only after they exist.
    }
  }
  return out;
}

async function walk(dir) {
  const out = [];
  for (const entry of await fs.readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (["node_modules", ".git"].includes(entry.name)) continue;
      out.push(...await walk(full));
    } else {
      out.push(full);
    }
  }
  return out;
}

async function secretScan() {
  const files = (await walk(ROOT)).filter((file) => {
    if (file.includes("/outputs/evidence/")) return false;
    return /\.(md|mjs|json|yaml|yml|toml|txt)$/.test(file);
  });
  const findings = [];
  const patterns = [
    { name: "sk_token", re: /sk-[A-Za-z0-9_-]{16,}/g },
    { name: "bearer_token", re: /Bearer\s+[A-Za-z0-9._-]{16,}/gi },
    { name: "private_key", re: /-----BEGIN [A-Z ]*PRIVATE KEY-----/g },
    { name: "inline_api_key_assignment", re: /(api[_-]?key|token|secret)\s*[:=]\s*["']?[A-Za-z0-9._-]{16,}/gi },
  ];
  for (const file of files) {
    const text = await fs.readFile(file, "utf8").catch(() => "");
    for (const pattern of patterns) {
      const matches = text.match(pattern.re) || [];
      for (const _match of matches) {
        findings.push({ file, pattern: pattern.name });
      }
    }
  }
  return {
    scannedAt: new Date().toISOString(),
    filesScanned: files.length,
    findingCount: findings.length,
    findings,
    pass: findings.length === 0,
  };
}

await fs.mkdir(EVIDENCE, { recursive: true });

const [company, adapters, agents, issues, runs] = await Promise.all([
  api(`/api/companies/${STATE.companyId}`),
  api("/api/adapters"),
  api(`/api/companies/${STATE.companyId}/agents`),
  api(`/api/companies/${STATE.companyId}/issues?limit=200`),
  api(`/api/companies/${STATE.companyId}/heartbeat-runs?limit=100`),
]);

const commentsByIssue = {};
for (const issue of issues) {
  const comments = await api(`/api/issues/${issue.id}/comments?order=asc`);
  commentsByIssue[issue.id] = comments.map((comment) => ({
    id: comment.id,
    authorAgentId: comment.authorAgentId,
    createdByRunId: comment.createdByRunId,
    createdAt: comment.createdAt,
    bodyPreview: String(comment.body || "").slice(0, 800),
  }));
}

await writeJson("runtime_config_redacted.json", {
  exportedAt: new Date().toISOString(),
  company: redactValue(company),
  adapters: adapters.filter((adapter) => ["claude_local", "kimi_cli"].includes(adapter.type)),
  agents: agents.map((agent) => redactValue({
    id: agent.id,
    name: agent.name,
    title: agent.title,
    adapterType: agent.adapterType,
    adapterConfig: agent.adapterConfig,
    runtimeConfig: agent.runtimeConfig,
    metadata: agent.metadata,
  })),
});

await writeJson("issues_redacted.json", {
  exportedAt: new Date().toISOString(),
  issues: issues.map((issue) => ({
    id: issue.id,
    identifier: issue.identifier,
    title: issue.title,
    status: issue.status,
    priority: issue.priority,
    assigneeAgentId: issue.assigneeAgentId,
    commentCount: commentsByIssue[issue.id]?.length || 0,
    latestComment: commentsByIssue[issue.id]?.at(-1) || null,
  })),
});

await writeJson("run_matrix.json", {
  exportedAt: new Date().toISOString(),
  runs: runs.map((run) => redactValue({
    id: run.id,
    agentId: run.agentId,
    status: run.status,
    invocationSource: run.invocationSource,
    triggerDetail: run.triggerDetail,
    startedAt: run.startedAt,
    finishedAt: run.finishedAt,
    error: run.error,
    errorCode: run.errorCode,
    usageJson: run.usageJson,
    contextSnapshot: run.contextSnapshot,
    livenessState: run.livenessState,
    livenessReason: run.livenessReason,
  })),
});

const artifactFiles = await existingFiles([
  STATE.outputPaths.claude,
  STATE.outputPaths.kimi,
  STATE.outputPaths.claudeKimi,
  path.join(ROOT, "outputs", "final_boss_entry.md"),
  path.join(ROOT, "outputs", "claude_kimi_comparison.md"),
  path.join(ROOT, "outputs", "boss_runtime_duel_entry.html"),
  path.join(ROOT, "outputs", "evidence", "pro_review_answer.md"),
  path.join(ROOT, "outputs", "evidence", "post_pro_iteration_summary.md"),
  path.join(EVIDENCE, "claude_run.json"),
  path.join(EVIDENCE, "kimi_run.json"),
  path.join(EVIDENCE, "claudeKimi_run.json"),
  path.join(EVIDENCE, "claudeKimi_operator_closeout.json"),
  path.join(EVIDENCE, "scorecard.json"),
  path.join(EVIDENCE, "mcp_tools_list_redacted.json"),
  path.join(EVIDENCE, "labebe_final_smoke_verification.json"),
  "/vol1/1000/projects/toyresearch/labebe-ai-design-studio/workspace/outputs/boss-demo-wow/index.html",
  "/vol1/1000/projects/toyresearch/labebe-ai-design-studio/workspace/outputs/boss-demo-onepager.html",
  "/vol1/1000/projects/toyresearch/labebe-ai-design-studio/workspace/outputs/frontstage-pack-verification.md",
  "/vol1/1000/projects/toyresearch/labebe-ai-design-studio/workspace/outputs/claim-lineage-matrix.md",
  "/vol1/1000/projects/toyresearch/labebe-ai-design-studio/workspace/outputs/space-smart-concept-card.md",
  "/vol1/1000/projects/toyresearch/qa/paperclip-wow/boss-demo-wow-desktop.png",
  "/vol1/1000/projects/toyresearch/qa/paperclip-wow/boss-demo-wow-mobile.png",
  "/vol1/1000/projects/toyresearch/qa/paperclip-wow/boss-demo-onepager-desktop.png",
  "/vol1/1000/projects/toyresearch/qa/paperclip-wow/boss-demo-onepager-mobile.png",
  path.join(ROOT, "outputs", "qa", "boss-runtime-duel-desktop.png"),
  path.join(ROOT, "outputs", "qa", "boss-runtime-duel-mobile.png"),
].filter(Boolean));
await writeJson("artifact_ledger.json", {
  exportedAt: new Date().toISOString(),
  artifacts: await Promise.all(artifactFiles.map(fileInfo)),
});

await writeJson("secret_scan.json", await secretScan());

const manifest = [
  "# Runtime Duel Evidence Manifest",
  "",
  `- Exported: ${new Date().toISOString()}`,
  `- Company: ${STATE.companyName} (${STATE.companyId})`,
  `- Claude issue: ${STATE.issues.claude}`,
  `- Kimi issue: ${STATE.issues.kimi}`,
  `- Claude Code Kimi issue: ${STATE.issues.claudeKimi || "not configured"}`,
  "",
  "## Core Artifacts",
  "",
  `- Claude output: ${STATE.outputPaths.claude}`,
  `- Kimi output: ${STATE.outputPaths.kimi}`,
  `- Claude Code Kimi output: ${STATE.outputPaths.claudeKimi || "not configured"}`,
  "- Claude Code Kimi comparison: outputs/claude_kimi_comparison.md",
  "- Final boss entry: outputs/final_boss_entry.md",
  "- Boss HTML entry: outputs/boss_runtime_duel_entry.html",
  "- Pro review answer: outputs/evidence/pro_review_answer.md",
  "- Post-Pro iteration summary: outputs/evidence/post_pro_iteration_summary.md",
  "- Scorecard: outputs/evidence/scorecard.json",
  "- Runtime config: outputs/evidence/runtime_config_redacted.json",
  "- Issues export: outputs/evidence/issues_redacted.json",
  "- Run matrix: outputs/evidence/run_matrix.json",
  "- Artifact ledger: outputs/evidence/artifact_ledger.json",
  "- Secret scan: outputs/evidence/secret_scan.json",
  "- Labebe smoke verification: outputs/evidence/labebe_final_smoke_verification.json",
  "- MCP tools list: outputs/evidence/mcp_tools_list_redacted.json",
  "",
  "## Interpretation",
  "",
  "This package compares local runtime aliases as configured on this machine. Claude Code is the local Claude Code CLI/client lane, Kimi is the native Kimi CLI lane via the local `kimi_cli` adapter, and Claude Code Kimi is the local `/home/yuanhaizhou/.local/bin/claudekimi` Claude Code compatibility wrapper routed to the Kimi coding endpoint. Model/provider claims must be read from adapter config and run evidence separately.",
  "",
].join("\n");
await fs.writeFile(path.join(EVIDENCE, "MANIFEST.md"), manifest);

console.log(JSON.stringify({
  evidenceDir: EVIDENCE,
  files: [
    "runtime_config_redacted.json",
    "issues_redacted.json",
    "run_matrix.json",
    "artifact_ledger.json",
    "secret_scan.json",
    "MANIFEST.md",
  ],
}, null, 2));
