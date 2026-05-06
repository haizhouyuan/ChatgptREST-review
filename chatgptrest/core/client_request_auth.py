from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_REGISTRY_PATH = (_REPO_ROOT / "ops" / "policies" / "ask_client_registry.json").resolve()
_REGISTRY_CACHE: tuple[str, float, dict[str, Any]] | None = None


@dataclass(frozen=True)
class RegisteredClientAuthProfile:
    client_id: str
    aliases: tuple[str, ...]
    auth_mode: str
    shared_secret_env: str


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


def _profile_from_payload(raw: dict[str, Any]) -> RegisteredClientAuthProfile:
    client_id = _normalize_token(raw.get("client_id"))
    if not client_id:
        raise RuntimeError("ask client registry profile missing client_id")
    return RegisteredClientAuthProfile(
        client_id=client_id,
        aliases=_normalize_str_list(raw.get("aliases")),
        auth_mode=_normalize_token(raw.get("auth_mode") or "registry"),
        shared_secret_env=_normalize_text(raw.get("shared_secret_env"), max_chars=200),
    )


def resolve_registered_client_auth_profile(client_lookup: str | None) -> RegisteredClientAuthProfile | None:
    lookup_key = _normalize_token(client_lookup)
    if not lookup_key:
        return None
    payload = _load_registry_payload()
    profiles_raw = payload.get("profiles")
    if not isinstance(profiles_raw, list):
        raise RuntimeError("ask client registry profiles must be a list")
    for item in profiles_raw:
        if not isinstance(item, dict):
            continue
        profile = _profile_from_payload(item)
        if lookup_key == profile.client_id or lookup_key in profile.aliases:
            return profile
    return None


def build_registered_client_hmac_headers(
    *,
    client_lookup: str | None,
    client_instance: str | None,
    method: str,
    path: str,
    body_payload: Any = None,
    environ: Mapping[str, str] | None = None,
    now_ts: int | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    profile = resolve_registered_client_auth_profile(client_lookup)
    if profile is None or profile.auth_mode != "hmac":
        return {}
    env_map = environ if environ is not None else os.environ
    secret_env = profile.shared_secret_env
    secret = _normalize_text(env_map.get(secret_env) if secret_env else "", max_chars=4000)
    if not secret:
        raise RuntimeError(
            f"HMAC secret env {secret_env or '<unset>'} is not configured for registered client {profile.client_id}"
        )
    normalized_instance = _normalize_text(client_instance, max_chars=200)
    timestamp_raw = str(int(now_ts if now_ts is not None else time.time()))
    normalized_nonce = _normalize_text(nonce or uuid.uuid4().hex, max_chars=200)
    body_hash = hashlib.sha256(_stable_json(body_payload or {}).encode("utf-8", errors="replace")).hexdigest()
    canonical = "\n".join(
        [
            str(method or "").upper(),
            str(path or "").strip() or "/",
            profile.client_id,
            normalized_instance,
            timestamp_raw,
            normalized_nonce,
            body_hash,
        ]
    )
    signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "X-Client-Id": profile.client_id,
        "X-Client-Timestamp": timestamp_raw,
        "X-Client-Nonce": normalized_nonce,
        "X-Client-Signature": signature,
    }
