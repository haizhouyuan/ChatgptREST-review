import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const SCRIPT_PATH = fileURLToPath(import.meta.url);

type Args = {
  openclawRoot: string;
  configPath: string;
  accountId: string;
  senderOpenId: string;
  senderUserId: string;
  chatId: string;
  message: string;
  messageId: string;
  outputPath: string;
  worker: boolean;
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

  const homeConfig = path.join(os.homedir(), ".home-codex-official", ".openclaw", "openclaw.json");
  const messageId =
    values.get("--message-id") ||
    `om_proxy_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  return {
    openclawRoot: path.resolve(values.get("--openclaw-root") || process.env.OPENCLAW_ROOT || "/vol1/1000/projects/openclaw"),
    configPath: path.resolve(values.get("--config") || process.env.OPENCLAW_CONFIG || homeConfig),
    accountId: values.get("--account-id") || "default",
    senderOpenId: values.get("--sender-open-id") || "",
    senderUserId: values.get("--sender-user-id") || "",
    chatId: values.get("--chat-id") || "",
    message,
    messageId,
    outputPath: path.resolve(outputPath),
    worker: values.has("--worker"),
  };
}

function writeJson(outputPath: string, payload: Record<string, unknown>): void {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify(payload, null, 2), "utf8");
}

async function runWorker(args: Args): Promise<Record<string, unknown>> {
  const result: Record<string, unknown> = {
    ok: false,
    started_at: new Date().toISOString(),
    account_id: args.accountId,
    sender_open_id: args.senderOpenId,
    sender_user_id: args.senderUserId,
    chat_id: args.chatId,
    config_path: args.configPath,
    openclaw_root: args.openclawRoot,
    message_excerpt: args.message.replace(/\s+/g, " ").trim().slice(0, 160),
    synthetic_message_id: args.messageId,
    mode: "worker",
  };

  try {
    process.env.OPENCLAW_CONFIG_PATH = args.configPath;
    process.env.OPENCLAW_CONFIG = args.configPath;
    process.env.OPENCLAW_ROOT = args.openclawRoot;
    const configRaw = fs.readFileSync(args.configPath, "utf8");
    const cfg = JSON.parse(configRaw);
    const pluginRuntimePath = pathToFileURL(path.join(args.openclawRoot, "src", "plugins", "runtime", "index.ts")).href;
    const feishuRuntimePath = pathToFileURL(path.join(args.openclawRoot, "extensions", "feishu", "src", "runtime.ts")).href;
    const botPath = pathToFileURL(path.join(args.openclawRoot, "extensions", "feishu", "src", "bot.ts")).href;

    const { createPluginRuntime } = await import(pluginRuntimePath);
    const { setFeishuRuntime } = await import(feishuRuntimePath);
    const { handleFeishuMessage } = await import(botPath);

    const runtime = createPluginRuntime();
    setFeishuRuntime(runtime);

    const event = {
      sender: {
        sender_id: {
          open_id: args.senderOpenId,
          user_id: args.senderUserId,
        },
      },
      message: {
        message_id: args.messageId,
        chat_id: args.chatId,
        chat_type: "p2p",
        message_type: "text",
        content: JSON.stringify({ text: args.message }),
      },
    };

    await handleFeishuMessage({
      cfg,
      event,
      accountId: args.accountId,
      runtime: {
        log: (...items: unknown[]) => {
          process.stderr.write(`${items.map((item) => String(item)).join(" ")}\n`);
        },
        error: (...items: unknown[]) => {
          process.stderr.write(`${items.map((item) => String(item)).join(" ")}\n`);
        },
      },
    });
    result["ok"] = true;
    result["completed_at"] = new Date().toISOString();
  } catch (error) {
    result["ok"] = false;
    result["completed_at"] = new Date().toISOString();
    result["error"] = error instanceof Error ? { message: error.message, stack: error.stack || "" } : { message: String(error) };
  }
  return result;
}

function buildWorkerArgs(args: Args): string[] {
  const out: string[] = [
    path.resolve(SCRIPT_PATH),
    "--worker",
    "--openclaw-root",
    args.openclawRoot,
    "--config",
    args.configPath,
    "--account-id",
    args.accountId,
    "--sender-open-id",
    args.senderOpenId,
    "--sender-user-id",
    args.senderUserId,
    "--chat-id",
    args.chatId,
    "--message-id",
    args.messageId,
    "--message",
    args.message,
    "--output",
    args.outputPath,
  ];
  return out;
}

function resolveTsxCommand(openclawRoot: string): { command: string; args: string[] } {
  const localTsx = path.join(openclawRoot, "node_modules", ".bin", "tsx");
  if (fs.existsSync(localTsx)) {
    return { command: localTsx, args: [] };
  }
  return { command: "npx", args: ["--yes", "tsx"] };
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  if (!args.senderOpenId) {
    throw new Error("--sender-open-id is required");
  }
  if (!args.chatId) {
    throw new Error("--chat-id is required");
  }

  if (args.worker) {
    const result = await runWorker(args);
    writeJson(args.outputPath, result);
    return;
  }

  writeJson(args.outputPath, {
    ok: true,
    started_at: new Date().toISOString(),
    account_id: args.accountId,
    sender_open_id: args.senderOpenId,
    sender_user_id: args.senderUserId,
    chat_id: args.chatId,
    config_path: args.configPath,
    openclaw_root: args.openclawRoot,
    message_excerpt: args.message.replace(/\s+/g, " ").trim().slice(0, 160),
    synthetic_message_id: args.messageId,
    mode: "background_dispatch_initializing",
  });

  const workerStdoutPath = `${args.outputPath}.worker.stdout.log`;
  const workerStderrPath = `${args.outputPath}.worker.stderr.log`;
  const stdoutFd = fs.openSync(workerStdoutPath, "a");
  const stderrFd = fs.openSync(workerStderrPath, "a");
  const tsx = resolveTsxCommand(args.openclawRoot);
  const child = spawn(
    tsx.command,
    [...tsx.args, ...buildWorkerArgs(args)],
    {
      cwd: args.openclawRoot,
      detached: true,
      stdio: ["ignore", stdoutFd, stderrFd],
      env: process.env,
    },
  );
  child.unref();
  fs.closeSync(stdoutFd);
  fs.closeSync(stderrFd);

  writeJson(args.outputPath, {
    ok: true,
    started_at: new Date().toISOString(),
    account_id: args.accountId,
    sender_open_id: args.senderOpenId,
    sender_user_id: args.senderUserId,
    chat_id: args.chatId,
    config_path: args.configPath,
    openclaw_root: args.openclawRoot,
    message_excerpt: args.message.replace(/\s+/g, " ").trim().slice(0, 160),
    synthetic_message_id: args.messageId,
    mode: "background_dispatch",
    worker_pid: child.pid,
    worker_stdout_path: workerStdoutPath,
    worker_stderr_path: workerStderrPath,
  });
}

main().catch((error) => {
  const message = error instanceof Error ? error.stack || error.message : String(error);
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
});
