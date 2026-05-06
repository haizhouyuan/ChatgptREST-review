from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Any

_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)

# Proxy environment variables are process-global. This guard must be safe under overlapping
# contexts (nested or concurrent async tasks): only restore the baseline once the last
# suppression context exits.
_PROXY_ENV_LOCK = threading.Lock()
_PROXY_ENV_DISABLE_COUNT = 0
_PROXY_ENV_BASELINE: dict[str, str] = {}


def _proxy_env_for_subprocess() -> dict[str, str]:
    """Return the baseline proxy env when suppression is active.

    Callers typically build a subprocess env from `dict(os.environ)`; when suppression is
    active, the proxy keys are removed from `os.environ`, so we re-inject the baseline here.
    """

    with _PROXY_ENV_LOCK:
        if _PROXY_ENV_DISABLE_COUNT <= 0 or not _PROXY_ENV_BASELINE:
            return {}
        return {k: v for k, v in _PROXY_ENV_BASELINE.items() if v}


@contextmanager
def _without_proxy_env() -> Any:
    global _PROXY_ENV_BASELINE, _PROXY_ENV_DISABLE_COUNT

    with _PROXY_ENV_LOCK:
        if _PROXY_ENV_DISABLE_COUNT == 0:
            baseline: dict[str, str] = {k: os.environ.get(k, "") for k in _PROXY_ENV_KEYS if k in os.environ}
            for key in _PROXY_ENV_KEYS:
                os.environ.pop(key, None)
            _PROXY_ENV_BASELINE = baseline
        _PROXY_ENV_DISABLE_COUNT += 1

    try:
        yield
    finally:
        with _PROXY_ENV_LOCK:
            _PROXY_ENV_DISABLE_COUNT = max(0, _PROXY_ENV_DISABLE_COUNT - 1)
            if _PROXY_ENV_DISABLE_COUNT != 0:
                return

            baseline = dict(_PROXY_ENV_BASELINE)
            _PROXY_ENV_BASELINE = {}
            for key in _PROXY_ENV_KEYS:
                os.environ.pop(key, None)
            for key, value in baseline.items():
                os.environ[key] = value
