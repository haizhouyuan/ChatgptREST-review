from __future__ import annotations

import re
from typing import Any

from chatgptrest.providers.policy import policy_from_config
from chatgptrest.providers.spec import ProviderSpec


class PresetValidationError(ValueError):
    def __init__(self, detail: Any) -> None:
        super().__init__("invalid preset")
        self.detail = detail


_COMMON_PRESET_ALIASES: dict[str, str] = {
    "default": "auto",
    "defaults": "auto",
}

_CHATGPT_PRESET_ALIASES: dict[str, str] = {
    **_COMMON_PRESET_ALIASES,
    # Compatibility: allow callers to express DR intent via preset string.
    "research": "deep_research",
    "deep_research": "deep_research",
    "deep-research": "deep_research",
    "deepresearch": "deep_research",
}

_GEMINI_PRESET_ALIASES: dict[str, str] = {
    # Policy: do not allow clients to force Gemini's "Thinking" mode.
    # We normalize common aliases to `pro` so callers only effectively choose:
    # - `pro`
    # - `deep_think`
    "default": "pro",
    "defaults": "pro",
    "auto": "pro",
    # Compatibility: allow ChatGPT-style and shorthand strings (normalized to `pro`).
    "thinking": "pro",
    "prothinking": "pro",
    "pro_thinking": "pro",
    "pro_extended": "pro",
    "thinking_heavy": "pro",
    "thinking_extended": "pro",
    "gemini_pro": "pro",
    "deepthink": "deep_think",
    "prodeepthink": "deep_think",
    "pro_deep_think": "deep_think",
}

_PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        provider_id="chatgpt",
        kind_namespace="chatgpt_web.",
        ask_kind="chatgpt_web.ask",
        rate_limit_key="chatgpt_web_send",
        min_interval_attr="min_prompt_interval_seconds",
        supported_presets=frozenset({"auto", "pro_extended", "thinking_heavy", "thinking_extended", "deep_research"}),
        preset_aliases=_CHATGPT_PRESET_ALIASES,
    ),
    ProviderSpec(
        provider_id="gemini",
        kind_namespace="gemini_web.",
        ask_kind="gemini_web.ask",
        rate_limit_key="gemini_web_send",
        min_interval_attr="gemini_min_prompt_interval_seconds",
        supported_presets=frozenset({"pro", "deep_think"}),
        preset_aliases=_GEMINI_PRESET_ALIASES,
    ),
)

_SPEC_BY_ASK_KIND: dict[str, ProviderSpec] = {spec.ask_kind: spec for spec in _PROVIDER_SPECS}
_SPEC_BY_NAMESPACE: dict[str, ProviderSpec] = {spec.kind_namespace: spec for spec in _PROVIDER_SPECS}
_WEB_ASK_KINDS: frozenset[str] = frozenset(_SPEC_BY_ASK_KIND.keys())
_WORKER_AUTOFIX_KINDS: frozenset[str] = frozenset([*_WEB_ASK_KINDS, "gemini_web.generate_image"])
_REMOVED_ASK_KINDS: frozenset[str] = frozenset({"qwen_web.ask"})

_GEMINI_THREAD_URL_RE = re.compile(r"https?://(?:[^/]*\.)?gemini\.google\.com/app/[0-9a-zA-Z_-]{8,}", re.I)


def provider_specs() -> tuple[ProviderSpec, ...]:
    return _PROVIDER_SPECS


def web_ask_kinds() -> frozenset[str]:
    return _WEB_ASK_KINDS


def is_web_ask_kind(kind: str | None) -> bool:
    return str(kind or "").strip() in _WEB_ASK_KINDS


def is_worker_autofix_kind(kind: str | None) -> bool:
    return str(kind or "").strip().lower() in _WORKER_AUTOFIX_KINDS


def provider_spec_for_ask_kind(kind: str | None) -> ProviderSpec | None:
    return _SPEC_BY_ASK_KIND.get(str(kind or "").strip())


def provider_spec_for_kind(kind: str | None) -> ProviderSpec | None:
    raw = str(kind or "").strip()
    for namespace, spec in _SPEC_BY_NAMESPACE.items():
        if raw.startswith(namespace):
            return spec
    return None


def is_provider_web_kind(kind: str | None) -> bool:
    return provider_spec_for_kind(kind) is not None


def provider_id_for_kind(kind: str | None) -> str | None:
    """Return the provider id (e.g. 'chatgpt', 'gemini') for a given kind.

    Wraps ``provider_spec_for_kind`` for use in dedup callsites that only
    need the id string.
    """
    spec = provider_spec_for_kind(kind)
    return spec.provider_id if spec is not None else None


# Mapping from provider_id → user-facing conversation platform name.
_PROVIDER_PLATFORM: dict[str, str] = {
    "chatgpt": "chatgpt",
    "gemini": "gemini",
}


def conversation_platform(kind: str | None) -> str:
    """Return the conversation platform name for a given kind.

    Falls back to ``'unknown'`` when the kind is not recognised.
    """
    pid = provider_id_for_kind(kind)
    if pid is None:
        return "unknown"
    return _PROVIDER_PLATFORM.get(pid, pid)


def ask_rate_limit_key(kind: str | None) -> str | None:
    spec = provider_spec_for_ask_kind(kind)
    return spec.rate_limit_key if spec is not None else None


def ask_min_prompt_interval_seconds(*, cfg: Any, kind: str | None) -> int | None:
    spec = provider_spec_for_ask_kind(kind)
    if spec is None:
        return None
    return policy_from_config(cfg=cfg, spec=spec).min_prompt_interval_seconds


def looks_like_thread_url(kind: str, url: str | None) -> bool:
    raw = str(url or "").strip().lower()
    if not raw:
        return False
    spec = provider_spec_for_ask_kind(kind)
    if spec is None:
        return False
    if spec.provider_id == "chatgpt":
        return "/c/" in raw
    if spec.provider_id == "gemini":
        return bool(_GEMINI_THREAD_URL_RE.search(raw))
    return False


def validate_ask_preset(*, kind: str, params_obj: Any) -> None:
    kind_l = str(kind or "").strip().lower()
    if kind_l in _REMOVED_ASK_KINDS:
        raise PresetValidationError(
            {
                "error": "provider_removed",
                "detail": f"{kind_l} has been retired and is no longer available",
                "hint": "Use chatgpt_web.ask or gemini_web.ask instead.",
            },
        )
    spec = provider_spec_for_ask_kind(kind)
    if spec is None:
        return
    if not isinstance(params_obj, dict):
        raise PresetValidationError("params must be an object")
    raw = params_obj.get("preset")
    if not isinstance(raw, str) or not raw.strip():
        raise PresetValidationError(
            {
                "error": "missing_preset",
                "detail": f"params.preset is required for {spec.ask_kind} (no server-side default)",
                "supported": sorted(spec.supported_presets),
            },
        )
    preset = spec.normalize_preset(raw)
    if preset not in spec.supported_presets:
        raise PresetValidationError(
            {
                "error": "invalid_preset",
                "detail": f"unsupported params.preset for {spec.ask_kind}: {raw!r}",
                "supported": sorted(spec.supported_presets),
            },
        )
    if kind == "chatgpt_web.ask" and preset == "deep_research":
        # ChatGPT DR is driven by an explicit deep_research flag in executor params.
        # Keep internal preset canonicalized for existing policy/guard logic.
        params_obj["deep_research"] = True
        params_obj["preset"] = "thinking_heavy"
        return
    params_obj["preset"] = preset
