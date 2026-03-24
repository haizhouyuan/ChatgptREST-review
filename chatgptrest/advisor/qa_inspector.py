"""QA Inspector Agent — 8D-based task completion quality evaluation.

Uses dual-model evaluation (Codex + Gemini) for comprehensive quality
analysis following the 8D methodology adapted for AI task completion:

  D1: Task Context — who asked, via which channel
  D2: Problem Description — what was requested
  D3: Execution Summary — what was actually done
  D4: Quality Analysis — strengths and weaknesses
  D5: Root Cause of Issues — why certain things failed
  D6: Corrective Actions — what should be improved
  D7: Prevention — how to prevent recurrence
  D8: Knowledge Capture — what to feed into EvoMap

Results feed back into EvoMap as quality signals, improving EvoScore's
"feedback health" and "usage impact" dimensions.
"""
from __future__ import annotations

import json
import logging
import os
import time
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EVOMAP_DB = str(_REPO_ROOT / "data" / "evomap_knowledge.db")
_QA_INSPECTOR_CLIENT_NAME = (os.environ.get("CHATGPTREST_QA_INSPECTOR_CLIENT_NAME") or "chatgptrestctl").strip() or "chatgptrestctl"
_QA_INSPECTOR_CLIENT_INSTANCE = (os.environ.get("CHATGPTREST_QA_INSPECTOR_CLIENT_INSTANCE") or f"qa-inspector-{os.getpid()}").strip() or f"qa-inspector-{os.getpid()}"


# ── Quality Rubric ─────────────────────────────────────────────


@dataclass
class QualityDimension:
    name: str
    score: int = 0           # 1-5
    max_score: int = 5
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    comment: str = ""


@dataclass
class QualityReport8D:
    """8D-style quality report for a completed task."""
    # D1: Context
    task_id: str = ""
    channel: str = ""        # feishu / mcp / api
    user_id: str = ""
    timestamp: float = 0.0

    # D2: Problem Description
    original_question: str = ""

    # D3: Execution Summary
    answer_text: str = ""
    route_used: str = ""
    kb_hits: int = 0
    response_time_sec: float = 0.0

    # D4: Quality Dimensions (scored by evaluators)
    completeness: QualityDimension = field(
        default_factory=lambda: QualityDimension("completeness")
    )
    accuracy: QualityDimension = field(
        default_factory=lambda: QualityDimension("accuracy")
    )
    kb_utilization: QualityDimension = field(
        default_factory=lambda: QualityDimension("kb_utilization")
    )
    actionability: QualityDimension = field(
        default_factory=lambda: QualityDimension("actionability")
    )
    communication: QualityDimension = field(
        default_factory=lambda: QualityDimension("communication")
    )

    # D5-D7: Analysis
    root_causes: list[str] = field(default_factory=list)
    corrective_actions: list[str] = field(default_factory=list)
    prevention_measures: list[str] = field(default_factory=list)

    # D8: Knowledge Capture
    knowledge_atoms: list[str] = field(default_factory=list)
    improvement_signals: list[str] = field(default_factory=list)

    # Meta
    evaluator_model: str = ""
    overall_score: float = 0.0
    overall_verdict: str = ""   # excellent / good / needs_improvement / poor
    raw_evaluation: str = ""

    def total_score(self) -> float:
        dims = [
            self.completeness, self.accuracy,
            self.kb_utilization, self.actionability,
            self.communication,
        ]
        return sum(d.score for d in dims)

    def max_total(self) -> int:
        return 25

    def score_pct(self) -> float:
        m = self.max_total()
        return (self.total_score() / m * 100) if m else 0


# ── Evaluation Prompt ──────────────────────────────────────────


_EVAL_PROMPT_TEMPLATE = """你是一名AI系统质量检查员(QA Inspector)。请对以下任务的完成情况做8D质量评估。

## 任务信息

**用户问题**: {question}

**系统回答**: 
{answer}

**路由方式**: {route}
**KB命中数**: {kb_hits}
**响应时间**: {response_time:.1f}秒

## 评估要求

请按以下5个维度打分(1-5分)，并详细说明做的好的地方和做的不好的地方：

### 评分维度
1. **完整性(completeness)**: 是否完整回答了用户的所有问题点？
2. **准确性(accuracy)**: 信息是否准确、无虚构、无误导？
3. **KB利用率(kb_utilization)**: 是否有效利用了已有知识库？如果KB命中了但回答没用到，扣分。
4. **可操作性(actionability)**: 回复是否可以直接执行或直接使用？
5. **沟通质量(communication)**: 表达是否清晰、结构化、适合目标用户？

### 8D分析
- **D5 根因分析**: 如果有做的不好的地方，根本原因是什么？
- **D6 纠正措施**: 应该如何改进？
- **D7 预防措施**: 如何防止类似问题再次发生？
- **D8 知识萃取**: 这次任务中有什么值得记录到知识库的经验？

## 输出格式

请严格按以下JSON格式输出（不要加```json标记）：

{{
  "completeness": {{"score": N, "strengths": ["..."], "weaknesses": ["..."], "comment": "..."}},
  "accuracy": {{"score": N, "strengths": ["..."], "weaknesses": ["..."], "comment": "..."}},
  "kb_utilization": {{"score": N, "strengths": ["..."], "weaknesses": ["..."], "comment": "..."}},
  "actionability": {{"score": N, "strengths": ["..."], "weaknesses": ["..."], "comment": "..."}},
  "communication": {{"score": N, "strengths": ["..."], "weaknesses": ["..."], "comment": "..."}},
  "root_causes": ["如果有问题的根本原因"],
  "corrective_actions": ["建议的纠正措施"],
  "prevention_measures": ["预防措施"],
  "knowledge_atoms": ["值得记录的知识点"],
  "overall_verdict": "excellent|good|needs_improvement|poor",
  "overall_comment": "总体评价（2-3句话）"
}}
"""


# ── Inspector Engine ───────────────────────────────────────────


class QAInspector:
    """Dual-model quality inspector using 8D methodology."""

    def __init__(self, api_base: str = ""):
        self._api_base = api_base or f"http://127.0.0.1:{os.environ.get('CHATGPTREST_PORT', '18711')}"

    def inspect(
        self,
        question: str,
        answer: str,
        route: str = "",
        kb_hits: int = 0,
        response_time: float = 0.0,
        task_id: str = "",
        channel: str = "",
        user_id: str = "",
    ) -> list[QualityReport8D]:
        """Run dual-model evaluation. Returns list of reports (one per model).

        Uses chatgptrest_consult to evaluate with both models in parallel.
        """
        if not answer or len(answer) < 50:
            logger.debug("QA Inspector: answer too short, skipping")
            return []

        prompt = _EVAL_PROMPT_TEMPLATE.format(
            question=question[:1000],
            answer=answer[:4000],
            route=route,
            kb_hits=kb_hits,
            response_time=response_time,
        )

        reports = []

        # Model 1: Gemini Deep Think
        try:
            report_gemini = self._evaluate_single(
                prompt, provider="gemini", preset="deep_think",
                question=question, answer=answer, route=route,
                kb_hits=kb_hits, response_time=response_time,
                task_id=task_id, channel=channel, user_id=user_id,
            )
            if report_gemini:
                reports.append(report_gemini)
        except Exception as e:
            logger.warning("QA Gemini evaluation failed: %s", e)

        # Model 2: ChatGPT Pro
        try:
            report_chatgpt = self._evaluate_single(
                prompt, provider="chatgpt", preset="auto",
                question=question, answer=answer, route=route,
                kb_hits=kb_hits, response_time=response_time,
                task_id=task_id, channel=channel, user_id=user_id,
            )
            if report_chatgpt:
                reports.append(report_chatgpt)
        except Exception as e:
            logger.warning("QA ChatGPT evaluation failed: %s", e)

        return reports

    def inspect_evaluator_results(
        self,
        question: str,
        answer: str,
        route: str = "",
        kb_hits: int = 0,
        response_time: float = 0.0,
        task_id: str = "",
        channel: str = "",
        user_id: str = "",
        trace_id: str = "",
        run_id: str = "",
        job_id: str = "",
        task_ref: str = "",
        logical_task_id: str = "",
        identity_confidence: str = "",
    ) -> list[dict[str, Any]]:
        """Adapter surface for the evaluator plane.

        Keeps the existing QA inspector logic as the report generator, then
        converts those reports into a normalized evaluator schema.
        """
        from chatgptrest.eval.evaluator_service import EvaluatorService

        reports = self.inspect(
            question=question,
            answer=answer,
            route=route,
            kb_hits=kb_hits,
            response_time=response_time,
            task_id=task_id,
            channel=channel,
            user_id=user_id,
        )
        service = EvaluatorService()
        return [
            result.to_dict()
            for result in service.from_reports(
                reports,
                trace_id=trace_id,
                run_id=run_id,
                job_id=job_id,
                task_ref=task_ref,
                logical_task_id=logical_task_id,
                identity_confidence=identity_confidence,
            )
        ]

    def _evaluate_single(
        self,
        prompt: str,
        provider: str,
        preset: str,
        question: str,
        answer: str,
        route: str,
        kb_hits: int,
        response_time: float,
        task_id: str,
        channel: str,
        user_id: str,
    ) -> Optional[QualityReport8D]:
        """Submit evaluation to a single model and parse the result."""
        import urllib.request
        import urllib.error

        idem_key = f"qa-inspect-{provider}-{task_id or int(time.time())}"
        request_id = f"{idem_key}-submit"

        # Use the ChatgptREST ask API
        url = f"{self._api_base}/v1/jobs"
        kind = f"{provider}_web.ask"

        payload = json.dumps({
            "kind": kind,
            "input": {
                "question": str(prompt or "").replace("\x00", " ")[:12000],
            },
            "params": {
                "preset": preset,
                "purpose": "qa_inspector",
                "min_chars": 0,
            },
        }).encode()

        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": idem_key,
            "X-Client-Name": _QA_INSPECTOR_CLIENT_NAME,
            "X-Client-Instance": _QA_INSPECTOR_CLIENT_INSTANCE,
            "X-Request-ID": request_id,
        }
        token = os.environ.get("CHATGPTREST_API_TOKEN", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                job_data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            logger.warning("QA Inspector job submit failed (%s): %s body=%s", provider, e, body[:500])
            return None
        except Exception as e:
            logger.warning("QA Inspector job submit failed (%s): %s", provider, e)
            return None

        job_id = job_data.get("job_id", "")
        if not job_id:
            return None

        logger.info("QA Inspector: submitted %s evaluation job %s", provider, job_id[:12])

        # Wait for completion (up to 10 minutes)
        answer_text = self._wait_and_read(job_id, timeout=600)
        if not answer_text:
            logger.warning("QA Inspector: %s evaluation timed out", provider)
            return None

        # Parse the JSON result
        report = self._parse_eval_result(
            answer_text, provider,
            question=question, answer=answer, route=route,
            kb_hits=kb_hits, response_time=response_time,
            task_id=task_id, channel=channel, user_id=user_id,
        )
        return report

    def _wait_and_read(self, job_id: str, timeout: int = 600) -> str:
        """Poll job until complete and read answer."""
        import urllib.request

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                url = f"{self._api_base}/v1/jobs/{job_id}"
                headers = {}
                token = os.environ.get("CHATGPTREST_API_TOKEN", "")
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())

                status = data.get("status", "")
                if status == "completed":
                    # Read answer
                    ans_url = f"{self._api_base}/v1/jobs/{job_id}/answer?max_chars=16000"
                    req2 = urllib.request.Request(ans_url, headers=headers)
                    with urllib.request.urlopen(req2, timeout=10) as resp2:
                        ans_data = json.loads(resp2.read().decode())
                    return ans_data.get("text", "") or ans_data.get("chunk", "")
                elif status in ("error", "canceled"):
                    logger.warning("QA job %s ended with status: %s", job_id[:12], status)
                    return ""
            except Exception:
                pass

            time.sleep(15)

        return ""

    def _parse_eval_result(
        self, raw_text: str, provider: str, **kwargs
    ) -> Optional[QualityReport8D]:
        """Parse model evaluation output into QualityReport8D."""
        report = QualityReport8D(
            task_id=kwargs.get("task_id", ""),
            channel=kwargs.get("channel", ""),
            user_id=kwargs.get("user_id", ""),
            timestamp=time.time(),
            original_question=kwargs.get("question", ""),
            answer_text=kwargs.get("answer", "")[:2000],
            route_used=kwargs.get("route", ""),
            kb_hits=kwargs.get("kb_hits", 0),
            response_time_sec=kwargs.get("response_time", 0.0),
            evaluator_model=provider,
            raw_evaluation=raw_text[:5000],
        )

        # Try to extract JSON from the response
        parsed = None
        try:
            # Try direct parse
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            # Try to find JSON block in text
            import re
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_text, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

        if not parsed:
            logger.warning("QA Inspector: could not parse %s evaluation JSON", provider)
            # Still return the report with raw text
            report.overall_verdict = "parse_error"
            return report

        # Map parsed data to report
        for dim_name in ["completeness", "accuracy", "kb_utilization", "actionability", "communication"]:
            dim_data = parsed.get(dim_name, {})
            dim = getattr(report, dim_name)
            dim.score = max(1, min(5, int(dim_data.get("score", 3))))
            dim.strengths = dim_data.get("strengths", [])[:5]
            dim.weaknesses = dim_data.get("weaknesses", [])[:5]
            dim.comment = str(dim_data.get("comment", ""))[:300]

        report.root_causes = parsed.get("root_causes", [])[:5]
        report.corrective_actions = parsed.get("corrective_actions", [])[:5]
        report.prevention_measures = parsed.get("prevention_measures", [])[:5]
        report.knowledge_atoms = parsed.get("knowledge_atoms", [])[:5]
        report.overall_verdict = parsed.get("overall_verdict", "unknown")
        report.overall_score = report.total_score()

        # Store overall comment as an improvement signal
        comment = parsed.get("overall_comment", "")
        if comment:
            report.improvement_signals.append(comment)

        return report

    def write_evomap_feedback(self, reports: list[QualityReport8D]) -> None:
        """Write quality signals back to EvoMap as feedback atoms."""
        if not reports:
            return

        try:
            from chatgptrest.evomap.knowledge.extractors.auto_extractor import _insert_atom
        except ImportError:
            logger.debug("QA Inspector: EvoMap not available, skipping feedback")
            return

        for report in reports:
            try:
                # Create a quality feedback atom
                q = f"[QA质检] {report.original_question[:200]}"
                lines = [
                    f"## 8D质检报告 (by {report.evaluator_model})",
                    f"评分: {report.total_score()}/{report.max_total()} ({report.overall_verdict})",
                    "",
                ]

                # Dimensions
                for dim_name in ["completeness", "accuracy", "kb_utilization", "actionability", "communication"]:
                    dim = getattr(report, dim_name)
                    lines.append(f"### {dim_name}: {dim.score}/5")
                    if dim.strengths:
                        lines.append("优势: " + "; ".join(dim.strengths[:3]))
                    if dim.weaknesses:
                        lines.append("不足: " + "; ".join(dim.weaknesses[:3]))

                # D5-D7
                if report.root_causes:
                    lines.append("\n### 根因: " + "; ".join(report.root_causes[:3]))
                if report.corrective_actions:
                    lines.append("### 纠正: " + "; ".join(report.corrective_actions[:3]))
                if report.prevention_measures:
                    lines.append("### 预防: " + "; ".join(report.prevention_measures[:3]))
                if report.improvement_signals:
                    lines.append("\n### 总评: " + report.improvement_signals[0])

                answer_text = "\n".join(lines)

                _insert_atom(
                    db_path=_EVOMAP_DB,
                    question=q,
                    answer=answer_text[:4000],
                    job_id=f"qa_inspect:{report.evaluator_model}:{report.task_id[:12]}",
                )
                logger.info(
                    "QA feedback written to EvoMap: %s score=%d/%d verdict=%s",
                    report.evaluator_model, report.total_score(),
                    report.max_total(), report.overall_verdict,
                )
            except Exception as e:
                logger.warning("QA EvoMap feedback failed: %s", e)


# ── Convenience: Fire-and-Forget Hook ──────────────────────────


def qa_inspect_async(
    question: str,
    answer: str,
    route: str = "",
    kb_hits: int = 0,
    response_time: float = 0.0,
    task_id: str = "",
    channel: str = "unknown",
    user_id: str = "",
) -> None:
    """Fire-and-forget QA inspection.

    Runs in a background thread. Evaluates with dual models and writes
    results to EvoMap.
    """
    if not answer or len(answer) < 200:
        return

    def _bg():
        try:
            inspector = QAInspector()
            reports = inspector.inspect(
                question=question, answer=answer, route=route,
                kb_hits=kb_hits, response_time=response_time,
                task_id=task_id, channel=channel, user_id=user_id,
            )

            if reports:
                # Write feedback to EvoMap
                inspector.write_evomap_feedback(reports)

                # Log summary
                for r in reports:
                    logger.info(
                        "QA Report [%s]: %d/%d (%s) — %s",
                        r.evaluator_model,
                        r.total_score(), r.max_total(),
                        r.overall_verdict,
                        (r.improvement_signals[0][:100] if r.improvement_signals else ""),
                    )
        except Exception as e:
            logger.error("QA inspection failed: %s", e)

    threading.Thread(
        target=_bg, daemon=True,
        name=f"qa-inspect-{task_id[:8]}",
    ).start()


# ── CLI: Manual Inspection ─────────────────────────────────────


def main():
    """CLI entry point for manual QA inspection."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="QA Inspector — 8D quality evaluation")
    parser.add_argument("-q", "--question", required=True, help="Original question")
    parser.add_argument("-a", "--answer", help="Answer text (or - for stdin)")
    parser.add_argument("--answer-file", help="Read answer from file")
    parser.add_argument("--route", default="", help="Route used")
    parser.add_argument("--kb-hits", type=int, default=0, help="KB hit count")
    parser.add_argument("--time", type=float, default=0.0, help="Response time (sec)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-evomap", action="store_true", help="Don't write to EvoMap")
    args = parser.parse_args()

    # Get answer text
    answer = args.answer or ""
    if args.answer_file:
        answer = Path(args.answer_file).read_text()
    elif args.answer == "-":
        answer = sys.stdin.read()

    if not answer:
        print("Error: answer text required (-a or --answer-file)")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    inspector = QAInspector()
    print(f"Running dual-model QA inspection...")
    print(f"  Question: {args.question[:80]}...")
    print(f"  Answer: {len(answer)} chars")
    print()

    reports = inspector.inspect(
        question=args.question,
        answer=answer,
        route=args.route,
        kb_hits=args.kb_hits,
        response_time=args.time,
        task_id=f"manual-{int(time.time())}",
        channel="cli",
    )

    if not reports:
        print("No evaluations completed.")
        sys.exit(1)

    for report in reports:
        if args.json:
            print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
        else:
            _print_8d_report(report)

    # Write to EvoMap
    if not args.no_evomap:
        inspector.write_evomap_feedback(reports)
        print(f"\n✅ Quality feedback written to EvoMap")


def _print_8d_report(report: QualityReport8D) -> None:
    """Pretty-print an 8D report to terminal."""
    score = report.total_score()
    max_s = report.max_total()
    pct = report.score_pct()

    verdict_icons = {
        "excellent": "🏆", "good": "✅",
        "needs_improvement": "⚠️", "poor": "❌",
    }
    icon = verdict_icons.get(report.overall_verdict, "❓")

    print(f"\n{'='*60}")
    print(f"  8D Quality Report — {report.evaluator_model.upper()}")
    print(f"  {icon} {score}/{max_s} ({pct:.0f}%) — {report.overall_verdict}")
    print(f"{'='*60}")

    # D4: Dimensions
    print(f"\n  D4: Quality Dimensions")
    print(f"  {'─'*40}")
    for dim_name in ["completeness", "accuracy", "kb_utilization", "actionability", "communication"]:
        dim = getattr(report, dim_name)
        bar = "█" * dim.score + "░" * (5 - dim.score)
        print(f"  {dim_name:<18} {bar} {dim.score}/5")
        if dim.strengths:
            for s in dim.strengths[:2]:
                print(f"    ✅ {s}")
        if dim.weaknesses:
            for w in dim.weaknesses[:2]:
                print(f"    ❌ {w}")

    # D5-D7
    if report.root_causes:
        print(f"\n  D5: Root Causes")
        for rc in report.root_causes:
            print(f"    • {rc}")

    if report.corrective_actions:
        print(f"\n  D6: Corrective Actions")
        for ca in report.corrective_actions:
            print(f"    → {ca}")

    if report.prevention_measures:
        print(f"\n  D7: Prevention")
        for pm in report.prevention_measures:
            print(f"    🛡️ {pm}")

    # D8
    if report.knowledge_atoms:
        print(f"\n  D8: Knowledge Capture")
        for ka in report.knowledge_atoms:
            print(f"    📝 {ka}")

    if report.improvement_signals:
        print(f"\n  Overall: {report.improvement_signals[0]}")

    print()


if __name__ == "__main__":
    main()
