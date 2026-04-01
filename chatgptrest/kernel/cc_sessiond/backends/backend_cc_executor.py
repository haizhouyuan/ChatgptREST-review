import logging
from typing import AsyncIterator, Any, Optional

from .base import SessionBackend, BackendResult
from chatgptrest.kernel.cc_executor import CcExecutor, CcTask, CcResult


logger = logging.getLogger(__name__)


class CcExecutorBackend(SessionBackend):
    """Backend using existing CcExecutor headless dispatch."""

    backend_name = "cc_executor"

    def __init__(self, cc_executor: Optional[CcExecutor] = None):
        self._executor = cc_executor

    def _get_executor(self) -> CcExecutor:
        if self._executor is None:
            self._executor = CcExecutor()
        return self._executor

    def _build_task(
        self,
        prompt: str,
        options: dict,
        *,
        resume_session_id: Optional[str] = None,
    ) -> CcTask:
        files = options.get("files")
        if files is None:
            files = options.get("file_paths", [])

        task = CcTask(
            task_type=options.get("task_type", "general"),
            description=prompt,
            files=files or [],
            context=options.get("context", {}),
            timeout=options.get("timeout", 300),
            model=options.get("model", "sonnet"),
            max_turns=options.get("max_turns", 25),
            max_budget_usd=options.get("max_budget_usd", 10.0),
            system_prompt=options.get("system_prompt", ""),
            cwd=options.get("cwd", ""),
            permission_mode=options.get("permission_mode", "bypassPermissions"),
            add_dirs=options.get("add_dirs", []),
        )
        if resume_session_id:
            task.stateless = False
            task.session_id = resume_session_id
        return task

    def _result_payload(self, result: CcResult) -> dict:
        total_tokens = (result.input_tokens or 0) + (result.output_tokens or 0)
        return {
            "subtype": "completed" if result.ok else "failed",
            "output_text": result.output,
            "structured_output": result.structured_output,
            "quality_score": result.quality_score,
            "total_cost_usd": result.cost_usd,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "total_tokens": total_tokens,
            "turns": result.num_turns,
            "session_id": result.session_id,
            "model_used": result.model_used,
            "error": result.error or None,
        }

    async def create_run(
        self,
        session_id: str,
        prompt: str,
        options: dict,
    ) -> AsyncIterator[Any]:
        executor = self._get_executor()
        task = self._build_task(prompt, options)

        try:
            result = await executor.dispatch_headless(task)

            yield {
                "type": "completed",
                "backend": self.backend_name,
                "backend_run_id": result.session_id or None,
                "result": {
                    **self._result_payload(result),
                },
            }
        except Exception as e:
            logger.exception(f"CcExecutorBackend.create_run failed: {e}")
            yield {
                "type": "completed",
                "backend": self.backend_name,
                "result": {
                    "subtype": "failed",
                    "error": str(e),
                },
            }

    async def continue_run(
        self,
        session_id: str,
        backend_run_id: str,
        prompt: str,
        options: dict,
    ) -> AsyncIterator[Any]:
        executor = self._get_executor()
        if not backend_run_id:
            yield {
                "type": "completed",
                "backend": self.backend_name,
                "result": {
                    "subtype": "failed",
                    "error": "Missing backend_run_id for continuation",
                },
            }
            return

        task = self._build_task(prompt, options, resume_session_id=backend_run_id)
        task.context = {
            **task.context,
            "continue_from_session": session_id,
            "continue_from_run_id": backend_run_id,
        }

        try:
            result = await executor.dispatch_headless(task)

            yield {
                "type": "completed",
                "backend": self.backend_name,
                "backend_run_id": result.session_id or backend_run_id,
                "result": {
                    **self._result_payload(result),
                },
            }
        except Exception as e:
            logger.exception(f"CcExecutorBackend.continue_run failed: {e}")
            yield {
                "type": "completed",
                "backend": self.backend_name,
                "result": {
                    "subtype": "failed",
                    "error": str(e),
                },
            }

    async def cancel_run(
        self,
        session_id: str,
        backend_run_id: str,
    ) -> bool:
        return False

    async def poll_run(
        self,
        session_id: str,
        backend_run_id: str,
    ) -> BackendResult:
        return BackendResult(
            ok=False,
            session_id=session_id,
            backend=self.backend_name,
            backend_run_id=backend_run_id,
            state="unknown",
            error="Poll not implemented for CcExecutor backend",
        )

    async def result_from_run(
        self,
        session_id: str,
        backend_run_id: str,
    ) -> BackendResult:
        return BackendResult(
            ok=False,
            session_id=session_id,
            backend=self.backend_name,
            backend_run_id=backend_run_id,
            state="unknown",
            error="Result fetch not implemented for CcExecutor backend",
        )
