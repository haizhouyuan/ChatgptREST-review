from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from chatgptrest.providers.spec import ProviderSpec

if TYPE_CHECKING:
    from chatgptrest.core.config import AppConfig


@dataclass(frozen=True)
class ProviderPolicy:
    provider_id: str
    ask_kind: str
    rate_limit_key: str
    min_prompt_interval_seconds: int


def policy_from_config(*, cfg: AppConfig, spec: ProviderSpec) -> ProviderPolicy:
    raw = getattr(cfg, spec.min_interval_attr, 0)
    try:
        interval = max(0, int(raw or 0))
    except Exception:
        interval = 0
    return ProviderPolicy(
        provider_id=spec.provider_id,
        ask_kind=spec.ask_kind,
        rate_limit_key=spec.rate_limit_key,
        min_prompt_interval_seconds=interval,
    )
