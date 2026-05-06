import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { callGateway } from "/vol1/1000/projects/openclaw/src/gateway/call.ts";
import { buildAgentPeerSessionKey } from "/vol1/1000/projects/openclaw/src/routing/session-key.ts";

type Args = {
  openclawRoot: string;
  configPath: string;
  accountId: string;
  senderOpenId: string;
  message: string;
  outputPath: string;
  agentId: string;
  timeoutSeconds: number;
  deliver: boolean;
};

function parseArgs(argv: string[]): Args {
  const values = new Map<string, string>();
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) {
      continue;
    }
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      values.set(token, "");
      continue;
    }
    values.set(token, next);
    index += 1;
  }

  const outputPath = values.get("--output");
  if (!outputPath) {
    throw new Error("--output is required");
  }
  const messageFile = values.get("--message-file");
  const inlineMessage = values.get("--message") || "";
  const message = messageFile ? fs.readFileSync(path.resolve(messageFile), "utf8") : inlineMessage;
  if (!String(message || "").trim()) {
    throw new Error("message is required via --message or --message-file");
  }
  const senderOpenId = values.get("--sender-open-id") || "";
  if (!senderOpenId) {
    throw new Error("--sender-open-id is required");
  }
  return {
    openclawRoot: path.resolve(values.get("--openclaw-root") || "/vol1/1000/projects/openclaw"),
    configPath: path.resolve(
      values.get("--config") || path.join(process.env.HOME || "", ".home-codex-official", ".openclaw", "openclaw.json"),
    ),
    accountId: values.get("--account-id") || "default",
    senderOpenId,
    message,
    outputPath: path.resolve(outputPath),
    agentId: values.get("--agent-id") || "feishu-intake",
    timeoutSeconds: Math.max(30, Number.parseInt(values.get("--timeout-seconds") || "600", 10) || 600),
    deliver: (values.get("--deliver") || "true").toLowerCase() !== "false",
  };
}

function writeJson(outputPath: string, payload: Record<string, unknown>): void {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify(payload, null, 2), "utf8");
}

function buildExplicitGatewayRuntime(configPath: string): { config: Record<string, unknown>; url: string; token?: string } {
  const raw = JSON.parse(fs.readFileSync(configPath, "utf8")) as Record<string, unknown>;
  const gateway = ((raw.gateway as Record<string, unknown> | undefined) || {}) as Record<string, unknown>;
  const auth = ((gateway.auth as Record<string, unknown> | undefined) || {}) as Record<string, unknown>;
  const port = Number.parseInt(String(gateway.port ?? "18789"), 10) || 18789;
  const tlsEnabled = gateway.tls && typeof gateway.tls === "object" && (gateway.tls as Record<string, unknown>).enabled === true;
  const scheme = tlsEnabled ? "wss" : "ws";
  const url = `${scheme}://127.0.0.1:${port}`;
  return {
    config: {
      gateway: {
        port,
        mode: String(gateway.mode || "local"),
        bind: String(gateway.bind || "loopback"),
        auth: {
          mode: String(auth.mode || "token"),
          ...(typeof auth.token === "string" && auth.token.trim() ? { token: auth.token.trim() } : {}),
          ...(typeof auth.password === "string" && auth.password.trim() ? { password: auth.password.trim() } : {}),
        },
      },
    },
    url,
    token: typeof auth.token === "string" && auth.token.trim() ? auth.token.trim() : undefined,
  };
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  process.env.OPENCLAW_ROOT = args.openclawRoot;
  const gatewayRuntime = buildExplicitGatewayRuntime(args.configPath);

  const sessionKey = buildAgentPeerSessionKey({
    agentId: args.agentId,
    channel: "feishu",
    accountId: args.accountId,
    peerKind: "direct",
    peerId: args.senderOpenId,
    dmScope: "per-account-channel-peer",
  });

  const payload: Record<string, unknown> = {
    message: args.message,
    agentId: args.agentId,
    sessionKey,
    channel: "feishu",
    replyChannel: "feishu",
    replyAccountId: args.accountId,
    replyTo: args.senderOpenId,
    deliver: args.deliver,
    timeout: args.timeoutSeconds,
    idempotencyKey: `codex-feishu-gateway-${randomUUID()}`,
  };

  const startedAt = new Date().toISOString();
  try {
    const response = await callGateway({
      config: gatewayRuntime.config as never,
      url: gatewayRuntime.url,
      token: gatewayRuntime.token,
      configPath: args.configPath,
      method: "agent",
      params: payload,
      expectFinal: true,
      timeoutMs: (args.timeoutSeconds + 60) * 1000,
    });
    writeJson(args.outputPath, {
      ok: true,
      started_at: startedAt,
      completed_at: new Date().toISOString(),
      session_key: sessionKey,
      request: payload,
      response,
    });
  } catch (error) {
    writeJson(args.outputPath, {
      ok: false,
      started_at: startedAt,
      completed_at: new Date().toISOString(),
      session_key: sessionKey,
      request: payload,
      error:
        error instanceof Error
          ? { message: error.message, stack: error.stack || "" }
          : { message: String(error) },
    });
    throw error;
  }
}

main().catch((error) => {
  const message = error instanceof Error ? error.stack || error.message : String(error);
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
});
