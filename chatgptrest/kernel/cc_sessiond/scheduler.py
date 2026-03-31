import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path


@dataclass
class BudgetSnapshot:
    """Budget tracking snapshot."""
    total_spent: float = 0.0
    hourly_spent: float = 0.0
    tokens_used: int = 0
    last_reset: datetime = field(default_factory=datetime.now)


class BudgetTracker:
    """Track and enforce budget limits."""

    def __init__(
        self,
        budget_per_hour: float = 10.0,
        budget_total: float = 100.0,
    ):
        self.budget_per_hour = budget_per_hour
        self.budget_total = budget_total
        self.snapshot = BudgetSnapshot()
        self._lock = asyncio.Lock()

    async def check_budget(self) -> bool:
        """Check if budget allows new job."""
        async with self._lock:
            self._reset_hourly_if_needed()
            
            if self.snapshot.hourly_spent >= self.budget_per_hour:
                return False
            if self.snapshot.total_spent >= self.budget_total:
                return False
            return True

    async def record_cost(self, cost: float, tokens: int = 0):
        """Record job cost."""
        async with self._lock:
            self.snapshot.total_spent += cost
            self.snapshot.hourly_spent += cost
            self.snapshot.tokens_used += tokens

    def get_snapshot(self) -> dict:
        """Get current budget snapshot."""
        self._reset_hourly_if_needed()
        return {
            "total_spent": self.snapshot.total_spent,
            "hourly_spent": self.snapshot.hourly_spent,
            "tokens_used": self.snapshot.tokens_used,
            "budget_per_hour": self.budget_per_hour,
            "budget_total": self.budget_total,
            "remaining_hourly": self.budget_per_hour - self.snapshot.hourly_spent,
            "remaining_total": self.budget_total - self.snapshot.total_spent,
        }

    def _reset_hourly_if_needed(self):
        """Reset hourly tracking if needed."""
        now = datetime.now()
        if (now - self.snapshot.last_reset) > timedelta(hours=1):
            self.snapshot.hourly_spent = 0.0
            self.snapshot.last_reset = now

    def close(self):
        pass


@dataclass
class QueuedJob:
    """A job in the scheduler queue."""
    session_id: str
    prompt: str
    options: dict
    priority: int = 0
    created_at: datetime = field(default_factory=datetime.now)


class JobScheduler:
    """Job scheduler with concurrency and budget control."""

    def __init__(
        self,
        max_concurrent: int = 3,
        budget_per_hour: float = 10.0,
        budget_total: float = 100.0,
    ):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.budget_tracker = BudgetTracker(budget_per_hour, budget_total)
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.running: set[str] = set()
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def submit(
        self,
        session_id: str,
        prompt: str,
        options: dict,
        priority: int = 0,
    ) -> str:
        """Submit a job to the scheduler."""
        # Check budget first
        if not await self.budget_tracker.check_budget():
            raise RuntimeError("Budget exceeded")
        
        job = QueuedJob(
            session_id=session_id,
            prompt=prompt,
            options=options,
            priority=priority,
        )
        
        # Add priority (negate so lower number = higher priority)
        # Use timestamp as tiebreaker for same priority
        tiebreaker = time.time()
        await self.queue.put((-priority, tiebreaker, job))
        return session_id

    async def run_next(self, executor_fn) -> Optional[str]:
        """Run the next job in the queue."""
        async with self.semaphore:
            try:
                _, _, job = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                return None

            if job.session_id in self.running:
                return None

            async with self._lock:
                self.running.add(job.session_id)

            # Run the job
            task = asyncio.create_task(
                self._run_job(job.session_id, job.prompt, job.options, executor_fn)
            )
            self._running_tasks[job.session_id] = task
            
            return job.session_id

    async def _run_job(
        self,
        session_id: str,
        prompt: str,
        options: dict,
        executor_fn,
    ):
        """Execute a single job."""
        try:
            await executor_fn(session_id, prompt, options)
        except Exception as e:
            raise
        finally:
            async with self._lock:
                self.running.discard(session_id)
                self._running_tasks.pop(session_id, None)

    async def cancel(self, session_id: str) -> bool:
        """Cancel a running or queued job."""
        async with self._lock:
            if session_id in self.running:
                task = self._running_tasks.get(session_id)
                if task:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                return True
            
            # Check queue
            temp_items = []
            found = False
            while not self.queue.empty():
                try:
                    _, _, job = self.queue.get_nowait()
                    if job.session_id == session_id:
                        found = True
                    else:
                        temp_items.append(((-job.priority, time.time(), job)))
                except asyncio.QueueEmpty:
                    break
            
            for item in temp_items:
                await self.queue.put(item)
            
            return found

    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "running_count": len(self.running),
            "max_concurrent": self.max_concurrent,
            "queue_size": self.queue.qsize(),
            "running_sessions": list(self.running),
            "budget": self.budget_tracker.get_snapshot(),
        }

    async def wait_for_completion(self, session_id: str, timeout: Optional[float] = None):
        """Wait for a specific session to complete."""
        if session_id not in self._running_tasks:
            return
        
        task = self._running_tasks[session_id]
        try:
            await asyncio.wait_for(task, timeout=timeout)
        except asyncio.TimeoutError:
            pass

    @property
    def running_tasks(self) -> dict:
        return self._running_tasks
