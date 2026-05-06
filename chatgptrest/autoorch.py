from __future__ import annotations

"""Compatibility wrapper for the old autoorch module name.

`finbot` is now the canonical OpenClaw investment-research agent identity.
Keep this module as a thin alias so older scripts and tests do not break
while the runtime migrates from `autoorch` to `finbot`.
"""

from chatgptrest.finbot import (  # noqa: F401
    DEFAULT_FINAGENT_PYTHON,
    DEFAULT_FINAGENT_ROOT,
    DEFAULT_FINBOT_ROOT,
    InboxItem,
    ack_inbox_item,
    ensure_inbox_dirs,
    list_inbox,
    refresh_dashboard_projection,
    render_inbox_markdown,
    watchlist_scout,
    write_inbox_item,
)

DEFAULT_AUTOORCH_ROOT = DEFAULT_FINBOT_ROOT
