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
    default_preset: str = ""
    has_true_non_pro: bool = False
    auto_semantics: str = "unsupported"
    safe_non_pro_fallback: str | None = None
    deep_research_support: str = "none"
    premium_presets: frozenset[str] = field(default_factory=frozenset)
    supported_presets: frozenset[str] = field(default_factory=frozenset)
    preset_aliases: Mapping[str, str] = field(default_factory=dict)

    def normalize_preset(self, value: str) -> str:
        raw = str(value or "").strip().lower()
        if not raw:
            return ""
        raw = re.sub(r"[\s\-]+", "_", raw).strip("_")
        return str(self.preset_aliases.get(raw, raw))

    def capability_profile(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "ask_kind": self.ask_kind,
            "kind_namespace": self.kind_namespace,
            "supported_presets": sorted(self.supported_presets),
            "default_preset": self.default_preset,
            "has_true_non_pro": self.has_true_non_pro,
            "auto_semantics": self.auto_semantics,
            "safe_non_pro_fallback": self.safe_non_pro_fallback,
            "deep_research_support": self.deep_research_support,
            "premium_presets": sorted(self.premium_presets),
        }
