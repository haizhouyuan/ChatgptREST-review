#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";

const ROOT = "/vol1/1000/projects/toyresearch/paperclip_runtime_duel";
const API = process.env.PAPERCLIP_API_URL || "http://127.0.0.1:3100";
const STATE_PATH = path.join(ROOT, "state.json");
const PATH_ENV = [
  "/vol1/1000/home-yuanhaizhou/_root_home/.local/bin",
  "/home/yuanhaizhou/.local/bin",
  "/home/yuanhaizhou/local/node/bin",
  "/usr/local/sbin",
  "/usr/local/bin",
  "/usr/sbin",
  "/usr/bin",
  "/sbin",
  "/bin",
].join(":");
const COMPANY_NAME = "Runtime Duel Studio - Claude Code vs Kimi";
const PROJECT_NAME = "Same-Goal Boss Demo Generation";

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

async function maybeReadState() {
  try {
    return JSON.parse(await fs.readFile(STATE_PATH, "utf8"));
  } catch {
    return null;
  }
}

async function writeState(state) {
  await fs.writeFile(STATE_PATH, `${JSON.stringify(state, null, 2)}\n`);
}

async function ensureAdapter() {
  const adapters = await api("/api/adapters");
  if (adapters.some((a) => a.type === "kimi_cli" && !a.disabled)) {
    return { installed: false, type: "kimi_cli" };
  }
  return api("/api/adapters/install", {
    method: "POST",
    body: JSON.stringify({
      packageName: path.join(ROOT, "adapter-kimi-cli"),
      isLocalPath: true,
    }),
  });
}

async function createSkill(companyId, file) {
  const markdown = await fs.readFile(path.join(ROOT, file), "utf8");
  const slug = path.basename(path.dirname(file));
  const existing = await api(`/api/companies/${companyId}/skills`);
  const found = existing.find((skill) => skill.slug === slug || skill.name === slug);
  if (found) return found;
  return api(`/api/companies/${companyId}/skills`, {
    method: "POST",
    body: JSON.stringify({
      name: slug,
      slug,
      description: `Runtime duel support skill: ${slug}`,
      markdown,
    }),
  });
}

async function ensureCompany() {
  const companies = await api("/api/companies");
  let company = companies.find((entry) => entry.name === COMPANY_NAME && entry.status !== "archived");
  if (!company) {
    company = await api("/api/companies", {
      method: "POST",
      body: JSON.stringify({
        name: COMPANY_NAME,
        description: "Independent Paperclip company for same-goal generation comparison between Claude Code and native Kimi CLI.",
        budgetMonthlyCents: 0,
      }),
    });
  }
  if (company.requireBoardApprovalForNewAgents !== false) {
    company = await api(`/api/companies/${company.id}`, {
      method: "PATCH",
      body: JSON.stringify({ requireBoardApprovalForNewAgents: false }),
    });
  }
  return company;
}

async function ensureProject(companyId) {
  const projects = await api(`/api/companies/${companyId}/projects`);
  const existing = projects.find((entry) => entry.name === PROJECT_NAME);
  if (existing) return existing;
  return api(`/api/companies/${companyId}/projects`, {
    method: "POST",
    body: JSON.stringify({
      name: PROJECT_NAME,
      description: "One shared target, two local runtimes, common rubric and evidence ledger.",
      status: "planned",
      color: "#2563eb",
      workspace: {
        name: "runtime-duel-root",
        sourceType: "local_path",
        cwd: ROOT,
        isPrimary: true,
      },
      executionWorkspacePolicy: {
        enabled: true,
        defaultMode: "shared_workspace",
        allowIssueOverride: true,
      },
    }),
  });
}

async function ensureAgent(companyId, name, payload) {
  const agents = await api(`/api/companies/${companyId}/agents`);
  const existing = agents.find((entry) => entry.name === name);
  if (existing) return existing;
  return api(`/api/companies/${companyId}/agents`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function ensureIssue(companyId, title, payload) {
  const issues = await api(`/api/companies/${companyId}/issues?limit=200`);
  const existing = issues.find((entry) => entry.title === title);
  if (existing) return existing;
  return api(`/api/companies/${companyId}/issues`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

function sameGoalDescription(lane) {
  const outPath = lane === "claude"
    ? `${ROOT}/outputs/claude_code_demo.md`
    : `${ROOT}/outputs/kimi_demo.md`;
  return [
    "Run the shared Runtime Duel target now.",
    "",
    `Lane: ${lane === "claude" ? "Claude Code" : "Kimi"}`,
    `Output path: ${outPath}`,
    "",
    "You must read:",
    `- ${ROOT}/brief/shared_target_brief.md`,
    `- ${ROOT}/brief/rubric_100.yaml`,
    "",
    "Then produce the full Markdown artifact with all required sections, save it to the output path, and close this issue as done.",
    "",
    "Acceptance criteria:",
    "- Artifact file exists and is non-empty.",
    "- All required sections from the shared brief are present.",
    "- Evidence Ledger has local evidence entries.",
    "- Final Self-Score targets 95+ / 100 and explains point-level reasoning.",
    "- No secrets, fake external validation, fake metrics, or unverifiable claims.",
  ].join("\n");
}

async function main() {
  await fs.mkdir(path.join(ROOT, "outputs", "evidence"), { recursive: true });
  await fs.mkdir(path.join(ROOT, "workspaces", "claude"), { recursive: true });
  await fs.mkdir(path.join(ROOT, "workspaces", "kimi"), { recursive: true });

  const existingState = await maybeReadState();
  if (existingState?.companyId && existingState?.agents?.claude && existingState?.agents?.kimi) {
    console.log(JSON.stringify({ reused: true, ...existingState }, null, 2));
    return;
  }

  const adapter = await ensureAdapter();
  const company = await ensureCompany();

  const operatorSkill = await createSkill(company.id, "skills/runtime-duel-operator/SKILL.md");
  const rubricSkill = await createSkill(company.id, "skills/runtime-duel-rubric/SKILL.md");
  const desiredSkills = [operatorSkill.key, rubricSkill.key];

  const project = await ensureProject(company.id);

  const promptTemplate = [
    "Complete the scoped Paperclip issue now.",
    "Use the assigned issue, shared target brief, rubric, and your lane instructions.",
    "Do not stop at a plan. Produce the artifact, save it to the lane output path, and close out with evidence.",
    "",
    "Context JSON:",
    "{{context}}",
  ].join("\n");

  const claude = await ensureAgent(company.id, "Claude Code Content Lead", {
      name: "Claude Code Content Lead",
      role: "pm",
      title: "Claude Code CLI Runtime Lane",
      icon: "brain",
      capabilities: "Generate the shared boss-demo content pack using the local Claude Code CLI/client lane and report actual model/provider from run evidence.",
      desiredSkills,
      adapterType: "claude_local",
      adapterConfig: {
        command: "/home/yuanhaizhou/local/node/bin/claude",
        cwd: `${ROOT}/workspaces/claude`,
        instructionsFilePath: `${ROOT}/agents/claude-code-content-lead/AGENTS.md`,
        promptTemplate,
        dangerouslySkipPermissions: true,
        maxTurnsPerRun: 30,
        timeoutSec: 900,
        env: {
          HOME: "/home/yuanhaizhou",
          PATH: PATH_ENV,
          HCOM: "/vol1/1000/home-yuanhaizhou/_root_home/.local/bin/hcom",
        },
      },
      runtimeConfig: { heartbeat: { enabled: false, maxConcurrentRuns: 1 } },
      metadata: { runtimeAlias: "Claude Code", duelLane: "claude" },
  });

  const kimi = await ensureAgent(company.id, "Kimi Content Lead", {
      name: "Kimi Content Lead",
      role: "pm",
      title: "Native Kimi CLI Runtime Lane",
      icon: "sparkles",
      capabilities: "Generate the shared boss-demo content pack using native Kimi Code CLI.",
      desiredSkills,
      adapterType: "kimi_cli",
      adapterConfig: {
        command: "/home/yuanhaizhou/.local/bin/kimi-direct",
        configFile: "/home/yuanhaizhou/.kimi/config.toml",
        model: "kimi-for-coding",
        cwd: `${ROOT}/workspaces/kimi`,
        home: "/home/yuanhaizhou",
        pathEnv: PATH_ENV,
        instructionsFilePath: `${ROOT}/agents/kimi-content-lead/AGENTS.md`,
        promptTemplate,
        apiUrl: API,
        autoUpdateIssue: true,
        timeoutSec: 900,
      },
      runtimeConfig: { heartbeat: { enabled: false, maxConcurrentRuns: 1 } },
      metadata: { runtimeAlias: "Kimi", duelLane: "kimi" },
  });

  const claudeIssue = await ensureIssue(company.id, "RUNTIME-DUEL-CLAUDE - Generate the shared boss demo pack", {
      projectId: project.id,
      title: "RUNTIME-DUEL-CLAUDE - Generate the shared boss demo pack",
      description: sameGoalDescription("claude"),
      status: "backlog",
      priority: "critical",
      assigneeAgentId: claude.id,
  });

  const kimiIssue = await ensureIssue(company.id, "RUNTIME-DUEL-KIMI - Generate the shared boss demo pack", {
      projectId: project.id,
      title: "RUNTIME-DUEL-KIMI - Generate the shared boss demo pack",
      description: sameGoalDescription("kimi"),
      status: "backlog",
      priority: "critical",
      assigneeAgentId: kimi.id,
  });

  const state = {
    apiUrl: API,
    createdAt: new Date().toISOString(),
    adapter,
    companyId: company.id,
    companyName: company.name,
    projectId: project.id,
    skillKeys: desiredSkills,
    agents: {
      claude: claude.id,
      kimi: kimi.id,
    },
    issues: {
      claude: claudeIssue.id,
      kimi: kimiIssue.id,
    },
    outputPaths: {
      claude: `${ROOT}/outputs/claude_code_demo.md`,
      kimi: `${ROOT}/outputs/kimi_demo.md`,
    },
  };
  await writeState(state);
  console.log(JSON.stringify(state, null, 2));
}

main().catch((err) => {
  console.error(err.stack || err.message);
  process.exit(1);
});
