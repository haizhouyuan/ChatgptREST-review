import { Type } from "@sinclair/typebox";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk";

type EndpointConfig = {
  baseUrl: string;
  apiKey?: string;
  timeoutMs: number;
};

type GraphConfig = {
  endpoint: EndpointConfig;
  defaultRepo: string;
  defaultScopes: string[];
};

function readConfig(api: OpenClawPluginApi): GraphConfig {
  const raw = (api.pluginConfig ?? {}) as Record<string, unknown>;
  const endpoint = ((raw.endpoint as Record<string, unknown> | undefined) ?? {});
  const envApiKey = String(process.env.OPENMIND_API_KEY ?? "").trim() || undefined;
  const baseUrl = String(endpoint.baseUrl ?? "http://127.0.0.1:18711").trim().replace(/\/+$/, "");
  const defaultScopes = Array.isArray(raw.defaultScopes)
    ? raw.defaultScopes.filter((value): value is string => typeof value === "string" && !!value.trim())
    : ["personal_graph"];
  return {
    endpoint: {
      baseUrl,
      apiKey: String(endpoint.apiKey ?? "").trim() || envApiKey,
      timeoutMs: Math.max(1000, Math.min(Number(endpoint.timeoutMs ?? 120000), 300000)),
    },
    defaultRepo: String(raw.defaultRepo ?? "").trim(),
    defaultScopes,
  };
}

async function requestJson(
  cfg: EndpointConfig,
  path: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), cfg.timeoutMs);
  try {
    const response = await fetch(`${cfg.baseUrl}${path}`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...(cfg.apiKey ? { "x-api-key": cfg.apiKey } : {}),
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    const text = await response.text();
    const payload = JSON.parse(text) as Record<string, unknown>;
    if (!response.ok) {
      throw new Error(`OpenMind graph request failed (${response.status}): ${text.slice(0, 1000)}`);
    }
    return payload;
  } finally {
    clearTimeout(timer);
  }
}

const graphPlugin = {
  id: "openmind-graph",
  name: "OpenMind Graph",
  description: "Expose OpenMind graph query results to OpenClaw tools.",

  register(api: OpenClawPluginApi) {
    const cfg = readConfig(api);

    api.registerTool(
      {
        name: "openmind_graph_query",
        label: "OpenMind Graph Query",
        description:
          "Query personal_graph and repo_graph through OpenMind's graph fabric.",
        parameters: Type.Object({
          query: Type.String({ description: "Graph query." }),
          scopes: Type.Optional(Type.Array(Type.String())),
          repo: Type.Optional(Type.String()),
          limit: Type.Optional(Type.Number({ minimum: 1, maximum: 50 })),
          includeEdges: Type.Optional(Type.Boolean()),
          includePaths: Type.Optional(Type.Boolean()),
        }),
        async execute(_toolCallId, params) {
          const query = String((params as Record<string, unknown>).query ?? "").trim();
          if (!query) {
            return {
              content: [{ type: "text", text: "query required" }],
              details: { ok: false, error: "query required" },
            };
          }
          const payload = await requestJson(cfg.endpoint, "/v2/graph/query", {
            query,
            scopes: Array.isArray((params as Record<string, unknown>).scopes)
              ? (params as Record<string, unknown>).scopes
              : cfg.defaultScopes,
            repo: String((params as Record<string, unknown>).repo ?? cfg.defaultRepo).trim(),
            limit: Number((params as Record<string, unknown>).limit ?? 10),
            include_edges: Boolean((params as Record<string, unknown>).includeEdges ?? true),
            include_paths: Boolean((params as Record<string, unknown>).includePaths ?? true),
          });
          const nodes = Array.isArray(payload.nodes) ? payload.nodes.length : 0;
          const evidence = Array.isArray(payload.evidence) ? payload.evidence.length : 0;
          return {
            content: [
              {
                type: "text",
                text: `Graph query returned ${nodes} nodes and ${evidence} evidence items.\n\n${JSON.stringify(payload, null, 2)}`,
              },
            ],
            details: payload,
          };
        },
      },
      { name: "openmind_graph_query" },
    );

    api.registerService({
      id: "openmind-graph",
      start: () => {
        api.logger.info(`openmind-graph: ready (${cfg.endpoint.baseUrl})`);
      },
      stop: () => {
        api.logger.info("openmind-graph: stopped");
      },
    });
  },
};

export default graphPlugin;
