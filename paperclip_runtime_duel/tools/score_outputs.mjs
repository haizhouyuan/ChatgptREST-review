#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";

const ROOT = "/vol1/1000/projects/toyresearch/paperclip_runtime_duel";
const outputs = {
  claude: path.join(ROOT, "outputs", "claude_code_demo.md"),
  kimi: path.join(ROOT, "outputs", "kimi_demo.md"),
};
const requiredSections = [
  "# Executive Demo Narrative",
  "## What The Boss Should See In 90 Seconds",
  "## Control Plane Architecture",
  "## Same-Goal Generation Plan",
  "## The Premium Labebe Demo Concept",
  "## Visual And Interaction Direction",
  "## Agent Organization And Workflow",
  "## Governance, MCP, Skills, And Secrets Policy",
  "## Acceptance Criteria",
  "## Evidence Ledger",
  "## Risks And Open Decisions",
  "## Final Self-Score",
];

function sha256(text) {
  return crypto.createHash("sha256").update(text).digest("hex");
}

function scoreText(text) {
  const missingSections = requiredSections.filter((section) => !text.includes(section));
  const evidenceHits = (text.match(/\/vol1\/1000\/projects\/toyresearch\/[^\s)`]+/g) || []).length;
  const factLabels = (text.match(/\bFact\b/g) || []).length;
  const inferenceLabels = (text.match(/\bInference\b/g) || []).length;
  const hypothesisLabels = (text.match(/\bHypothesis\b/g) || []).length;
  const finalSection = text.split(/^## Final Self-Score\s*$/im)[1] || "";
  const selfScoreMatch =
    finalSection.match(/(?:Total|Score|Self-Score|self-score)\D{0,40}(\d{2,3})\s*\/\s*100/i) ||
    text.match(/(?:Self-Score|self-score|score)\D{0,20}(\d{2,3})\s*\/\s*100/i);
  const selfScore = selfScoreMatch ? Number(selfScoreMatch[1]) : null;
  let score = 100;
  score -= missingSections.length * 8;
  if (text.length < 7000) score -= 10;
  if (evidenceHits < 5) score -= (5 - evidenceHits) * 3;
  if (factLabels + inferenceLabels + hypothesisLabels < 8) score -= 8;
  if (selfScore == null) score -= 8;
  if (!/90[- ]second|90 seconds|90秒/i.test(text)) score -= 5;
  if (!/MCP|secret|secrets|approval|heartbeat|issue/i.test(text)) score -= 10;
  score = Math.max(0, Math.min(100, score));
  return {
    score,
    selfScore,
    missingSections,
    evidenceHits,
    labelCounts: { Fact: factLabels, Inference: inferenceLabels, Hypothesis: hypothesisLabels },
    chars: text.length,
    sha256: sha256(text),
  };
}

const result = { scoredAt: new Date().toISOString(), lanes: {} };
for (const [lane, file] of Object.entries(outputs)) {
  const text = await fs.readFile(file, "utf8");
  result.lanes[lane] = { file, ...scoreText(text) };
}

result.comparison = {
  winnerByDeterministicRubric:
    result.lanes.claude.score === result.lanes.kimi.score
      ? "tie"
      : (result.lanes.claude.score > result.lanes.kimi.score ? "claude" : "kimi"),
  note: "This deterministic score checks structure, traceability, and policy hygiene. Human/Pro review is still needed for taste and true wow factor.",
};

const outPath = path.join(ROOT, "outputs", "evidence", "scorecard.json");
await fs.writeFile(outPath, `${JSON.stringify(result, null, 2)}\n`);
console.log(JSON.stringify(result, null, 2));
