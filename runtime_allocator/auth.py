"""Simple API key authentication for the Paperclip service layer.

Production should replace this with JWT or OAuth2.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Header, HTTPException, status


_API_KEYS: dict[str, str] = {}


def _load_api_keys():
    """Load API keys from env var PAPERCLIP_API_KEYS (comma-separated key:role pairs)."""
    global _API_KEYS
    raw = os.getenv("PAPERCLIP_API_KEYS", "")
    if not raw:
        # Default dev key
        _API_KEYS = {"dev-key": "admin"}
        return
    for pair in raw.split(","):
        if ":" in pair:
            key, role = pair.strip().split(":", 1)
            _API_KEYS[key] = role
        else:
            _API_KEYS[pair.strip()] = "user"


def _ensure_loaded():
    if not _API_KEYS:
        _load_api_keys()


def require_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """FastAPI dependency: validate API key and return role."""
    _ensure_loaded()
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )
    if x_api_key not in _API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
    return _API_KEYS[x_api_key]


def require_admin(x_api_key: Optional[str] = Header(None)) -> str:
    """FastAPI dependency: require admin role."""
    role = require_api_key(x_api_key)
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return role
