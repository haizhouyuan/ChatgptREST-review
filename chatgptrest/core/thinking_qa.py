"""Thinking-trace quality assessment.

Provides helpers to evaluate response quality based on the model's captured
thinking process alongside the final answer.  Used by the worker after a job
completes to produce structured QA records for debug/evomap consumption.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ThinkingQAResult:
    """Structured quality assessment of a model response."""

    score: float = 0.0  # 0.0‒1.0
    flags: dict[str, bool] = field(default_factory=lambda: {
        "intent_mismatch": False,
        "truncation_detected": False,
        "upload_incomplete": False,
        "hallucination_risk": False,
        "reasoning_gaps": False,
    })
    summary: str = ""
    assessed_by: str = ""
    assessed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_assessment_prompt(
    *,
    question: str,
    answer: str,
    thinking_trace: dict[str, Any] | None,
    thinking_metadata: dict[str, Any] | None = None,
) -> str:
    """Build a prompt for Codex to assess response quality.

    The prompt instructs the assessor to evaluate intent comprehension,
    upload/context completeness, reasoning quality, and answer relevance.
    """
    thinking_summary = ""
    if thinking_trace:
        steps = thinking_trace.get("steps") or []
        provider = thinking_trace.get("provider", "unknown")
        total_chars = thinking_trace.get("total_content_chars", 0)
        thinking_summary = (
            f"Provider: {provider}\n"
            f"Total thinking steps: {len(steps)}\n"
            f"Total thinking chars: {total_chars}\n"
        )
        for i, step in enumerate(steps):
            label = step.get("label", "")
            content = step.get("content", "")
            thinking_summary += f"\n--- Step {i + 1}: {label} ---\n"
            if content:
                # Truncate very long step content for the assessment prompt
                if len(content) > 4000:
                    thinking_summary += content[:4000] + "\n... [truncated]\n"
                else:
                    thinking_summary += content + "\n"
            else:
                thinking_summary += "[no content captured]\n"

    metadata_section = ""
    if thinking_metadata:
        metadata_section = f"\n## Metadata\n```json\n{json.dumps(thinking_metadata, indent=2, default=str)}\n```\n"

    return f"""# Response Quality Assessment

You are evaluating the quality of an AI model's response. Analyze the thinking
process alongside the final answer to identify any issues.

## User Question
```
{question[:8000]}
```

## Thinking Process
{thinking_summary if thinking_summary else "[No thinking trace captured]"}
{metadata_section}
## Final Answer
```
{answer[:12000]}
```

## Assessment Instructions

Evaluate the response on these dimensions and return a **JSON object** (no markdown fences):

1. **intent_mismatch** (bool): Did the model misunderstand the user's question?
2. **truncation_detected** (bool): Are there signs the model's input was truncated?
   Look for: incomplete file reads, missing context acknowledgments, or the model
   saying it can only see part of the input.
3. **upload_incomplete** (bool): If files were uploaded, did the model fail to
   read them completely? Look for mentions of partial reads or missing sections.
4. **hallucination_risk** (bool): Does the answer contain information that appears
   fabricated or unsupported by the thinking process?
5. **reasoning_gaps** (bool): Are there logical jumps in the thinking that skip
   important considerations?
6. **score** (float 0.0-1.0): Overall quality score.
   - 0.9-1.0: Excellent — accurate, complete, well-reasoned
   - 0.7-0.89: Good — minor issues but largely correct
   - 0.5-0.69: Acceptable — some important gaps or issues
   - 0.3-0.49: Poor — significant problems
   - 0.0-0.29: Failed — major misunderstanding or hallucination
7. **summary** (str): 1-2 sentence summary of the assessment.

Return ONLY a JSON object like:
{{"score": 0.85, "intent_mismatch": false, "truncation_detected": true, "upload_incomplete": false, "hallucination_risk": false, "reasoning_gaps": false, "summary": "..."}}
"""


def parse_assessment_response(raw_text: str) -> ThinkingQAResult:
    """Parse a Codex/model assessment response into a ThinkingQAResult."""
    result = ThinkingQAResult(assessed_at=time.time())

    # Try to find JSON in the response
    text = (raw_text or "").strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        import re
        match = re.search(r'\{[^{}]*"score"[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                result.summary = f"Failed to parse assessment: {text[:200]}"
                return result
        else:
            result.summary = f"No JSON found in assessment: {text[:200]}"
            return result

    result.score = float(data.get("score", 0.0))
    result.flags = {
        "intent_mismatch": bool(data.get("intent_mismatch", False)),
        "truncation_detected": bool(data.get("truncation_detected", False)),
        "upload_incomplete": bool(data.get("upload_incomplete", False)),
        "hallucination_risk": bool(data.get("hallucination_risk", False)),
        "reasoning_gaps": bool(data.get("reasoning_gaps", False)),
    }
    result.summary = str(data.get("summary", ""))
    return result


def persist_thinking_trace(
    *,
    job_id: str,
    thinking_trace: dict[str, Any],
    artifacts_dir: Path | str,
) -> Path:
    """Write thinking_trace.json to the job artifacts directory."""
    artifacts = Path(artifacts_dir)
    job_dir = artifacts / "jobs" / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / "thinking_trace.json"
    path.write_text(json.dumps(thinking_trace, indent=2, default=str, ensure_ascii=False))
    return path


def persist_qa_assessment(
    *,
    job_id: str,
    assessment: ThinkingQAResult,
    artifacts_dir: Path | str,
) -> Path:
    """Write thinking_qa_assessment.json to the job artifacts directory."""
    artifacts = Path(artifacts_dir)
    job_dir = artifacts / "jobs" / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / "thinking_qa_assessment.json"
    path.write_text(json.dumps(assessment.to_dict(), indent=2, default=str, ensure_ascii=False))
    return path
