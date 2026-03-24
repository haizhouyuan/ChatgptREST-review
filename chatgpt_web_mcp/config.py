from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from chatgpt_web_mcp.env import _truthy_env


@dataclass(frozen=True)
class ChatGPTWebConfig:
    url: str
    storage_state_path: Path
    cdp_url: str | None
    headless: bool
    viewport_width: int
    viewport_height: int
    proxy_server: str | None
    proxy_username: str | None
    proxy_password: str | None


def _load_config() -> ChatGPTWebConfig:
    url = os.environ.get("CHATGPT_WEB_URL", "https://chatgpt.com/")
    storage_state = Path(os.environ.get("CHATGPT_STORAGE_STATE", "secrets/storage_state.json")).expanduser().resolve()
    cdp_url = os.environ.get("CHATGPT_CDP_URL") or None
    headless = _truthy_env("CHATGPT_HEADLESS", True)
    viewport_width = int(os.environ.get("CHATGPT_VIEWPORT_WIDTH", "1280"))
    viewport_height = int(os.environ.get("CHATGPT_VIEWPORT_HEIGHT", "720"))

    proxy_server = os.environ.get("CHATGPT_PROXY_SERVER")
    if not proxy_server:
        proxy_server = os.environ.get("ALL_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    proxy_username = os.environ.get("CHATGPT_PROXY_USERNAME")
    proxy_password = os.environ.get("CHATGPT_PROXY_PASSWORD")

    return ChatGPTWebConfig(
        url=url,
        storage_state_path=storage_state,
        cdp_url=cdp_url,
        headless=headless,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        proxy_server=proxy_server,
        proxy_username=proxy_username,
        proxy_password=proxy_password,
    )
