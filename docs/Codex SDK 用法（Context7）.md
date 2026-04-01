# Codex SDK 用法（Context7）

本文件是用 Context7 MCP 从 `/websites/developers_openai_codex` 抽取/整理的 Codex SDK（TypeScript）与 Codex CLI 相关用法要点，便于在本项目中直接引用。

来源（Context7 索引）：
- https://github.com/context7/developers_openai_codex/blob/main/sdk.md
- https://github.com/context7/developers_openai_codex/blob/main/cli/reference.md
- https://github.com/context7/developers_openai_codex/blob/main/changelog.md

## 1) TypeScript SDK（`@openai/codex-sdk`）

### 1.1 运行环境与安装

- 运行环境：Node.js v18 或更高（server-side）
- 安装：

```bash
npm install @openai/codex-sdk
```

### 1.2 最小示例：启动线程并执行一次任务

```typescript
import { Codex } from "@openai/codex-sdk";

async function runCodexTask() {
  const codex = new Codex();
  const thread = codex.startThread();
  const result = await thread.run("Make a plan to diagnose and fix the CI failures");
  console.log(result);
}
```

### 1.3 多轮：在同一线程继续对话 / 通过 threadId 恢复线程

```typescript
import { Codex } from "@openai/codex-sdk";

async function manageCodexThreads() {
  const codex = new Codex();

  // Continuing the same thread
  const thread = codex.startThread(); // Assuming thread is already started and has a threadId
  const result = await thread.run("Implement the plan");
  console.log(result);

  // Resuming a past thread
  const threadId = "your_thread_id_here"; // Replace with an actual thread ID
  const thread2 = codex.resumeThread(threadId);
  const result2 = await thread2.run("Pick up where you left off");
  console.log(result2);
}
```

### 1.4 `modelReasoningEffort`（changelog 提到的配置项）

Context7 的 changelog 里提到了 TypeScript SDK 支持 `modelReasoningEffort`（示例为 0~1 的数值）：

```typescript
import { Configuration } from "@openai/codex-sdk";

const config: Configuration = {
  // ... other configurations
  modelReasoningEffort: 0.75 // Example value between 0 and 1
};
```

> 说明：该片段来自 changelog，具体如何把 `Configuration` 注入到 `Codex` / `startThread()`（例如构造参数/线程参数）请以你本机安装版本的 SDK 类型定义为准。

## 2) Codex CLI（作为 SDK 之外的可编程入口）

即使你最终在业务服务里主要用 TypeScript SDK，CLI 的 `codex exec` 仍然适合做一次性批处理、CI 任务、或“结构化落盘输出”的脚本化编排。

### 2.1 `codex exec` 的输出与事件流

Context7 文档说明：
- `codex exec` 运行时会把过程信息 stream 到 **stderr**，只把最终 agent message 输出到 **stdout**（方便管道处理）。
- `--json` 会让 stdout 变成 JSON Lines 事件流，包含 `thread.started`、`turn.started`、`turn.completed`、`turn.failed`、`item.*`、`error` 等事件类型。
- `-o` / `--output-last-message` 可把最终消息写入文件。

示例：

```bash
codex exec "generate release notes" | tee release-notes.md
codex exec --json "summarize the repo structure"
```

### 2.2 结构化输出（JSON Schema）

用 `--output-schema` 让 `codex exec` 输出符合 JSON Schema 的结构化 JSON，并用 `-o` 直接落盘：

```bash
codex exec "Extract project metadata" \
  --output-schema ./schema.json \
  -o ./project-metadata.json
```

## 3) 认证（login / 覆盖单次 exec）

### 3.1 `codex login`（交互式 or API key）

Context7 文档说明：`codex login` 默认会打开浏览器走 ChatGPT OAuth；也支持从 stdin 读取 API key 的非交互方式：

```bash
codex login
printenv OPENAI_API_KEY | codex login --with-api-key
codex login status
```

### 3.2 `CODEX_API_KEY`（仅用于单次 `codex exec` 覆盖认证）

`codex exec` 默认复用 CLI 的登录态；如果你要对单次运行覆盖认证，可设置 `CODEX_API_KEY`（Context7 文档强调：仅支持 `codex exec`）：

```bash
CODEX_API_KEY=your-api-key codex exec --json "triage open bug reports"
```

