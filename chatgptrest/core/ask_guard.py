from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

from chatgptrest.core.codex_runner import codex_exec_with_schema
from chatgptrest.core.prompt_policy import (
    canonical_prompt_head,
    looks_like_live_chatgpt_smoke_prompt,
    looks_like_trivial_pro_prompt,
    purpose_from_params,
)
from chatgptrest.providers.registry import is_web_ask_kind

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_REGISTRY_PATH = (_REPO_ROOT / "ops" / "policies" / "ask_client_registry.json").resolve()
_SCHEMA_PATH = (_REPO_ROOT / "ops" / "schemas" / "ask_guard_decision.schema.json").resolve()
_STRUCTURED_OUTPUT_HINTS = (
    "只返回json",
    "只输出json",
    "只返回 json",
    "只输出 json",
    "return only json",
    "respond with json only",
    "only output json",
    "json array",
    "json object",
)
_MICROTASK_HINTS = (
    "你是一个产业链知识图谱构建助手",
    "你是一个竞品分析助手",
    "知识图谱",
    "竞品分析",
    "结构化提取",
    "extract triples",
    "extract entities",
    "extract competitors",
)
_SUFFICIENCY_HINTS = (
    "判断这批检索结果是否足以支撑当前查询",
    "只回答 sufficient 或 insufficient",
    "只回答sufficient或insufficient",
    "only answer sufficient or insufficient",
    "sufficient or insufficient",
)
_VALID_AUTH_MODES = {"registry", "hmac"}
_VALID_TRUST_CLASSES = {
    "interactive_trusted",
    "automation_registered",
    "maintenance_internal",
    "testing_only",
}
_VALID_SOURCE_TYPES = {
    "interactive_cli",
    "bot",
    "timer",
    "service",
    "pipeline",
    "maintenance",
    "smoke_test",
}
_VALID_CODEX_GUARD_MODES = {"bypass", "deterministic_only", "classify"}
_NONCE_TTL_SECONDS = 10 * 60
_NONCE_CACHE: dict[str, float] = {}
_REGISTRY_CACHE: tuple[str, float, dict[str, Any]] | None = None


@dataclass(frozen=True)
class AskClientProfile:
    client_id: str
    aliases: tuple[str, ...]
    display_name: str
    source_type: str
    trust_class: str
    auth_mode: str
    allowed_surfaces: tuple[str, ...]
    allowed_kinds: tuple[str, ...]
    allow_live_chatgpt: bool
    allow_gemini_web: bool
    allow_qwen_web: bool
    allow_deep_research: bool
    allow_pro: bool
    codex_guard_mode: str
    notes: str
    shared_secret_env: str = ""
    enabled: bool = True
    max_in_flight_jobs: int = 0
    dedupe_window_seconds: int = 0


def _normalize_text(value: Any, *, max_chars: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:max_chars]


def _normalize_token(value: Any, *, max_chars: int = 200) -> str:
    return _normalize_text(value, max_chars=max_chars).lower()


def _normalize_str_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    out: list[str] = []
    for item in value:
        token = _normalize_token(item)
        if token and token not in out:
            out.append(token)
    return tuple(out)


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _registry_path() -> Path:
    raw = _normalize_text(os.environ.get("CHATGPTREST_ASK_CLIENT_REGISTRY_PATH") or "", max_chars=2000)
    if raw:
        return Path(raw).expanduser().resolve()
    return _DEFAULT_REGISTRY_PATH


def _load_registry_payload() -> dict[str, Any]:
    global _REGISTRY_CACHE
    path = _registry_path()
    try:
        stat = path.stat()
        mtime = float(stat.st_mtime)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ask client registry not found: {path}") from exc
    cache = _REGISTRY_CACHE
    if cache is not None and cache[0] == str(path) and cache[1] == mtime:
        return dict(cache[2])
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"failed to parse ask client registry: {path}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError(f"ask client registry must be an object: {path}")
    _REGISTRY_CACHE = (str(path), mtime, dict(raw))
    return dict(raw)


def _profile_from_payload(raw: dict[str, Any]) -> AskClientProfile:
    client_id = _normalize_token(raw.get("client_id"))
    if not client_id:
        raise RuntimeError("ask client registry profile missing client_id")
    aliases = _normalize_str_list(raw.get("aliases"))
    display_name = _normalize_text(raw.get("display_name") or client_id, max_chars=200)
    source_type = _normalize_token(raw.get("source_type"))
    trust_class = _normalize_token(raw.get("trust_class"))
    auth_mode = _normalize_token(raw.get("auth_mode") or "registry")
    codex_guard_mode = _normalize_token(raw.get("codex_guard_mode") or "bypass")
    if source_type not in _VALID_SOURCE_TYPES:
        raise RuntimeError(f"invalid source_type for ask client profile {client_id}: {source_type}")
    if trust_class not in _VALID_TRUST_CLASSES:
        raise RuntimeError(f"invalid trust_class for ask client profile {client_id}: {trust_class}")
    if auth_mode not in _VALID_AUTH_MODES:
        raise RuntimeError(f"invalid auth_mode for ask client profile {client_id}: {auth_mode}")
    if codex_guard_mode not in _VALID_CODEX_GUARD_MODES:
        raise RuntimeError(f"invalid codex_guard_mode for ask client profile {client_id}: {codex_guard_mode}")
    return AskClientProfile(
        client_id=client_id,
        aliases=aliases,
        display_name=display_name,
        source_type=source_type,
        trust_class=trust_class,
        auth_mode=auth_mode,
        allowed_surfaces=_normalize_str_list(raw.get("allowed_surfaces")),
        allowed_kinds=_normalize_str_list(raw.get("allowed_kinds")),
        allow_live_chatgpt=bool(raw.get("allow_live_chatgpt", False)),
        allow_gemini_web=bool(raw.get("allow_gemini_web", False)),
        allow_qwen_web=bool(raw.get("allow_qwen_web", False)),
        allow_deep_research=bool(raw.get("allow_deep_research", False)),
        allow_pro=bool(raw.get("allow_pro", False)),
        codex_guard_mode=codex_guard_mode,
        notes=_normalize_text(raw.get("notes"), max_chars=500),
        shared_secret_env=_normalize_text(raw.get("shared_secret_env"), max_chars=200),
        enabled=bool(raw.get("enabled", True)),
        max_in_flight_jobs=max(0, int(raw.get("max_in_flight_jobs") or 0)),
        dedupe_window_seconds=max(0, int(raw.get("dedupe_window_seconds") or 0)),
    )


def _profiles_by_lookup() -> dict[str, AskClientProfile]:
    payload = _load_registry_payload()
    profiles_raw = payload.get("profiles")
    if not isinstance(profiles_raw, list):
        raise RuntimeError("ask client registry profiles must be a list")
    lookup: dict[str, AskClientProfile] = {}
    for item in profiles_raw:
        if not isinstance(item, dict):
            raise RuntimeError("ask client registry profiles must be objects")
        profile = _profile_from_payload(item)
        keys = (profile.client_id, *profile.aliases)
        for key in keys:
            existing = lookup.get(key)
            if existing is not None and existing.client_id != profile.client_id:
                raise RuntimeError(f"duplicate ask client registry key: {key}")
            if existing is not None:
                continue
            lookup[key] = profile
    return lookup


def _testclient_identity_exempt(request: Request, client_obj: dict[str, Any]) -> bool:
    user_agent = _normalize_token(request.headers.get("user-agent"))
    client_host = _normalize_token(getattr(request.client, "host", ""))
    header_client_name = _normalize_token(request.headers.get("x-client-name"))
    header_client_id = _normalize_token(request.headers.get("x-client-id"))
    body_client_name = _normalize_token(client_obj.get("name"))
    body_client_id = _normalize_token(client_obj.get("client_id") or client_obj.get("id"))
    return (
        "testclient" in user_agent
        and client_host == "testclient"
        and not header_client_name
        and not header_client_id
        and not body_client_name
        and not body_client_id
    )


def _body_identity(client_obj: dict[str, Any]) -> tuple[str, str]:
    return (
        _normalize_token(client_obj.get("client_id") or client_obj.get("id")),
        _normalize_token(client_obj.get("name")),
    )


def _resolve_client_profile(*, request: Request, client_obj: dict[str, Any]) -> tuple[AskClientProfile, dict[str, Any]]:
    if _testclient_identity_exempt(request, client_obj):
        raise HTTPException(status_code=418, detail={"error": "testclient_identity_exempt"})

    header_client_id = _normalize_token(request.headers.get("x-client-id"))
    header_client_name = _normalize_token(request.headers.get("x-client-name"))
    body_client_id, body_client_name = _body_identity(client_obj)
    lookup_key = header_client_id or header_client_name or body_client_id or body_client_name
    if not lookup_key:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "low_level_ask_client_identity_required",
                "error_type": "LowLevelAskClientIdentityRequired",
                "reason": "missing_low_level_ask_client_identity",
                "detail": "low-level web ask clients must declare a registered source identity",
                "hint": "Provide X-Client-Id or X-Client-Name for a registered ask client profile.",
            },
        )
    if header_client_name and body_client_name and header_client_name != body_client_name:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "low_level_ask_client_identity_mismatch",
                "error_type": "LowLevelAskClientIdentityMismatch",
                "reason": "header_and_body_client_name_mismatch",
                "detail": "X-Client-Name does not match body client.name",
                "x_client_name": header_client_name,
                "body_client_name": body_client_name,
            },
        )
    if header_client_id and body_client_id and header_client_id != body_client_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "low_level_ask_client_identity_mismatch",
                "error_type": "LowLevelAskClientIdentityMismatch",
                "reason": "header_and_body_client_id_mismatch",
                "detail": "X-Client-Id does not match body client.client_id",
                "x_client_id": header_client_id,
                "body_client_id": body_client_id,
            },
        )
    lookup = _profiles_by_lookup()
    profile = lookup.get(lookup_key)
    if profile is None:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "low_level_ask_client_not_registered",
                "error_type": "LowLevelAskClientNotRegistered",
                "reason": "low_level_ask_client_not_registered",
                "detail": "low-level web ask caller is not registered in the ask client registry",
                "lookup_key": lookup_key,
                "hint": f"Register the client in {_registry_path()} before using low-level ask.",
            },
        )
    declared_type = _normalize_token(request.headers.get("x-client-type") or client_obj.get("source_type"))
    if declared_type and declared_type != profile.source_type:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "low_level_ask_client_type_mismatch",
                "error_type": "LowLevelAskClientTypeMismatch",
                "reason": "declared_client_type_does_not_match_registry",
                "detail": "declared client type does not match registry source_type",
                "declared_client_type": declared_type,
                "registered_source_type": profile.source_type,
                "client_id": profile.client_id,
            },
        )
    audit = {
        "requested_lookup_key": lookup_key,
        "requested_name": header_client_name or body_client_name or None,
        "requested_client_id": header_client_id or body_client_id or None,
        "resolved_client_id": profile.client_id,
        "resolved_display_name": profile.display_name,
        "source_type": profile.source_type,
        "trust_class": profile.trust_class,
        "auth_mode": profile.auth_mode,
        "client_instance": _normalize_text(request.headers.get("x-client-instance")),
        "source_repo": _normalize_text(request.headers.get("x-source-repo"), max_chars=500),
        "source_entrypoint": _normalize_text(request.headers.get("x-source-entrypoint"), max_chars=500),
        "client_run_id": _normalize_text(request.headers.get("x-client-run-id"), max_chars=200),
    }
    return profile, audit


def _gc_nonce_cache(now: float) -> None:
    stale = [key for key, ts in _NONCE_CACHE.items() if now - ts > _NONCE_TTL_SECONDS]
    for key in stale:
        _NONCE_CACHE.pop(key, None)


def _verify_hmac_if_required(
    *,
    request: Request,
    body_payload: dict[str, Any],
    profile: AskClientProfile,
    audit: dict[str, Any],
) -> None:
    if profile.auth_mode != "hmac":
        return
    secret_env = profile.shared_secret_env
    secret = _normalize_text(os.environ.get(secret_env) or "", max_chars=4000)
    if not secret:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "low_level_ask_client_auth_unconfigured",
                "error_type": "LowLevelAskClientAuthUnconfigured",
                "reason": "shared_secret_missing",
                "detail": f"HMAC secret env {secret_env or '<unset>'} is not configured for registered client {profile.client_id}",
            },
        )
    timestamp_raw = _normalize_text(request.headers.get("x-client-timestamp"), max_chars=64)
    nonce = _normalize_text(request.headers.get("x-client-nonce"), max_chars=200)
    signature = _normalize_text(request.headers.get("x-client-signature"), max_chars=512)
    if not timestamp_raw or not nonce or not signature:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "low_level_ask_client_auth_failed",
                "error_type": "LowLevelAskClientAuthFailed",
                "reason": "missing_hmac_headers",
                "detail": "HMAC-authenticated ask client is missing timestamp/nonce/signature headers",
                "client_id": profile.client_id,
            },
        )
    try:
        timestamp = int(timestamp_raw)
    except Exception as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "low_level_ask_client_auth_failed",
                "error_type": "LowLevelAskClientAuthFailed",
                "reason": "invalid_hmac_timestamp",
                "detail": "x-client-timestamp must be an integer unix timestamp",
                "client_id": profile.client_id,
            },
        ) from exc
    now = int(time.time())
    if abs(now - timestamp) > _NONCE_TTL_SECONDS:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "low_level_ask_client_auth_failed",
                "error_type": "LowLevelAskClientAuthFailed",
                "reason": "stale_hmac_timestamp",
                "detail": "HMAC timestamp is outside the allowed skew window",
                "client_id": profile.client_id,
            },
        )
    _gc_nonce_cache(float(now))
    nonce_key = f"{profile.client_id}:{nonce}"
    if nonce_key in _NONCE_CACHE:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "low_level_ask_client_auth_failed",
                "error_type": "LowLevelAskClientAuthFailed",
                "reason": "replayed_hmac_nonce",
                "detail": "HMAC nonce was already used recently",
                "client_id": profile.client_id,
            },
        )
    canonical = "\n".join(
        [
            request.method.upper(),
            request.url.path,
            profile.client_id,
            _normalize_text(request.headers.get("x-client-instance"), max_chars=200),
            timestamp_raw,
            nonce,
            hashlib.sha256(_stable_json(body_payload).encode("utf-8", errors="replace")).hexdigest(),
        ]
    )
    expected = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "low_level_ask_client_auth_failed",
                "error_type": "LowLevelAskClientAuthFailed",
                "reason": "invalid_hmac_signature",
                "detail": "HMAC signature does not match request payload",
                "client_id": profile.client_id,
            },
        )
    _NONCE_CACHE[nonce_key] = float(now)
    audit["auth_method"] = "hmac"


def _is_json_only_prompt(text: str) -> bool:
    head = canonical_prompt_head(text).lower()
    return any(hint in head for hint in _STRUCTURED_OUTPUT_HINTS)


def _is_structured_microtask(text: str) -> bool:
    head = canonical_prompt_head(text).lower()
    return any(hint.lower() in head for hint in _MICROTASK_HINTS)


def _is_sufficiency_gate(text: str) -> bool:
    head = canonical_prompt_head(text).lower()
    return any(hint.lower() in head for hint in _SUFFICIENCY_HINTS)


def _is_pro_like_request(*, kind: str, preset: str, params_obj: dict[str, Any]) -> bool:
    p = _normalize_token(preset)
    if kind == "chatgpt_web.ask":
        return p in {"pro_extended", "thinking_heavy", "thinking_extended", "deep_research", "deep-research", "deepresearch", "research"}
    if kind == "gemini_web.ask":
        return p in {"pro", "deep_think", "deepthink", "deep_research"}
    if kind == "qwen_web.ask":
        return p in {"deep_thinking", "deep_research"}
    return False


def _deterministic_guard_decision(
    *,
    kind: str,
    question: str,
    params_obj: dict[str, Any],
    profile: AskClientProfile,
) -> dict[str, Any] | None:
    head = canonical_prompt_head(question)
    if not head:
        return {
            "decision": "block",
            "reason_code": "trivial_ping",
            "intent_class": "trivial_ping",
            "substantive": False,
            "allow_live_chatgpt": False,
            "allow_deep_research": False,
            "allow_pro": False,
            "short_answer_ok": False,
            "min_chars_override": 0,
            "remediation": "Provide a substantive user-facing ask instead of an empty prompt.",
            "notes": ["empty_prompt"],
        }
    if profile.trust_class == "testing_only" and kind == "chatgpt_web.ask":
        return {
            "decision": "block",
            "reason_code": "testing_client_live_chatgpt_blocked",
            "intent_class": "smoke_test",
            "substantive": False,
            "allow_live_chatgpt": False,
            "allow_deep_research": False,
            "allow_pro": False,
            "short_answer_ok": False,
            "min_chars_override": 0,
            "remediation": "Testing clients must use Gemini/Qwen or a mock path instead of live ChatGPT ask.",
            "notes": ["testing_only_client", "chatgpt_live_disallowed"],
        }
    if looks_like_live_chatgpt_smoke_prompt(head):
        return {
            "decision": "block",
            "reason_code": "synthetic_smoke",
            "intent_class": "smoke_test",
            "substantive": False,
            "allow_live_chatgpt": False,
            "allow_deep_research": False,
            "allow_pro": False,
            "short_answer_ok": True,
            "min_chars_override": 0,
            "remediation": "Use a mock path or non-live substrate for smoke/state probes.",
            "notes": ["synthetic_smoke_probe"],
        }
    if looks_like_trivial_pro_prompt(head):
        return {
            "decision": "block",
            "reason_code": "trivial_ping",
            "intent_class": "trivial_ping",
            "substantive": False,
            "allow_live_chatgpt": False,
            "allow_deep_research": False,
            "allow_pro": False,
            "short_answer_ok": True,
            "min_chars_override": 0,
            "remediation": "Use a substantive task instead of hello/test/ping style prompts.",
            "notes": ["trivial_prompt"],
        }
    if _is_sufficiency_gate(head):
        return {
            "decision": "block",
            "reason_code": "sufficiency_gate",
            "intent_class": "sufficiency_gate",
            "substantive": False,
            "allow_live_chatgpt": False,
            "allow_deep_research": False,
            "allow_pro": False,
            "short_answer_ok": True,
            "min_chars_override": 0,
            "remediation": "Pipeline sufficiency gates should not consume low-level live ask capacity.",
            "notes": ["sufficiency_gate"],
        }
    if _is_structured_microtask(head):
        return {
            "decision": "block",
            "reason_code": "structured_microtask",
            "intent_class": "structured_microtask",
            "substantive": False,
            "allow_live_chatgpt": False,
            "allow_deep_research": False,
            "allow_pro": False,
            "short_answer_ok": True,
            "min_chars_override": 0,
            "remediation": "Structured extraction microtasks should stay on dedicated non-public/non-live lanes.",
            "notes": ["structured_microtask"],
        }
    if _is_json_only_prompt(head) and profile.trust_class != "maintenance_internal":
        if profile.trust_class == "automation_registered" and profile.codex_guard_mode == "classify":
            return None
        return {
            "decision": "block",
            "reason_code": "json_only_extractor",
            "intent_class": "structured_microtask",
            "substantive": False,
            "allow_live_chatgpt": False,
            "allow_deep_research": False,
            "allow_pro": False,
            "short_answer_ok": True,
            "min_chars_override": 0,
            "remediation": "JSON-only extractors should not go through low-level live ask unless explicitly maintenance-scoped.",
            "notes": ["json_only_prompt"],
        }
    if bool((params_obj or {}).get("deep_research")) and len(head) < 120 and profile.trust_class != "maintenance_internal":
        return {
            "decision": "block",
            "reason_code": "unclear_intent_blocked",
            "intent_class": "unknown",
            "substantive": False,
            "allow_live_chatgpt": True,
            "allow_deep_research": False,
            "allow_pro": False,
            "short_answer_ok": False,
            "min_chars_override": None,
            "remediation": "Low-context direct asks should not request deep_research; use a richer agent turn or add substantive context.",
            "notes": ["deep_research_low_context"],
        }
    return None


def _codex_guard_enabled() -> bool:
    raw = _normalize_token(os.environ.get("CHATGPTREST_ASK_GUARD_CODEX_ENABLED") or "1")
    return raw not in {"0", "false", "no", "off"}


def _codex_guard_timeout_seconds() -> int:
    raw = _normalize_text(os.environ.get("CHATGPTREST_ASK_GUARD_CODEX_TIMEOUT_SECONDS") or "", max_chars=32)
    try:
        timeout = int(raw) if raw else 45
    except Exception:
        timeout = 45
    return max(10, min(timeout, 300))


def _ask_guard_prompt(*, kind: str, question: str, params_obj: dict[str, Any], profile: AskClientProfile, audit: dict[str, Any]) -> str:
    payload = {
        "kind": kind,
        "prompt_head": canonical_prompt_head(question),
        "prompt_chars": len(str(question or "")),
        "purpose": purpose_from_params(params_obj),
        "preset": _normalize_token(params_obj.get("preset")),
        "deep_research": bool((params_obj or {}).get("deep_research")),
        "profile": {
            "client_id": profile.client_id,
            "display_name": profile.display_name,
            "source_type": profile.source_type,
            "trust_class": profile.trust_class,
            "allowed_surfaces": list(profile.allowed_surfaces),
            "allowed_kinds": list(profile.allowed_kinds),
            "allow_live_chatgpt": profile.allow_live_chatgpt,
            "allow_deep_research": profile.allow_deep_research,
            "allow_pro": profile.allow_pro,
            "codex_guard_mode": profile.codex_guard_mode,
        },
        "audit": audit,
    }
    return (
        "You are the ingress safety reviewer for ChatgptREST low-level live ask requests.\n"
        "Judge whether a registered automation client is submitting a substantive human-like task, or an inappropriate "
        "microtask/smoke/trivial ask that should be blocked.\n"
        "Do not answer the user's task. Return JSON only that matches the provided schema.\n"
        "Prefer blocking ambiguous low-context automation asks instead of allowing them.\n\n"
        f"INPUT_JSON:\n{_stable_json(payload)}\n"
    )


def _normalize_codex_guard_output(raw: dict[str, Any] | None, *, profile: AskClientProfile) -> dict[str, Any]:
    payload = dict(raw or {})
    decision = _normalize_token(payload.get("decision"))
    if decision not in {"allow", "allow_with_limits", "block", "require_public_agent"}:
        raise RuntimeError(f"invalid ask guard decision: {decision or '<empty>'}")
    reason_code = _normalize_token(payload.get("reason_code"))
    intent_class = _normalize_token(payload.get("intent_class"))
    notes = payload.get("notes")
    if not isinstance(notes, list):
        notes = []
    return {
        "decision": decision,
        "reason_code": reason_code or "unclear_intent_blocked",
        "intent_class": intent_class or "unknown",
        "substantive": bool(payload.get("substantive", False)),
        "allow_live_chatgpt": bool(payload.get("allow_live_chatgpt", profile.allow_live_chatgpt)),
        "allow_deep_research": bool(payload.get("allow_deep_research", profile.allow_deep_research)),
        "allow_pro": bool(payload.get("allow_pro", profile.allow_pro)),
        "short_answer_ok": bool(payload.get("short_answer_ok", False)),
        "min_chars_override": payload.get("min_chars_override"),
        "remediation": _normalize_text(payload.get("remediation"), max_chars=400) or None,
        "notes": [_normalize_text(item, max_chars=200) for item in notes if _normalize_text(item, max_chars=200)],
    }


def _codex_guard_decision(
    *,
    kind: str,
    question: str,
    params_obj: dict[str, Any],
    profile: AskClientProfile,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if not _codex_guard_enabled():
        raise RuntimeError("Codex ask guard is disabled")
    with tempfile.TemporaryDirectory(prefix="chatgptrest-ask-guard-") as tmpdir:
        tmp_path = Path(tmpdir)
        out_json = tmp_path / "decision.json"
        result = codex_exec_with_schema(
            prompt=_ask_guard_prompt(kind=kind, question=question, params_obj=params_obj, profile=profile, audit=audit),
            schema_path=_SCHEMA_PATH,
            out_json=out_json,
            timeout_seconds=_codex_guard_timeout_seconds(),
            cd=_REPO_ROOT,
            sandbox="read-only",
        )
    if not result.ok:
        raise RuntimeError(str(result.error or result.stderr or "codex ask guard failed"))
    return _normalize_codex_guard_output(result.output or {}, profile=profile)


def _authorization_violation(*, error: str, reason: str, detail: str, profile: AskClientProfile, audit: dict[str, Any], status_code: int = 403, hint: str = "") -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": error,
            "error_type": "".join(part.capitalize() for part in error.split("_")),
            "reason": reason,
            "detail": detail,
            "client_id": profile.client_id,
            "source_type": profile.source_type,
            "trust_class": profile.trust_class,
            "requested_client_name": audit.get("requested_name"),
            "hint": hint or None,
        },
    )


def _require_automation_hard_auth(*, profile: AskClientProfile, audit: dict[str, Any]) -> None:
    if profile.trust_class != "automation_registered":
        return
    if "low_level_jobs" not in profile.allowed_surfaces:
        return
    if profile.auth_mode == "hmac":
        return
    raise _authorization_violation(
        error="low_level_ask_registry_misconfigured",
        reason="automation_low_level_jobs_requires_hmac",
        detail="registered automation low-level ask clients must use HMAC authentication",
        profile=profile,
        audit=audit,
        status_code=500,
        hint="Move the client to public advisor-agent MCP, or upgrade the low-level ask profile to auth_mode=hmac.",
    )


def _safe_non_pro_preset(kind: str) -> str | None:
    normalized_kind = _normalize_token(kind)
    if normalized_kind in {"chatgpt_web.ask", "qwen_web.ask"}:
        return "auto"
    return None


def _interactive_client_low_level_block(*, kind: str, profile: AskClientProfile, audit: dict[str, Any]) -> HTTPException:
    normalized_kind = _normalize_token(kind)
    requested_name = audit.get("requested_name")
    if normalized_kind == "chatgpt_web.ask":
        return HTTPException(
            status_code=403,
            detail={
                "error": "direct_live_chatgpt_ask_blocked",
                "error_type": "DirectLiveChatgptAskBlocked",
                "reason": "interactive_client_must_use_public_agent",
                "detail": "interactive coding clients must use public advisor-agent MCP instead of direct /v1/jobs chatgpt_web.ask",
                "x_client_name": requested_name or profile.client_id,
                "client_id": profile.client_id,
                "trust_class": profile.trust_class,
                "hint": "Use advisor_agent_turn/status/cancel/wait on http://127.0.0.1:18712/mcp. Maintenance exceptions must use a maintenance-registered client instead of params.allow_direct_live_chatgpt_ask.",
            },
        )
    if normalized_kind in {"gemini_web.ask", "qwen_web.ask"}:
        return HTTPException(
            status_code=403,
            detail={
                "error": "coding_agent_low_level_ask_blocked",
                "error_type": "CodingAgentLowLevelAskBlocked",
                "reason": "interactive_client_must_use_public_agent",
                "detail": "interactive coding clients must use public advisor-agent MCP instead of low-level /v1/jobs ask calls",
                "kind": normalized_kind,
                "x_client_name": requested_name or profile.client_id,
                "client_id": profile.client_id,
                "trust_class": profile.trust_class,
                "hint": "Use the public advisor-agent MCP (advisor_agent_turn/status/cancel/wait) instead of low-level /v1/jobs ask calls.",
            },
        )
    return _authorization_violation(
        error="low_level_ask_use_public_agent",
        reason="interactive_client_must_use_public_agent",
        detail="interactive coding clients must use public advisor-agent MCP instead of low-level ask",
        profile=profile,
        audit=audit,
        hint="Use advisor_agent_turn/status/cancel/wait on http://127.0.0.1:18712/mcp.",
    )


def _runtime_prompt_fingerprint(*, kind: str, input_obj: dict[str, Any], params_obj: dict[str, Any]) -> str:
    payload = {
        "kind": _normalize_token(kind),
        "question": _normalize_text(input_obj.get("question") or input_obj.get("prompt"), max_chars=12000),
        "github_repo": _normalize_text(input_obj.get("github_repo"), max_chars=500),
        "parent_job_id": _normalize_text(input_obj.get("parent_job_id"), max_chars=200),
        "file_paths": [str(item).strip() for item in list(input_obj.get("file_paths") or []) if str(item).strip()],
        "preset": _normalize_token(params_obj.get("preset")),
        "deep_research": bool(params_obj.get("deep_research") or False),
    }
    return hashlib.sha256(_stable_json(payload).encode("utf-8", errors="replace")).hexdigest()


def enforce_low_level_ask_runtime_controls(
    *,
    conn: Any,
    kind: str,
    input_obj: dict[str, Any],
    params_obj: dict[str, Any],
    guard_payload: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(guard_payload, dict) or not guard_payload or guard_payload.get("identity_exempt"):
        return dict(guard_payload or {})
    profile = dict(guard_payload)
    client_id = _normalize_token(profile.get("resolved_client_id"))
    if not client_id:
        return dict(guard_payload)
    runtime_control = dict(profile.get("runtime_control") or {})
    enabled = bool(runtime_control.get("enabled", True))
    if not enabled:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "low_level_ask_client_disabled",
                "error_type": "LowLevelAskClientDisabled",
                "reason": "registered_low_level_ask_client_disabled",
                "detail": "registered low-level ask client is currently disabled",
                "client_id": client_id,
            },
        )

    max_in_flight_jobs = max(0, int(runtime_control.get("max_in_flight_jobs") or 0))
    if max_in_flight_jobs > 0:
        rows = conn.execute(
            """
            SELECT job_id, status
              FROM jobs
             WHERE kind IN ('chatgpt_web.ask', 'gemini_web.ask', 'qwen_web.ask')
               AND json_extract(client_json, '$.name') = ?
               AND status IN ('queued', 'in_progress')
             ORDER BY created_at ASC
            """,
            (client_id,),
        ).fetchall()
        if len(rows) >= max_in_flight_jobs:
            active_job_ids = [str(row[0]) for row in list(rows)[:5] if str(row[0] or "").strip()]
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "low_level_ask_client_concurrency_exceeded",
                    "error_type": "LowLevelAskClientConcurrencyExceeded",
                    "reason": "registered_client_max_in_flight_exceeded",
                    "detail": "registered low-level ask client has reached its in-flight limit",
                    "client_id": client_id,
                    "max_in_flight_jobs": max_in_flight_jobs,
                    "active_job_ids": active_job_ids,
                },
            )

    dedupe_window_seconds = max(0, int(runtime_control.get("dedupe_window_seconds") or 0))
    prompt_fingerprint = _runtime_prompt_fingerprint(kind=kind, input_obj=input_obj, params_obj=params_obj)
    runtime_control["prompt_fingerprint"] = prompt_fingerprint
    if dedupe_window_seconds > 0 and prompt_fingerprint:
        row = conn.execute(
            """
            SELECT job_id, status, created_at
              FROM jobs
             WHERE kind = ?
               AND json_extract(client_json, '$.name') = ?
               AND created_at >= ?
               AND status NOT IN ('error', 'canceled')
               AND json_extract(params_json, '$.ask_guard.runtime_control.prompt_fingerprint') = ?
             ORDER BY created_at DESC
             LIMIT 1
            """,
            (str(kind), client_id, float(time.time()) - float(dedupe_window_seconds), prompt_fingerprint),
        ).fetchone()
        if row is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "low_level_ask_duplicate_recently_submitted",
                    "error_type": "LowLevelAskDuplicateRecentlySubmitted",
                    "reason": "duplicate_recent_low_level_ask",
                    "detail": "registered low-level ask client already submitted an equivalent request recently",
                    "client_id": client_id,
                    "existing_job_id": str(row[0] or ""),
                    "existing_status": str(row[1] or ""),
                    "dedupe_window_seconds": dedupe_window_seconds,
                },
            )

    out = dict(guard_payload)
    out["runtime_control"] = runtime_control
    return out


def enforce_low_level_ask_identity_and_policy(
    *,
    request: Request,
    body_payload: dict[str, Any],
    kind: str,
    input_obj: dict[str, Any],
    params_obj: dict[str, Any],
    client_obj: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not is_web_ask_kind(kind):
        return (dict(client_obj or {}), {})
    client_payload = dict(client_obj or {})
    try:
        profile, audit = _resolve_client_profile(request=request, client_obj=client_payload)
    except HTTPException as exc:
        if exc.status_code == 418:
            return (client_payload, {"identity_exempt": "testclient"})
        raise
    _verify_hmac_if_required(request=request, body_payload=body_payload, profile=profile, audit=audit)
    kind_l = _normalize_token(kind)
    if profile.trust_class == "interactive_trusted":
        raise _interactive_client_low_level_block(kind=kind_l, profile=profile, audit=audit)
    _require_automation_hard_auth(profile=profile, audit=audit)
    if "low_level_jobs" not in profile.allowed_surfaces:
        raise _authorization_violation(
            error="low_level_ask_surface_not_allowed",
            reason="client_surface_not_registered_for_low_level_jobs",
            detail="registered client is not allowed to use low-level ask jobs",
            profile=profile,
            audit=audit,
            hint="Use the public advisor-agent MCP or a maintenance-scoped lane instead.",
        )
    if profile.allowed_kinds and kind_l not in profile.allowed_kinds:
        raise _authorization_violation(
            error="low_level_ask_kind_not_allowed",
            reason="client_kind_not_registered",
            detail=f"registered client is not allowed to submit {kind}",
            profile=profile,
            audit=audit,
        )
    preset = _normalize_token(params_obj.get("preset"))
    if kind_l == "chatgpt_web.ask" and not profile.allow_live_chatgpt:
        raise _authorization_violation(
            error="low_level_ask_live_chatgpt_not_allowed",
            reason="client_not_allowed_for_live_chatgpt",
            detail="registered client is not allowed to create live ChatGPT ask jobs",
            profile=profile,
            audit=audit,
            hint="Use Gemini/Qwen or move the task to public advisor-agent MCP.",
        )
    if kind_l == "gemini_web.ask" and not profile.allow_gemini_web:
        raise _authorization_violation(
            error="low_level_ask_provider_not_allowed",
            reason="client_not_allowed_for_gemini_web",
            detail="registered client is not allowed to create Gemini web ask jobs",
            profile=profile,
            audit=audit,
        )
    if kind_l == "qwen_web.ask" and not profile.allow_qwen_web:
        raise _authorization_violation(
            error="low_level_ask_provider_not_allowed",
            reason="client_not_allowed_for_qwen_web",
            detail="registered client is not allowed to create Qwen web ask jobs",
            profile=profile,
            audit=audit,
        )
    if bool((params_obj or {}).get("deep_research")) and not profile.allow_deep_research:
        raise _authorization_violation(
            error="low_level_ask_deep_research_not_allowed",
            reason="client_not_allowed_for_deep_research",
            detail="registered client is not allowed to request deep_research on low-level ask",
            profile=profile,
            audit=audit,
        )
    if _is_pro_like_request(kind=kind_l, preset=preset, params_obj=params_obj) and not profile.allow_pro:
        raise _authorization_violation(
            error="low_level_ask_pro_not_allowed",
            reason="client_not_allowed_for_pro_preset",
            detail="registered client is not allowed to use Pro/Thinking style presets on low-level ask",
            profile=profile,
            audit=audit,
        )
    question = _normalize_text(input_obj.get("question") or input_obj.get("prompt"), max_chars=200000)
    decision = _deterministic_guard_decision(kind=kind_l, question=question, params_obj=params_obj, profile=profile)
    if decision is None and profile.codex_guard_mode == "classify":
        try:
            decision = _codex_guard_decision(kind=kind_l, question=question, params_obj=params_obj, profile=profile, audit=audit)
        except Exception as exc:
            raise _authorization_violation(
                error="low_level_ask_codex_guard_unavailable",
                reason="codex_guard_failed_closed",
                detail=f"Codex ask guard failed closed: {str(exc)[:400]}",
                profile=profile,
                audit=audit,
                status_code=503,
                hint="Retry after restoring Codex guard availability, or use a maintenance-scoped lane.",
            ) from exc
    if decision is None:
        decision = {
            "decision": "allow",
            "reason_code": ("maintenance_bypass" if profile.trust_class == "maintenance_internal" else "substantive_registered_automation"),
            "intent_class": ("maintenance" if profile.trust_class == "maintenance_internal" else "substantive_human_like_task"),
            "substantive": True,
            "allow_live_chatgpt": profile.allow_live_chatgpt,
            "allow_deep_research": profile.allow_deep_research,
            "allow_pro": profile.allow_pro,
            "short_answer_ok": False,
            "min_chars_override": None,
            "remediation": None,
            "notes": ["deterministic_allow"],
        }
    if decision["decision"] in {"block", "require_public_agent"}:
        error = (
            "low_level_ask_use_public_agent"
            if decision["decision"] == "require_public_agent"
            else "low_level_ask_intent_blocked"
        )
        raise _authorization_violation(
            error=error,
            reason=str(decision.get("reason_code") or "low_level_ask_intent_blocked"),
            detail="low-level ask request was rejected by registered client policy",
            profile=profile,
            audit=audit,
            hint=str(decision.get("remediation") or ""),
        )
    normalized_client = dict(client_payload)
    normalized_client["name"] = profile.client_id
    normalized_client["client_id"] = profile.client_id
    normalized_client["display_name"] = profile.display_name
    normalized_client["source_type"] = profile.source_type
    normalized_client["trust_class"] = profile.trust_class
    normalized_client["auth_mode"] = profile.auth_mode
    normalized_client["requested_name"] = audit.get("requested_name")
    if audit.get("client_instance"):
        normalized_client["instance"] = audit["client_instance"]
    if audit.get("source_repo"):
        normalized_client["source_repo"] = audit["source_repo"]
    if audit.get("source_entrypoint"):
        normalized_client["source_entrypoint"] = audit["source_entrypoint"]
    if audit.get("client_run_id"):
        normalized_client["client_run_id"] = audit["client_run_id"]
    guard_payload = {
        "registry_version": int(_load_registry_payload().get("version") or 1),
        "resolved_client_id": profile.client_id,
        "display_name": profile.display_name,
        "source_type": profile.source_type,
        "trust_class": profile.trust_class,
        "auth_mode": profile.auth_mode,
        "auth_method": audit.get("auth_method") or profile.auth_mode,
        "requested_name": audit.get("requested_name"),
        "requested_client_id": audit.get("requested_client_id"),
        "client_instance": audit.get("client_instance"),
        "source_repo": audit.get("source_repo"),
        "source_entrypoint": audit.get("source_entrypoint"),
        "client_run_id": audit.get("client_run_id"),
        "decision": decision,
        "runtime_control": {
            "enabled": bool(profile.enabled),
            "max_in_flight_jobs": int(profile.max_in_flight_jobs),
            "dedupe_window_seconds": int(profile.dedupe_window_seconds),
        },
    }
    return normalized_client, guard_payload


def apply_low_level_ask_guard_limits(
    *,
    kind: str,
    params_obj: dict[str, Any],
    guard_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    params = dict(params_obj or {})
    guard = dict(guard_payload or {})
    decision = dict(guard.get("decision") or {})
    if _normalize_token(decision.get("decision")) != "allow_with_limits":
        return params, {}

    applied: dict[str, Any] = {}
    normalized_kind = _normalize_token(kind)
    if not bool(decision.get("allow_deep_research", True)) and bool(params.get("deep_research") or False):
        params["deep_research"] = False
        applied["deep_research"] = False

    preset = _normalize_token(params.get("preset"))
    if not bool(decision.get("allow_pro", True)) and _is_pro_like_request(kind=normalized_kind, preset=preset, params_obj=params):
        fallback_preset = _safe_non_pro_preset(normalized_kind)
        if not fallback_preset:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "low_level_ask_limit_unenforceable",
                    "error_type": "LowLevelAskLimitUnenforceable",
                    "reason": "allow_with_limits_requires_unavailable_non_pro_preset",
                    "detail": "ask guard requested a non-Pro downgrade for a provider that does not expose a non-Pro low-level preset",
                    "kind": normalized_kind,
                    "resolved_client_id": guard.get("resolved_client_id"),
                    "hint": "Block the request instead, or use a provider/lane with a non-Pro preset.",
                },
            )
        params["preset"] = fallback_preset
        applied["preset"] = fallback_preset

    min_chars_override = decision.get("min_chars_override")
    if isinstance(min_chars_override, int):
        min_chars = max(0, int(min_chars_override))
        params["min_chars"] = min_chars
        applied["min_chars"] = min_chars
    elif bool(decision.get("short_answer_ok", False)):
        params["min_chars"] = 0
        applied["min_chars"] = 0

    return params, applied
