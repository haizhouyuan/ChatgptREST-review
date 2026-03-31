#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import threading
import uuid
from pathlib import Path
from typing import Any


ROUTE_CHATGPT_PRO = "chatgpt_pro"
ROUTE_DEEP_RESEARCH = "deep_research"
ROUTE_GEMINI = "gemini"
ROUTE_PRO_THEN_DR_THEN_PRO = "pro_then_dr_then_pro"
ROUTE_PRO_GEMINI_CROSSCHECK = "pro_gemini_crosscheck"

_CROSSCHECK_KEYWORDS: tuple[str, ...] = (
    "交叉验证",
    "双重验证",
    "多模型",
    "对照",
    "复核",
    "cross-check",
    "cross check",
)
_RESEARCH_KEYWORDS: tuple[str, ...] = (
    "调研",
    "research",
    "最新",
    "web",
    "搜索",
    "source",
    "来源",
    "引用",
    "论文",
    "benchmark",
    "竞品",
    "法规",
    "政策",
    "市场",
)
_RESEARCH_NEGATION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "zh_no_online_research",
        re.compile(
            r"(不需要|无需|无须|不用|别|不要)\s*(联网|在线|web|网络)?\s*(调研|研究|搜索|检索|查资料|查来源|查找来源)",
            re.I,
        ),
    ),
    (
        "zh_no_web_research",
        re.compile(r"(不需要|无需|无须|不用|别|不要)\s*(web|网络|联网)\s*(research|search|调研|研究|搜索)", re.I),
    ),
    (
        "en_no_research",
        re.compile(r"\b(no|without)\s+(web\s+)?(research|search|sources?)\b", re.I),
    ),
)
_STRATEGY_KEYWORDS: tuple[str, ...] = (
    "方案",
    "架构",
    "设计",
    "规划",
    "roadmap",
    "迭代",
    "review",
    "评审",
    "排障",
    "实施",
)
_GEMINI_KEYWORDS: tuple[str, ...] = ("gemini", "deep think", "备用", "兜底", "google")

_QUESTION_HINT_FIELDS: dict[str, str] = {
    "project": "请补充项目/仓库名称与分支信息。",
    "goal": "本次希望达成的明确目标是什么（可验证）？",
    "constraints": "请给出约束条件（时间、资源、合规、架构边界）。",
    "environment": "请补充运行环境（语言版本、依赖、部署环境）。",
    "acceptance": "请定义验收标准（日志指标、测试用例或交付物）。",
}

_V0_IMPORT_LOCK = threading.RLock()
_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "conclusion": ("结论", "conclusion", "summary", "tldr", "tl;dr", "总结", "最终结论"),
    "evidence": ("证据", "evidence", "依据", "rationale", "supporting", "论据"),
    "uncertainty": ("不确定", "uncertainty", "风险", "limitations", "局限", "caveats", "不确定性"),
    "next_steps": ("下一步", "next steps", "行动", "actions", "todo", "后续行动", "建议步骤"),
    "source_refs": ("来源", "source refs", "references", "sources", "citations", "参考"),
}


def _normalize_text(raw: str) -> str:
    return " ".join(str(raw or "").replace("\r", "\n").split()).strip()


def _split_lines(raw: str) -> list[str]:
    return [line.strip() for line in str(raw or "").replace("\r", "\n").split("\n")]


def prompt_refine(raw_question: str, context: dict[str, Any] | None = None) -> str:
    """Refine a low-quality question into an executable advisor prompt.

    The refined prompt keeps the original intent while adding explicit objective,
    constraints, and sub-questions so downstream channels can execute reliably.
    """

    question = _normalize_text(raw_question)
    if not question:
        return (
            "请把问题补充为：背景、目标、约束、期望输出。\n"
            "示例：\n"
            "- 背景：\n"
            "- 目标：\n"
            "- 约束：\n"
            "- 输出：\n"
        )

    lines = [
        "你是多渠道顾问代理，请先澄清问题再执行。",
        f"原始问题：{question}",
    ]
    ctx = dict(context or {})
    if ctx:
        lines.append("")
        lines.append("已知上下文：")
        for key, val in ctx.items():
            val_text = _normalize_text(str(val or ""))
            if val_text:
                lines.append(f"- {key}: {val_text}")
    lines.extend(
        [
            "",
            "请按以下结构完成：",
            "1) 目标定义：明确要解决的核心问题与成功标准。",
            "2) 上下文与约束：补齐已知事实、未知项、边界条件。",
            "3) 子问题拆解：把任务拆成 3-5 个可执行子问题。",
            "4) 渠道建议：说明为什么选择 chatgpt_pro / deep_research / gemini（或组合策略）。",
            "5) 交付格式：结论、证据、不确定项、下一步、来源引用。",
            "要求：缺失信息先列追问；不能确认的事实必须标注不确定性。",
        ]
    )
    return "\n".join(lines)


def question_gap_check(question: str, context: dict[str, Any]) -> list[str]:
    """Detect missing context and return concrete follow-up questions.

    Args:
        question: User question (raw or refined).
        context: Optional context dict from caller.

    Returns:
        Ordered follow-up prompts for missing context items.
    """

    q = _normalize_text(question)
    ctx = dict(context or {})
    asks: list[str] = []

    for key, prompt in _QUESTION_HINT_FIELDS.items():
        val = ctx.get(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            asks.append(prompt)

    q_lower = q.lower()
    ambiguous_tokens = ("这个", "那个", "它", "上次", "之前那", "same issue", "that one")
    if any(token in q_lower for token in ambiguous_tokens) and not _normalize_text(str(ctx.get("reference") or "")):
        asks.append("你提到的对象不明确，请给出具体链接/文件路径/任务编号。")

    urgency_tokens = ("尽快", "马上", "立刻", "asap", "urgent", "rush")
    has_urgency = any(token in q_lower for token in urgency_tokens)
    if has_urgency and not _normalize_text(str(ctx.get("deadline") or "")):
        asks.append("请给出明确截止时间（绝对日期时间）。")

    seen: set[str] = set()
    deduped: list[str] = []
    for item in asks:
        key = _normalize_text(item)
        if key and key not in seen:
            deduped.append(item)
            seen.add(key)
    return deduped


def channel_strategy(question: str) -> str:
    """Recommend a channel route strategy for the question."""

    trace = channel_strategy_trace(question)
    return str(trace.get("route") or ROUTE_CHATGPT_PRO)


def channel_strategy_trace(question: str) -> dict[str, Any]:
    """Return route decision trace for explainable advisor routing."""

    q = _normalize_text(question).lower()
    matched_crosscheck = [k for k in _CROSSCHECK_KEYWORDS if k in q]
    matched_research = [k for k in _RESEARCH_KEYWORDS if k in q]
    matched_research_negation = [name for name, rule in _RESEARCH_NEGATION_RULES if rule.search(q)]
    matched_strategy = [k for k in _STRATEGY_KEYWORDS if k in q]
    matched_gemini = [k for k in _GEMINI_KEYWORDS if k in q]

    has_crosscheck = bool(matched_crosscheck)
    has_research_negation = bool(matched_research_negation)
    has_research = bool(matched_research) and (not has_research_negation)
    has_strategy = bool(matched_strategy)
    has_gemini_bias = bool(matched_gemini)

    if has_crosscheck:
        route = ROUTE_PRO_GEMINI_CROSSCHECK
        reason = "matched_crosscheck_keywords"
    elif has_research and has_strategy:
        route = ROUTE_PRO_THEN_DR_THEN_PRO
        reason = "matched_research_and_strategy_keywords"
    elif has_research:
        route = ROUTE_DEEP_RESEARCH
        reason = "matched_research_keywords"
    elif has_gemini_bias:
        route = ROUTE_GEMINI
        reason = "matched_gemini_bias_keywords"
    elif matched_research and has_research_negation:
        route = ROUTE_CHATGPT_PRO
        reason = "matched_research_keywords_negated"
    else:
        route = ROUTE_CHATGPT_PRO
        reason = "default_route_chatgpt_pro"

    return {
        "route": route,
        "reason": reason,
        "flags": {
            "has_crosscheck": has_crosscheck,
            "has_research": has_research,
            "has_research_negation": has_research_negation,
            "has_strategy": has_strategy,
            "has_gemini_bias": has_gemini_bias,
        },
        "matched_keywords": {
            "crosscheck": matched_crosscheck,
            "research": matched_research,
            "research_negation": matched_research_negation,
            "strategy": matched_strategy,
            "gemini": matched_gemini,
        },
        "normalized_question": q,
    }


def _is_heading(line: str, names: tuple[str, ...]) -> bool:
    section = _detect_section_key(line)
    if not section:
        return False
    targets = {_normalize_heading_name(name) for name in names}
    return section in targets


def _collect_section(lines: list[str], names: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    in_section = False
    all_headings = (
        "结论",
        "conclusion",
        "tldr",
        "证据",
        "evidence",
        "依据",
        "不确定",
        "uncertainty",
        "风险",
        "下一步",
        "next steps",
        "行动",
        "来源",
        "source refs",
        "references",
    )
    for line in lines:
        if _is_heading(line, names):
            in_section = True
            continue
        if in_section and _is_heading(line, all_headings):
            break
        if in_section and line:
            out.append(line.lstrip("- ").strip())
    return out


def _normalize_heading_name(raw: str) -> str:
    s = str(raw or "").strip()
    s = re.sub(r"^\s{0,3}#{1,6}\s+", "", s)
    s = s.split(":", 1)[0].split("：", 1)[0]
    s = s.replace("*", "").replace("_", "")
    s = re.sub(r"^\d+[.)\s-]*", "", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _detect_section_key(line: str) -> str | None:
    s = str(line or "").strip()
    if not s:
        return None

    maybe_heading = False
    if re.match(r"^\s{0,3}#{1,6}\s+", s):
        maybe_heading = True
    if ":" in s or "：" in s:
        maybe_heading = True
    if not maybe_heading and len(s) <= 24:
        maybe_heading = True
    if not maybe_heading:
        return None

    normalized = _normalize_heading_name(s)
    if not normalized:
        return None

    for key, aliases in _SECTION_ALIASES.items():
        if normalized in {_normalize_heading_name(name) for name in aliases}:
            return key
    return None


def _strip_fenced_code_blocks(raw: str) -> str:
    out: list[str] = []
    in_code = False
    for line in str(raw or "").replace("\r", "\n").split("\n"):
        if re.match(r"^\s*(```|~~~)", line):
            in_code = not in_code
            continue
        if not in_code:
            out.append(line)
    return "\n".join(out)


def _extract_urls(raw: str) -> list[str]:
    urls = re.findall(r"https?://[^\s)\]>]+", _strip_fenced_code_blocks(raw))
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        u = u.rstrip(".,;!?\"'，。；！？）]")
        if u not in seen:
            out.append(u)
            seen.add(u)
    return out


def answer_contract(raw_answer: str) -> dict[str, Any]:
    """Parse answer text into normalized advisor JSON contract.

    The output always includes keys:
    ``conclusion``, ``evidence``, ``uncertainty``, ``next_steps``, ``source_refs``.
    """

    raw = str(raw_answer or "").strip()
    lines = _split_lines(raw)
    sections: dict[str, list[str]] = {key: [] for key in _SECTION_ALIASES}
    current_key: str | None = None
    in_code = False

    for line in lines:
        if re.match(r"^\s*(```|~~~)", line):
            in_code = not in_code
            continue
        if in_code:
            continue
        key = _detect_section_key(line)
        if key:
            current_key = key
            continue
        content = line.strip()
        if current_key and content:
            sections[current_key].append(content.lstrip("- ").strip())

    plain_lines = [line for line in _split_lines(_strip_fenced_code_blocks(raw)) if line]

    conclusion_lines = sections["conclusion"]
    evidence_lines = sections["evidence"]
    uncertainty_lines = sections["uncertainty"]
    next_lines = sections["next_steps"]
    source_lines = sections["source_refs"]

    if not conclusion_lines and plain_lines:
        conclusion_lines = [plain_lines[0]]

    if not evidence_lines and plain_lines:
        evidence_lines = [line for line in plain_lines if any(k in line.lower() for k in ("因为", "依据", "%", "data", "指标"))]

    if not uncertainty_lines and plain_lines:
        uncertainty_lines = [line for line in plain_lines if any(k in line.lower() for k in ("不确定", "可能", "待确认", "risk", "assume"))]

    if not next_lines and plain_lines:
        next_lines = [line for line in plain_lines if re.match(r"^(\d+\.|[-*])\s*", line)]

    source_refs = _extract_urls("\n".join(source_lines))
    if not source_refs:
        source_refs = _extract_urls(raw)
    if not source_refs and source_lines:
        source_refs = source_lines

    return {
        "conclusion": " ".join(conclusion_lines).strip(),
        "evidence": [item for item in evidence_lines if item],
        "uncertainty": [item for item in uncertainty_lines if item],
        "next_steps": [item for item in next_lines if item],
        "source_refs": [item for item in source_refs if item],
    }


def _load_v0_class() -> Any:
    path = Path(__file__).with_name("chatgpt_agent_shell_v0.py")
    spec = importlib.util.spec_from_file_location("chatgpt_agent_shell_v0", str(path))
    if not spec or not spec.loader:
        raise RuntimeError(f"failed to load v0 module from {path}")
    module_name = str(spec.name)
    with _V0_IMPORT_LOCK:
        force_reload = str(os.environ.get("CHATGPT_WRAPPER_V1_FORCE_RELOAD", "")).strip().lower() in {"1", "true", "yes", "on"}
        if force_reload:
            sys.modules.pop(module_name, None)

        module = sys.modules.get(module_name)
        if module is not None and not hasattr(module, "ChatGPTAgentV0"):
            sys.modules.pop(module_name, None)
            module = None

        if module is None:
            module = importlib.util.module_from_spec(spec)
            # dataclass decorators in v0 read sys.modules[__module__].
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception:
                sys.modules.pop(module_name, None)
                raise
    if not hasattr(module, "ChatGPTAgentV0"):
        raise RuntimeError("v0 module missing ChatGPTAgentV0")
    return getattr(module, "ChatGPTAgentV0")


class ChatGPTWrapperV1:
    """Advisor wrapper v1.

    v1 keeps compatibility with v0 execution ability by delegating concrete ask/wait
    execution to ``ChatGPTAgentV0`` while adding pre/post advisor capabilities.
    """

    def __init__(self, v0_agent: Any) -> None:
        self.v0_agent = v0_agent

    @staticmethod
    def _error_text(result: dict[str, Any]) -> str:
        parts = [
            str(result.get("error") or ""),
            str(result.get("reason") or ""),
            str(result.get("status") or ""),
        ]
        return " | ".join(parts).strip().lower()

    def _try_fill_conversation_url(self) -> bool:
        """Try to recover missing conversation_url from v0 status/state."""

        conversation_url = ""
        try:
            if hasattr(self.v0_agent, "get_status"):
                status_obj = self.v0_agent.get_status()
                if isinstance(status_obj, dict):
                    conversation_url = str(status_obj.get("conversation_url") or "").strip()
        except Exception:
            conversation_url = ""

        if not conversation_url:
            try:
                state_obj = getattr(self.v0_agent, "state", None)
                if isinstance(state_obj, dict):
                    conversation_url = str(state_obj.get("conversation_url") or "").strip()
                else:
                    conversation_url = str(getattr(state_obj, "conversation_url", "") or "").strip()
            except Exception:
                conversation_url = ""

        if not conversation_url:
            return False

        state_obj = getattr(self.v0_agent, "state", None)
        if state_obj is None:
            return False

        try:
            if isinstance(state_obj, dict):
                current_url = str(state_obj.get("conversation_url") or "").strip()
            else:
                current_url = str(getattr(state_obj, "conversation_url", "") or "").strip()
            if current_url == conversation_url:
                return True

            if isinstance(state_obj, dict):
                state_obj["conversation_url"] = conversation_url
            else:
                setattr(state_obj, "conversation_url", conversation_url)
            if hasattr(self.v0_agent, "_save_state"):
                self.v0_agent._save_state()
        except Exception:
            return False
        return True

    def _self_heal_once(self, *, ask_result: dict[str, Any], refined_question: str) -> tuple[dict[str, Any], list[str]]:
        """Apply one-shot self-heal for known recurrent wrapper failures."""

        err_text = self._error_text(ask_result)
        actions: list[str] = []

        if "idempotency-key" in err_text or "idempotency key" in err_text:
            actions.append("retry_with_fresh_request_context")

        if "conversation_url" in err_text or "waitingforconversationurl" in err_text:
            if self._try_fill_conversation_url():
                actions.append("recover_conversation_url_from_session")

        if not actions:
            return ask_result, actions

        retry_result = self.v0_agent.ask(question=refined_question, force=True)
        if isinstance(retry_result, dict):
            retry_result.setdefault("self_heal_actions", actions)
        return retry_result, actions

    @classmethod
    def from_v0(cls, **kwargs: Any) -> "ChatGPTWrapperV1":
        """Create a v1 wrapper by constructing an internal v0 agent."""

        v0_cls = _load_v0_class()
        return cls(v0_cls(**kwargs))

    def advise(
        self,
        *,
        raw_question: str,
        context: dict[str, Any] | None = None,
        force: bool = False,
        execute: bool = True,
    ) -> dict[str, Any]:
        """Run advisor pipeline and optionally execute with v0.

        Returns advisor metadata and normalized answer contract. If required context
        is missing, returns ``status=needs_context`` with follow-up questions.
        """

        ctx = dict(context or {})
        refined = prompt_refine(raw_question, ctx)
        gaps = question_gap_check(raw_question, ctx)
        route = channel_strategy(raw_question)

        result: dict[str, Any] = {
            "ok": True,
            "status": "planned",
            "route": route,
            "refined_question": refined,
            "followups": gaps,
            "request_id": f"advisor-v1:{uuid.uuid4().hex}",
            "answer_contract": {
                "conclusion": "",
                "evidence": [],
                "uncertainty": [],
                "next_steps": [],
                "source_refs": [],
            },
        }

        if gaps and not force:
            result["ok"] = False
            result["status"] = "needs_context"
            return result

        execution_question = refined
        if gaps and force:
            result["assumptions"] = list(gaps)
            assumption_lines = "\n".join(f"- {item}" for item in gaps)
            execution_question = (
                f"{refined}\n\n"
                "已识别待确认信息（先基于合理假设继续）：\n"
                f"{assumption_lines}"
            )

        if not execute:
            return result

        ask_result = self.v0_agent.ask(question=execution_question, force=bool(force))
        self_heal_actions: list[str] = []
        if not bool(ask_result.get("ok")):
            ask_result, self_heal_actions = self._self_heal_once(
                ask_result=dict(ask_result),
                refined_question=execution_question,
            )
        result["v0_result"] = ask_result
        result["status"] = str(ask_result.get("status") or "unknown")
        result["ok"] = bool(ask_result.get("ok"))
        result["answer_contract"] = answer_contract(str(ask_result.get("answer") or ""))
        if self_heal_actions:
            result["self_heal_actions"] = self_heal_actions

        if isinstance(ask_result, dict) and str(ask_result.get("conversation_url") or "").strip():
            result["conversation_url"] = str(ask_result.get("conversation_url") or "")
        if isinstance(ask_result, dict) and str(ask_result.get("job_id") or "").strip():
            result["job_id"] = str(ask_result.get("job_id") or "")
        return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ChatGPT advisor wrapper v1")
    parser.add_argument("--question", required=True, help="raw user question")
    parser.add_argument("--context-json", default="{}", help="context as json string")
    parser.add_argument("--execute", action="store_true", help="execute via v0 agent")
    parser.add_argument("--json", action="store_true", help="print json output")

    parser.add_argument("--base-url", default="http://127.0.0.1:18711")
    parser.add_argument("--api-token", default="")
    parser.add_argument("--state-root", default=str(Path(__file__).resolve().parents[1] / "state" / "chatgpt_agent_shell_v0"))
    parser.add_argument("--client-name", default=os.environ.get("CHATGPTREST_CLIENT_NAME", "chatgpt_wrapper_v1"))
    parser.add_argument("--client-instance", default=os.environ.get("CHATGPTREST_CLIENT_INSTANCE", ""))
    parser.add_argument("--request-id-prefix", default=os.environ.get("CHATGPTREST_REQUEST_ID_PREFIX", "chatgpt-wrapper-v1"))
    parser.add_argument("--auto-client-name-repair", action="store_true")
    parser.add_argument("--no-auto-client-name-repair", action="store_true")
    parser.add_argument(
        "--client-name-repair-allowlist",
        default=os.environ.get("CHATGPT_AGENT_V0_CLIENT_NAME_REPAIR_ALLOWLIST", ""),
    )
    parser.add_argument("--persist-client-name-repair", action="store_true")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--preset", default="auto")
    parser.add_argument("--max-turns", type=int, default=3)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--retry-base-seconds", type=int, default=30)
    parser.add_argument("--retry-max-seconds", type=int, default=180)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--send-timeout-seconds", type=int, default=180)
    parser.add_argument("--wait-timeout-seconds", type=int, default=600)
    parser.add_argument("--max-wait-seconds", type=int, default=1800)
    parser.add_argument("--min-chars", type=int, default=800)
    parser.add_argument("--poll-seconds", type=float, default=1.5)
    parser.add_argument("--answer-format", default="markdown")
    parser.add_argument("--agent-mode", choices=["on", "off"], default="on")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-roll-back", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry for local verification and incremental rollout."""

    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        context_obj = json.loads(str(args.context_json or "{}"))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"invalid --context-json: {exc}"}, ensure_ascii=False))
        return 2
    if not isinstance(context_obj, dict):
        print(json.dumps({"ok": False, "error": "--context-json must be an object"}, ensure_ascii=False))
        return 2
    if bool(args.auto_client_name_repair) and bool(args.no_auto_client_name_repair):
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "--auto-client-name-repair and --no-auto-client-name-repair are mutually exclusive",
                },
                ensure_ascii=False,
            )
        )
        return 2
    auto_client_name_repair_opt: bool | None = None
    if bool(args.auto_client_name_repair):
        auto_client_name_repair_opt = True
    elif bool(args.no_auto_client_name_repair):
        auto_client_name_repair_opt = False
    repair_allowlist_opt = [
        p.strip() for p in str(args.client_name_repair_allowlist or "").replace(";", ",").split(",") if p.strip()
    ] or None

    v1 = ChatGPTWrapperV1.from_v0(
        base_url=str(args.base_url),
        api_token=str(args.api_token or ""),
        state_root=Path(str(args.state_root)),
        client_name=(str(args.client_name).strip() or None),
        client_instance=(str(args.client_instance).strip() or None),
        request_id_prefix=(str(args.request_id_prefix).strip() or None),
        auto_client_name_repair=auto_client_name_repair_opt,
        client_name_repair_allowlist=repair_allowlist_opt,
        persist_client_name_repair=bool(args.persist_client_name_repair),
        session_id=(str(args.session_id).strip() or None),
        preset=str(args.preset),
        max_turns=int(args.max_turns),
        max_retries=int(args.max_retries),
        retry_base_seconds=int(args.retry_base_seconds),
        retry_max_seconds=int(args.retry_max_seconds),
        timeout_seconds=int(args.timeout_seconds),
        send_timeout_seconds=int(args.send_timeout_seconds),
        wait_timeout_seconds=int(args.wait_timeout_seconds),
        max_wait_seconds=int(args.max_wait_seconds),
        min_chars=int(args.min_chars),
        poll_seconds=float(args.poll_seconds),
        answer_format=str(args.answer_format),
        agent_mode=(str(args.agent_mode).strip().lower() != "off"),
        dry_run=bool(args.dry_run),
        auto_rollback=not bool(args.no_roll_back),
    )

    out = v1.advise(
        raw_question=str(args.question),
        context=context_obj,
        force=bool(args.force),
        execute=bool(args.execute),
    )

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if bool(out.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
