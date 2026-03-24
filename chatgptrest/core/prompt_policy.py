from __future__ import annotations

import re
from typing import Any

from chatgptrest.providers.registry import is_web_ask_kind


_SMOKETEST_PREFIX_RE = re.compile(r"^\s*[\(\[]\s*smoke\s*test\s*[\)\]]", re.I)
_SMOKETEST_COMPACT_PREFIX_RE = re.compile(r"^\s*[\(\[]\s*smoketest\s*[\)\]]", re.I)
_TRIVIAL_PRO_PROMPT_RE = re.compile(
    r"^\s*(?:"
    r"hi|"
    r"hello|"
    r"hey|"
    r"ok|"
    r"yes|"
    r"no|"
    r"ping|"
    r"test|"
    r"你好|"
    r"测试|"
    r"请(?:只)?回复[:：]?\s*ok|"
    r"回复[:：]?\s*ok|"
    r"只回复[:：]?\s*ok|"
    r"reply(?:\s+with)?\s+ok|"
    r"just\s+say\s+ok"
    r")\s*[.!。！？?]*\s*$",
    re.I,
)
_TRIVIAL_PRO_BREVITY_RE = re.compile(
    r"(?:"
    r"只(?:回复|返回|给出|说)|"
    r"简(?:短|要)(?:回答|说明|解释|介绍)|"
    r"简单(?:回答|说明|解释|介绍)|"
    r"简述|"
    r"[一二两三四1234]\s*句话|"
    r"不超过\s*\d+\s*字|"
    r"只做最终行动判定|"
    r"只说结论|"
    r"只给结论|"
    r"just\s+(?:answer|say|give)|"
    r"(?:one|two|three|four)\s+sentences?"
    r")",
    re.I,
)

_CHATGPT_PRO_PRESETS: frozenset[str] = frozenset(
    {
        "pro_extended",
        "thinking_heavy",
        "thinking_extended",
        "deep_research",
        "deep-research",
        "deepresearch",
        "research",
    }
)
_GEMINI_PRO_PRESETS: frozenset[str] = frozenset({"pro"})
_SMOKE_PURPOSES: frozenset[str] = frozenset(
    {
        "smoke",
        "test",
        "tests",
        "testing",
        "probe",
        "ping",
        "sanity",
        "healthcheck",
        "health_check",
    }
)
_LIVE_CHATGPT_SMOKE_CLIENT_NAMES: frozenset[str] = frozenset(
    {
        "smoke_test_chatgpt_auto",
        "fault_tester",
        "bi14_fault_tester",
    }
)
_LIVE_CHATGPT_SYNTHETIC_PROBE_RE = re.compile(
    r"^\s*(?:"
    r"test\s+(?:blocked|cooldown|needs[_\s-]*followup|error|cancel)(?:\s+state)?|"
    r"quick\s+probe|"
    r"sanity\s+check|"
    r"health\s+check"
    r")\s*$",
    re.I,
)
_PROMPT_CONTEXT_SPLIT_RE = re.compile(
    r"\n\s*---\s*(?:附加上下文|additional\s+context|context)\s*---\s*",
    re.I,
)


class PromptPolicyViolation(ValueError):
    def __init__(self, *, error: str, detail: str, hint: str) -> None:
        super().__init__(detail)
        self.error = str(error)
        self.detail = {
            "error": str(error),
            "detail": str(detail),
            "hint": str(hint),
        }


def purpose_from_params(params_obj: Any) -> str:
    if not isinstance(params_obj, dict):
        return ""
    raw = params_obj.get("purpose")
    if not isinstance(raw, str):
        return ""
    return raw.strip().lower()


def client_name_from_client_obj(client_obj: Any) -> str:
    if not isinstance(client_obj, dict):
        return ""
    raw = client_obj.get("name")
    if not isinstance(raw, str):
        return ""
    return raw.strip().lower()


def is_pro_preset_for_kind(*, kind: str, preset: str) -> bool:
    k = str(kind or "").strip().lower()
    p = str(preset or "").strip().lower()
    if k == "chatgpt_web.ask":
        return p in _CHATGPT_PRO_PRESETS
    if k == "gemini_web.ask":
        return p in _GEMINI_PRO_PRESETS
    return False


def looks_like_smoketest_prompt(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    return bool(_SMOKETEST_PREFIX_RE.search(raw) or _SMOKETEST_COMPACT_PREFIX_RE.search(raw))


def looks_like_trivial_pro_prompt(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return True
    if _TRIVIAL_PRO_PROMPT_RE.search(raw):
        return True
    if len(raw) <= 160 and _TRIVIAL_PRO_BREVITY_RE.search(raw):
        return True
    compact = "".join(raw.split()).lower()
    if compact in {"请回复ok", "回复ok", "只回复ok"}:
        return True
    return False


def looks_like_live_chatgpt_smoke_prompt(text: str) -> bool:
    raw = canonical_prompt_head(text)
    if not raw:
        return False
    return bool(
        _SMOKETEST_PREFIX_RE.search(raw)
        or _SMOKETEST_COMPACT_PREFIX_RE.search(raw)
        or _LIVE_CHATGPT_SYNTHETIC_PROBE_RE.search(raw)
    )


def canonical_prompt_head(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    parts = _PROMPT_CONTEXT_SPLIT_RE.split(raw, maxsplit=1)
    return str(parts[0] if parts else raw).strip()


def looks_like_synthetic_or_trivial_agent_prompt(text: str) -> bool:
    head = canonical_prompt_head(text)
    if not head:
        return False
    return looks_like_live_chatgpt_smoke_prompt(head) or looks_like_trivial_pro_prompt(head)


def enforce_agent_ingress_prompt_policy(
    *,
    question: str,
    allow_synthetic_prompt: bool = False,
) -> None:
    if allow_synthetic_prompt:
        return
    head = canonical_prompt_head(question)
    if not head:
        return
    if looks_like_live_chatgpt_smoke_prompt(head):
        raise PromptPolicyViolation(
            error="agent_synthetic_prompt_blocked",
            detail="synthetic smoke/probe prompts are blocked on advisor/public agent ingress",
            hint="Use a mock path or non-live substrate for smoke/fault probes.",
        )
    if looks_like_trivial_pro_prompt(head):
        raise PromptPolicyViolation(
            error="agent_trivial_prompt_blocked",
            detail="trivial prompts are blocked on advisor/public agent ingress",
            hint="Use a substantive task instead of hello/test/ping style prompts.",
        )


def enforce_prompt_submission_policy(
    *,
    kind: str,
    input_obj: dict[str, Any],
    params_obj: dict[str, Any],
    client_obj: dict[str, Any] | None = None,
) -> None:
    if not is_web_ask_kind(kind):
        return

    preset = str((params_obj or {}).get("preset") or "").strip().lower()
    question = str((input_obj or {}).get("question") or "").strip()
    purpose = purpose_from_params(params_obj)
    client_name = client_name_from_client_obj(client_obj)

    if is_pro_preset_for_kind(kind=kind, preset=preset):
        pro_smoke_detected = (
            purpose in _SMOKE_PURPOSES
            or client_name in _LIVE_CHATGPT_SMOKE_CLIENT_NAMES
            or looks_like_smoketest_prompt(question)
            or looks_like_live_chatgpt_smoke_prompt(question)
        )
        if pro_smoke_detected:
            raise PromptPolicyViolation(
                error="pro_smoke_test_blocked",
                detail="smoke/test prompts are hard-blocked on Pro presets",
                hint="Use a non-Pro preset for smoke tests.",
            )

        if looks_like_trivial_pro_prompt(question):
            raise PromptPolicyViolation(
                error="trivial_pro_prompt_blocked",
                detail="trivial prompts are hard-blocked on Pro presets",
                hint="Use a non-Pro preset or ask a substantive, human-like question.",
            )

    if kind == "chatgpt_web.ask":
        allow_live_chatgpt_smoke = bool((params_obj or {}).get("allow_live_chatgpt_smoke") or False)
        if (
            purpose in _SMOKE_PURPOSES
            or client_name in _LIVE_CHATGPT_SMOKE_CLIENT_NAMES
            or looks_like_live_chatgpt_smoke_prompt(question)
        ) and not allow_live_chatgpt_smoke:
            raise PromptPolicyViolation(
                error="live_chatgpt_smoke_blocked",
                detail="live smoke/test prompts are blocked on chatgpt_web.ask by default",
                hint="Use gemini/qwen or a mock path for smoke tests. Set params.allow_live_chatgpt_smoke=true only for controlled exceptions.",
            )
