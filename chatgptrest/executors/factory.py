from __future__ import annotations

from typing import Any

from chatgptrest.core.config import AppConfig
from chatgptrest.driver.api import ToolCaller
from chatgptrest.executors.advisor_orchestrate import AdvisorOrchestrateExecutor
from chatgptrest.executors.chatgpt_web_mcp import ChatGPTWebMcpExecutor
from chatgptrest.executors.coding_plan import CodingPlanExecutor
from chatgptrest.executors.dummy import DummyExecutor
from chatgptrest.executors.gemini_web_mcp import GeminiWebMcpExecutor
from chatgptrest.executors.local_llm import LocalLLMExecutor
from chatgptrest.executors.qwen_web_mcp import QwenWebMcpExecutor
from chatgptrest.executors.repair import RepairAutofixExecutor, RepairExecutor, RepairOpenPrExecutor
from chatgptrest.executors.sre import SreFixRequestExecutor
from chatgptrest.providers.registry import provider_spec_for_kind


def executor_for_job(
    cfg: AppConfig,
    kind: str,
    *,
    tool_caller: ToolCaller | None = None,
) -> Any | None:
    """
    Resolve a job kind to an executor instance.

    Keeping this mapping outside `worker.py` prevents the worker loop from
    being the de facto control plane for provider/executor policy.
    """
    if kind.startswith("dummy."):
        return DummyExecutor()
    if kind == "advisor.orchestrate":
        return AdvisorOrchestrateExecutor(cfg=cfg)
    if kind == "coding_plan.ask":
        return CodingPlanExecutor()
    if kind == "local_llm.ask":
        return LocalLLMExecutor()

    spec = provider_spec_for_kind(kind)
    if spec is not None and spec.provider_id == "chatgpt":
        return ChatGPTWebMcpExecutor(
            mcp_url=cfg.chatgpt_mcp_url,
            tool_caller=tool_caller,
            pro_fallback_presets=cfg.pro_fallback_presets,
        )
    if spec is not None and spec.provider_id == "gemini":
        return GeminiWebMcpExecutor(
            mcp_url=cfg.chatgpt_mcp_url,
            tool_caller=tool_caller,
        )
    if spec is not None and spec.provider_id == "qwen":
        from chatgptrest.core.env import get_bool as _env_get_bool

        if not _env_get_bool("CHATGPTREST_QWEN_ENABLED"):
            return None
        return QwenWebMcpExecutor(
            mcp_url=cfg.chatgpt_mcp_url,
            tool_caller=tool_caller,
        )
    if spec is not None and spec.provider_id == "local_llm":
        return LocalLLMExecutor()
    if kind in {"sre.fix_request", "sre.diagnose"}:
        return SreFixRequestExecutor(cfg=cfg)
    if kind == "repair.autofix":
        return RepairAutofixExecutor(cfg=cfg, tool_caller=tool_caller)
    if kind == "repair.open_pr":
        return RepairOpenPrExecutor(cfg=cfg, tool_caller=tool_caller)
    if kind.startswith("repair."):
        return RepairExecutor(cfg=cfg, tool_caller=tool_caller)
    return None
