import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";

const TYPE = "kimi_cli";
const DEFAULT_COMMAND = "/home/yuanhaizhou/.local/bin/kimi-direct";
const DEFAULT_CONFIG_FILE = "/home/yuanhaizhou/.kimi/config.toml";
const DEFAULT_MODEL = "kimi-for-coding";
const DEFAULT_API_URL = "http://127.0.0.1:3100";
const DEFAULT_TIMEOUT_SEC = 900;

function asString(value, fallback = "") {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : fallback;
}

function asNumber(value, fallback) {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function asRecord(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function readPathInContext(context) {
  const wake = asRecord(context.paperclipWake);
  const issue = asRecord(wake.issue);
  return (
    asString(context.issueId) ||
    asString(context.taskId) ||
    asString(issue.id) ||
    null
  );
}

function renderTemplate(template, data) {
  return String(template ?? "").replace(/\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}/g, (_m, key) => {
    const parts = key.split(".");
    let current = data;
    for (const part of parts) {
      if (!current || typeof current !== "object") return "";
      current = current[part];
    }
    if (current == null) return "";
    if (typeof current === "object") return JSON.stringify(current, null, 2);
    return String(current);
  });
}

async function readFileIfPresent(filePath) {
  if (!filePath) return "";
  try {
    return await fs.readFile(filePath, "utf8");
  } catch {
    return "";
  }
}

async function fetchJson(url, token) {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await fetch(url, { headers });
  if (!res.ok) return null;
  return res.json();
}

async function patchIssueDone(apiUrl, issueId, token, runId, comment) {
  if (!issueId || !token) return { ok: false, reason: "missing issueId or auth token" };
  const res = await fetch(`${apiUrl}/api/issues/${issueId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Paperclip-Run-Id": runId,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ status: "done", comment }),
  });
  if (!res.ok) {
    return { ok: false, status: res.status, body: await res.text().catch(() => "") };
  }
  return { ok: true };
}

async function readSelectedSkills(config) {
  const entries = Array.isArray(config.paperclipRuntimeSkills) ? config.paperclipRuntimeSkills : [];
  const preference = asRecord(config.paperclipSkillSync);
  const desiredRaw = Array.isArray(preference.desiredSkills) ? preference.desiredSkills : [];
  const desired = new Set(desiredRaw.filter((v) => typeof v === "string").map((v) => v.trim()).filter(Boolean));
  const explicit = Object.prototype.hasOwnProperty.call(preference, "desiredSkills");
  const selected = entries.filter((entry) => {
    if (!entry || typeof entry !== "object") return false;
    if (entry.required) return true;
    if (!explicit) return false;
    return desired.has(entry.key) || desired.has(entry.runtimeName);
  });
  const blocks = [];
  for (const entry of selected) {
    const source = asString(entry.source);
    const key = asString(entry.key);
    if (!source || !key) continue;
    const body = await readFileIfPresent(path.join(source, "SKILL.md"));
    if (!body) continue;
    blocks.push(`## Skill: ${key}\n\n${body}`);
  }
  return blocks.join("\n\n---\n\n");
}

function stripResumeHint(text) {
  return text.replace(/\n?To resume this session: kimi -r [0-9a-f-]+/gi, "").trim();
}

function runProcess(command, args, options) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      env: options.env,
      stdio: ["ignore", "pipe", "pipe"],
      detached: false,
    });
    let stdout = "";
    let stderr = "";
    let timedOut = false;
    const timer = options.timeoutSec > 0
      ? setTimeout(() => {
          timedOut = true;
          child.kill("SIGTERM");
          setTimeout(() => child.kill("SIGKILL"), 10_000).unref();
        }, options.timeoutSec * 1000)
      : null;
    child.stdout.on("data", (chunk) => {
      const text = String(chunk);
      stdout += text;
      options.onStdout?.(text);
    });
    child.stderr.on("data", (chunk) => {
      const text = String(chunk);
      stderr += text;
      options.onStderr?.(text);
    });
    child.on("spawn", () => options.onSpawn?.(child.pid));
    child.on("close", (code, signal) => {
      if (timer) clearTimeout(timer);
      resolve({ code, signal, stdout, stderr, timedOut });
    });
    child.on("error", (err) => {
      if (timer) clearTimeout(timer);
      resolve({ code: -1, signal: null, stdout, stderr: `${stderr}\n${err.message}`, timedOut });
    });
  });
}

async function execute(ctx) {
  const { runId, agent, config, context, authToken, onLog, onMeta, onSpawn } = ctx;
  const command = asString(config.command, DEFAULT_COMMAND);
  const configFile = asString(config.configFile, DEFAULT_CONFIG_FILE);
  const model = asString(config.model, DEFAULT_MODEL);
  const apiUrl = asString(config.apiUrl, DEFAULT_API_URL).replace(/\/$/, "");
  const cwd = asString(config.cwd, process.cwd());
  const timeoutSec = asNumber(config.timeoutSec, DEFAULT_TIMEOUT_SEC);
  await fs.mkdir(cwd, { recursive: true });

  const issueId = readPathInContext(context);
  const issueContext = issueId
    ? await fetchJson(`${apiUrl}/api/issues/${issueId}/heartbeat-context`, authToken)
    : null;
  const comments = issueId
    ? await fetchJson(`${apiUrl}/api/issues/${issueId}/comments?order=asc`, authToken)
    : null;
  const instructions = await readFileIfPresent(asString(config.instructionsFilePath));
  const selectedSkills = await readSelectedSkills(config);
  const promptTemplate = asString(config.promptTemplate, "Complete the assigned Paperclip issue. Produce the requested artifact, then summarize exactly what changed.");
  const renderedPrompt = renderTemplate(promptTemplate, {
    agent,
    company: { id: agent.companyId },
    run: { id: runId },
    context,
  });

  const prompt = [
    "You are running inside Paperclip as the Kimi CLI local runtime.",
    "This is a non-interactive heartbeat. Complete the scoped issue now; do not stop at a plan.",
    "Use only the evidence in this prompt and the referenced local files. Mark uncertain claims as Hypothesis.",
    "Do not expose secrets, API keys, or private tokens.",
    selectedSkills ? `\n# Available Skills\n\n${selectedSkills}` : "",
    instructions ? `\n# Agent Instructions\n\n${instructions}` : "",
    `\n# Paperclip Context\n\n${JSON.stringify({ issueId, issueContext, comments, wake: context.paperclipWake ?? null }, null, 2)}`,
    `\n# Task Prompt\n\n${renderedPrompt}`,
  ].filter(Boolean).join("\n\n---\n\n");

  const args = [
    "--config-file", configFile,
    "--model", model,
    "--work-dir", cwd,
    "--quiet",
    "--prompt", prompt,
  ];
  const env = {
    ...process.env,
    HOME: asString(config.home, "/home/yuanhaizhou"),
    PATH: asString(config.pathEnv, `${process.env.PATH ?? ""}:/home/yuanhaizhou/.local/bin:/home/yuanhaizhou/local/node/bin`),
  };
  const envConfig = asRecord(config.env);
  for (const [k, v] of Object.entries(envConfig)) {
    if (typeof v === "string") env[k] = v;
  }
  if (authToken) env.PAPERCLIP_API_KEY = authToken;
  env.PAPERCLIP_API_URL = apiUrl;
  env.PAPERCLIP_AGENT_ID = agent.id;
  env.PAPERCLIP_COMPANY_ID = agent.companyId;
  env.PAPERCLIP_RUN_ID = runId;
  if (issueId) env.PAPERCLIP_TASK_ID = issueId;

  await onMeta?.({
    adapterType: TYPE,
    command,
    cwd,
    commandArgs: ["--config-file", configFile, "--model", model, "--work-dir", cwd, "--quiet", "--prompt", "<redacted prompt>"],
    commandNotes: ["Kimi CLI native print-mode run", "Prompt redacted from meta to avoid large issue/context duplication"],
    env: { HOME: env.HOME, PATH: env.PATH, PAPERCLIP_API_URL: apiUrl },
    promptMetrics: { promptChars: prompt.length },
    context,
  });

  const proc = await runProcess(command, args, {
    cwd,
    env,
    timeoutSec,
    onStdout: (text) => onLog("stdout", text),
    onStderr: (text) => onLog("stderr", text),
    onSpawn: (pid) => onSpawn?.({ pid, processGroupId: null, startedAt: new Date().toISOString() }),
  });
  const finalText = stripResumeHint(proc.stdout);
  let issuePatch = null;
  if (!proc.timedOut && (proc.code ?? 0) === 0 && issueId && config.autoUpdateIssue !== false) {
    const comment = [
      "Kimi CLI runtime completed this issue.",
      "",
      finalText.slice(0, 12_000),
    ].join("\n");
    issuePatch = await patchIssueDone(apiUrl, issueId, authToken, runId, comment);
  }

  const failed = proc.timedOut || (proc.code ?? 0) !== 0;
  return {
    exitCode: proc.code,
    signal: proc.signal,
    timedOut: proc.timedOut,
    errorMessage: failed ? (proc.timedOut ? `Timed out after ${timeoutSec}s` : `Kimi CLI exited with code ${proc.code ?? -1}`) : null,
    errorCode: failed ? (proc.timedOut ? "timeout" : "kimi_cli_failed") : null,
    provider: "kimi",
    biller: "kimi-code",
    model,
    billingType: "subscription",
    resultJson: {
      stdout: finalText,
      stderr: proc.stderr,
      issueId,
      issuePatch,
    },
    summary: finalText.slice(0, 8_000),
  };
}

async function testEnvironment(ctx) {
  const config = asRecord(ctx.config);
  const command = asString(config.command, DEFAULT_COMMAND);
  const checks = [];
  try {
    await fs.access(command);
    checks.push({ code: "command_exists", level: "info", message: `Kimi command exists: ${command}` });
  } catch {
    checks.push({ code: "command_missing", level: "error", message: `Kimi command missing: ${command}` });
  }
  const result = await runProcess(command, ["--version"], {
    cwd: process.cwd(),
    env: process.env,
    timeoutSec: 30,
  });
  if ((result.code ?? 0) === 0) {
    checks.push({ code: "version", level: "info", message: result.stdout.trim() || "version command passed" });
  } else {
    checks.push({ code: "version_failed", level: "error", message: result.stderr.trim() || "version command failed" });
  }
  return {
    adapterType: TYPE,
    status: checks.some((c) => c.level === "error") ? "fail" : "pass",
    checks,
    testedAt: new Date().toISOString(),
  };
}

function skillSnapshot(ctx, desiredSkills) {
  const config = asRecord(ctx.config);
  const entries = Array.isArray(config.paperclipRuntimeSkills) ? config.paperclipRuntimeSkills : [];
  return {
    adapterType: TYPE,
    supported: true,
    mode: "ephemeral",
    desiredSkills,
    entries: entries.map((entry) => ({
      key: entry.key,
      runtimeName: entry.runtimeName ?? null,
      desired: desiredSkills.includes(entry.key) || desiredSkills.includes(entry.runtimeName),
      managed: true,
      required: Boolean(entry.required),
      requiredReason: entry.requiredReason ?? null,
      state: "available",
      origin: entry.required ? "paperclip_required" : "company_managed",
      sourcePath: entry.source ?? null,
      targetPath: null,
      readOnly: true,
    })),
    warnings: ["Kimi CLI adapter injects selected skills into the prompt for each run; it does not persist a Kimi skills directory."],
  };
}

export function createServerAdapter() {
  return {
    type: TYPE,
    execute,
    testEnvironment,
    listSkills: async (ctx) => skillSnapshot(ctx, []),
    syncSkills: async (ctx, desiredSkills) => skillSnapshot(ctx, desiredSkills),
    supportsLocalAgentJwt: true,
    supportsInstructionsBundle: true,
    requiresMaterializedRuntimeSkills: false,
    instructionsPathKey: "instructionsFilePath",
    models: [{ id: DEFAULT_MODEL, label: "Kimi for Coding" }],
    async listModels() {
      return [{ id: DEFAULT_MODEL, label: "Kimi for Coding" }];
    },
    agentConfigurationDoc: `# kimi_cli agent configuration

Adapter: kimi_cli

Runs the local Kimi Code CLI in non-interactive print mode.

Core fields:
- command: absolute path to kimi-direct; default ${DEFAULT_COMMAND}
- configFile: Kimi config TOML; default ${DEFAULT_CONFIG_FILE}
- model: Kimi model; default ${DEFAULT_MODEL}
- cwd: absolute working directory
- instructionsFilePath: markdown file injected into each prompt
- promptTemplate: task prompt template
- apiUrl: Paperclip API URL; default ${DEFAULT_API_URL}
- autoUpdateIssue: boolean, default true; when true the adapter marks the scoped issue done with Kimi output
- timeoutSec: run timeout in seconds
- env: extra environment variables

Notes:
- This adapter uses the native Kimi CLI path, not Moonshot Open Platform kimi-k2.5.
- It receives a Paperclip run JWT and includes issue heartbeat context in the prompt.
`,
  };
}
