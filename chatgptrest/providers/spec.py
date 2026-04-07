from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    kind_namespace: str
    ask_kind: str
    rate_limit_key: str
    min_interval_attr: str
    supported_presets: frozenset[str] = field(default_factory=frozenset)
    preset_aliases: Mapping[str, str] = field(default_factory=dict)

    def normalize_preset(self, value: str) -> str:
        raw = str(value or "").strip().lower()
        if not raw:
            return ""
        raw = re.sub(r"[\s\-]+", "_", raw).strip("_")
        return str(self.preset_aliases.get(raw, raw))
