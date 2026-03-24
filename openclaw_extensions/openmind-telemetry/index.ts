import { createHash, randomUUID } from "node:crypto";
import { Type } from "@sinclair/typebox";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk";

type EndpointConfig = {
  baseUrl: string;
  apiKey?: string;
  timeoutMs: number;
};

type TelemetryConfig = {
  endpoint: EndpointConfig;
  enabled: boolean;
  batchSize: number;
  flushIntervalMs: number;
  ignoreOwnTools: boolean;
  defaultRoleId: string;
  repoName: string;
  repoPath: string;
  taskRefPrefix: string;
  defaultProvider: string;
  defaultModel: string;
  executorKind: string;
};

type TelemetryEvent = {
  type: string;
  source: string;
  domain: string;
  sessionKey?: string;
  eventId?: string;
  runId?: string;
  taskRef?: string;
  repoName?: string;
  repoPath?: string;
  agentName?: string;
  agentSource?: string;
  provider?: string;
  model?: string;
  data: Record<string, unknown>;
};

type RunContext = {
  runId: string;
  taskRef: string;
  roleId: string;
  toolSeq: number;
};

function readConfig(api: OpenClawPluginApi): TelemetryConfig {
  const raw = (api.pluginConfig ?? {}) as Record<string, unknown>;
  const endpoint = ((raw.endpoint as Record<string, unknown> | undefined) ?? {});
  const envApiKey = String(process.env.OPENMIND_API_KEY ?? "").trim() || undefined;
  return {
    endpoint: {
      baseUrl: String(endpoint.baseUrl ?? "http://127.0.0.1:18711").trim().replace(/\/+$/, ""),
      apiKey: String(endpoint.apiKey ?? "").trim() || envApiKey,
      timeoutMs: Math.max(1000, Math.min(Number(endpoint.timeoutMs ?? 120000), 300000)),
    },
    enabled: raw.enabled !== false,
    batchSize: Math.max(1, Math.min(Number(raw.batchSize ?? 10), 100)),
    flushIntervalMs: Math.max(1000, Math.min(Number(raw.flushIntervalMs ?? 15000), 600000)),
    ignoreOwnTools: raw.ignoreOwnTools !== false,
    defaultRoleId: String(raw.defaultRoleId ?? "").trim(),
    repoName: String(raw.repoName ?? "ChatgptREST").trim(),
    repoPath: String(raw.repoPath ?? "").trim(),
    taskRefPrefix: String(raw.taskRefPrefix ?? "openclaw").trim() || "openclaw",
    defaultProvider: String(raw.defaultProvider ?? "").trim(),
    defaultModel: String(raw.defaultModel ?? "").trim(),
    executorKind: String(raw.executorKind ?? "openclaw.agent").trim() || "openclaw.agent",
  };
}

function hashKey(parts: string[]): string {
  return createHash("sha1").update(parts.join("::"), "utf8").digest("hex");
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
      throw new Error(`OpenMind telemetry request failed (${response.status}): ${text.slice(0, 1000)}`);
    }
    return payload;
  } finally {
    clearTimeout(timer);
  }
}

class TelemetryQueue {
  private readonly cfg: TelemetryConfig;
  private readonly logger: OpenClawPluginApi["logger"];
  private readonly events: TelemetryEvent[] = [];
  private flushTimer: ReturnType<typeof setInterval> | null = null;

  constructor(cfg: TelemetryConfig, logger: OpenClawPluginApi["logger"]) {
    this.cfg = cfg;
    this.logger = logger;
  }

  start(): void {
    if (!this.cfg.enabled || this.flushTimer) {
      return;
    }
    this.flushTimer = setInterval(() => {
      void this.flush();
    }, this.cfg.flushIntervalMs);
  }

  stop(): Promise<void> {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }
    return this.flush();
  }

  enqueue(event: TelemetryEvent): void {
    if (!this.cfg.enabled) {
      return;
    }
    this.events.push(event);
    if (this.events.length >= this.cfg.batchSize) {
      void this.flush();
    }
  }

  pendingCount(): number {
    return this.events.length;
  }

  async flush(): Promise<void> {
    if (!this.cfg.enabled || this.events.length === 0) {
      return;
    }
    const batch = this.events.splice(0, this.cfg.batchSize);
    const grouped = new Map<string, TelemetryEvent[]>();
    for (const event of batch) {
      const key = event.sessionKey ?? "";
      const items = grouped.get(key) ?? [];
      items.push(event);
      grouped.set(key, items);
    }

    for (const [sessionKey, items] of grouped.entries()) {
      try {
        await requestJson(this.cfg.endpoint, "/v2/telemetry/ingest", {
          session_key: sessionKey,
          events: items.map((item) => ({
            type: item.type,
            source: item.source,
            domain: item.domain,
            event_id: item.eventId,
            run_id: item.runId,
            task_ref: item.taskRef,
            repo_name: item.repoName,
            repo_path: item.repoPath,
            agent_name: item.agentName,
            agent_source: item.agentSource,
            provider: item.provider,
            model: item.model,
            data: item.data,
          })),
        });
      } catch (error) {
        this.logger.warn(`openmind-telemetry: flush failed: ${String(error)}`);
        this.events.unshift(...items);
        break;
      }
    }
  }
}

const telemetryPlugin = {
  id: "openmind-telemetry",
  name: "OpenMind Telemetry",
  description: "Feed OpenClaw execution outcomes into OpenMind EvoMap.",

  register(api: OpenClawPluginApi) {
    const cfg = readConfig(api);
    const queue = new TelemetryQueue(cfg, api.logger);
    const runs = new Map<string, RunContext>();

    function transportSessionKey(ctx: { sessionKey?: string; sessionId?: string; agentId?: string } | undefined): string {
      return String(ctx?.sessionId ?? ctx?.sessionKey ?? ctx?.agentId ?? "unknown").trim() || "unknown";
    }

    function stableSessionKey(ctx: { sessionKey?: string; sessionId?: string; agentId?: string } | undefined): string {
      return String(ctx?.sessionKey ?? ctx?.sessionId ?? ctx?.agentId ?? "unknown").trim() || "unknown";
    }

    function ensureRunContext(ctx: { sessionKey?: string; sessionId?: string; agentId?: string } | undefined): RunContext {
      const sessionKey = transportSessionKey(ctx);
      const existing = runs.get(sessionKey);
      if (existing) {
        return existing;
      }
      const agentId = String(ctx?.agentId ?? "unknown").trim() || "unknown";
      const created: RunContext = {
        runId: randomUUID().replace(/-/g, ""),
        taskRef: `${cfg.taskRefPrefix}:${agentId}:${hashKey([sessionKey])}`,
        roleId: cfg.defaultRoleId,
        toolSeq: 0,
      };
      runs.set(sessionKey, created);
      return created;
    }

    function agentName(ctx: { agentId?: string } | undefined): string {
      return String(ctx?.agentId ?? "unknown").trim() || "unknown";
    }

    api.registerTool(
      {
        name: "openmind_telemetry_flush",
        label: "OpenMind Telemetry Flush",
        description: "Flush queued execution telemetry into OpenMind.",
        parameters: Type.Object({}),
        async execute() {
          await queue.flush();
          const details = { ok: true, pending: queue.pendingCount() };
          return {
            content: [{ type: "text", text: JSON.stringify(details, null, 2) }],
            details,
          };
        },
      },
      { name: "openmind_telemetry_flush" },
    );

    api.on("before_agent_start", async (_event, ctx) => {
      const run = ensureRunContext(ctx);
      const sessionKey = transportSessionKey(ctx);
      queue.enqueue({
        type: "team.run.created",
        source: "openclaw",
        domain: "execution",
        sessionKey,
        eventId: `${run.runId}:created`,
        runId: run.runId,
        taskRef: run.taskRef,
        repoName: cfg.repoName,
        repoPath: cfg.repoPath,
        agentName: agentName(ctx),
        agentSource: "openclaw",
        provider: cfg.defaultProvider,
        model: cfg.defaultModel,
        data: {
          session_id: sessionKey,
          session_key: stableSessionKey(ctx),
          agent_id: agentName(ctx),
          role_id: run.roleId,
          executor_kind: cfg.executorKind,
        },
      });
    });

    api.on("after_tool_call", async (event, ctx) => {
      if (cfg.ignoreOwnTools && String(event.toolName).startsWith("openmind_")) {
        return;
      }
      const run = ensureRunContext(ctx);
      const sessionKey = transportSessionKey(ctx);
      run.toolSeq += 1;
      queue.enqueue({
        type: event.error ? "tool.failed" : "tool.completed",
        source: "openclaw",
        domain: "execution",
        sessionKey,
        eventId: `${run.runId}:tool:${run.toolSeq}`,
        runId: run.runId,
        taskRef: run.taskRef,
        repoName: cfg.repoName,
        repoPath: cfg.repoPath,
        agentName: agentName(ctx),
        agentSource: "openclaw",
        provider: cfg.defaultProvider,
        model: cfg.defaultModel,
        data: {
          session_id: sessionKey,
          session_key: stableSessionKey(ctx),
          agent_id: agentName(ctx),
          role_id: run.roleId,
          executor_kind: cfg.executorKind,
          tool: event.toolName,
          duration_ms: event.durationMs ?? null,
          error: event.error ?? null,
        },
      });
    });

    api.on("agent_end", async (event, ctx) => {
      const run = ensureRunContext(ctx);
      const sessionKey = transportSessionKey(ctx);
      queue.enqueue({
        type: event.success ? "workflow.completed" : "workflow.failed",
        source: "openclaw",
        domain: "execution",
        sessionKey,
        eventId: event.success ? `${run.runId}:completed` : `${run.runId}:failed`,
        runId: run.runId,
        taskRef: run.taskRef,
        repoName: cfg.repoName,
        repoPath: cfg.repoPath,
        agentName: agentName(ctx),
        agentSource: "openclaw",
        provider: cfg.defaultProvider,
        model: cfg.defaultModel,
        data: {
          session_id: sessionKey,
          session_key: stableSessionKey(ctx),
          agent_id: agentName(ctx),
          role_id: run.roleId,
          executor_kind: cfg.executorKind,
          duration_ms: event.durationMs ?? null,
          message_count: Array.isArray(event.messages) ? event.messages.length : 0,
          error: event.error ?? null,
        },
      });
      runs.delete(sessionKey);
    });

    api.on("message_sent", async (event, ctx) => {
      if (event.success) {
        return;
      }
      const run = ensureRunContext(ctx);
      const sessionKey = transportSessionKey(ctx);
      run.toolSeq += 1;
      queue.enqueue({
        type: "delivery.failed",
        source: "openclaw",
        domain: "delivery",
        sessionKey,
        eventId: `${run.runId}:delivery:${run.toolSeq}`,
        runId: run.runId,
        taskRef: run.taskRef,
        repoName: cfg.repoName,
        repoPath: cfg.repoPath,
        agentName: agentName(ctx),
        agentSource: "openclaw",
        provider: cfg.defaultProvider,
        model: cfg.defaultModel,
        data: {
          session_id: sessionKey,
          session_key: stableSessionKey(ctx),
          agent_id: agentName(ctx),
          role_id: run.roleId,
          executor_kind: cfg.executorKind,
          to: event.to,
          error: event.error ?? null,
        },
      });
    });

    api.registerService({
      id: "openmind-telemetry",
      start: () => {
        queue.start();
        api.logger.info(`openmind-telemetry: ready (${cfg.endpoint.baseUrl})`);
      },
      stop: async () => {
        runs.clear();
        await queue.stop();
        api.logger.info("openmind-telemetry: stopped");
      },
    });
  },
};

export default telemetryPlugin;
