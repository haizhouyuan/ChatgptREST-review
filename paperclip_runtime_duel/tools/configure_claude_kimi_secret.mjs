#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";

const ROOT = "/vol1/1000/projects/toyresearch/paperclip_runtime_duel";
const STATE_PATH = path.join(ROOT, "state.json");
const SECRET_NAME = "kimi-codingplan-api-key";

const state = JSON.parse(await fs.readFile(STATE_PATH, "utf8"));
const API = state.apiUrl || process.env.PAPERCLIP_API_URL || "http://127.0.0.1:3100";
const companyId = state.companyId;
const agentId = state.agents?.claudeKimi;
const kimiCredential = process.env.KIMI_CODINGPLAN_API_KEY;

if (!companyId || !agentId) {
  throw new Error("state.json must contain companyId and agents.claudeKimi");
}
if (!kimiCredential || kimiCredential.trim().length < 12) {
  throw new Error("KIMI_CODINGPLAN_API_KEY is missing from the current shell environment");
}

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

const secrets = await api(`/api/companies/${companyId}/secrets`);
let secret = secrets.find((entry) => entry.name === SECRET_NAME);
if (secret) {
  secret = await api(`/api/secrets/${secret.id}/rotate`, {
    method: "POST",
    body: JSON.stringify({ value: kimiCredential }),
  });
} else {
  secret = await api(`/api/companies/${companyId}/secrets`, {
    method: "POST",
    body: JSON.stringify({
      name: SECRET_NAME,
      value: kimiCredential,
      description: "Kimi coding endpoint API key for the local claudekimi Paperclip lane.",
    }),
  });
}

const agents = await api(`/api/companies/${companyId}/agents`);
const agent = agents.find((entry) => entry.id === agentId);
if (!agent) throw new Error(`Agent not found: ${agentId}`);

const adapterConfig = agent.adapterConfig || {};
const env = {
  ...(adapterConfig.env || {}),
  KIMI_CODINGPLAN_API_KEY: {
    type: "secret_ref",
    secretId: secret.id,
    version: "latest",
  },
};

const updated = await api(`/api/agents/${agentId}`, {
  method: "PATCH",
  body: JSON.stringify({
    adapterConfig: { env },
  }),
});

console.log(JSON.stringify({
  companyId,
  agentId,
  secret: {
    id: secret.id,
    name: secret.name,
    provider: secret.provider,
    latestVersion: secret.latestVersion,
  },
  envKeys: Object.keys(updated.adapterConfig?.env || {}).sort(),
  note: "Secret value was written to Paperclip encrypted secret storage and was not printed.",
}, null, 2));
