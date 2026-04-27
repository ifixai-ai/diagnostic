

import asyncio
from contextlib import asynccontextmanager

JUDGE_CALL_CAP = 200
RATE_LIMIT_RECOVERY_SECONDS = 30.0
MIN_EFFECTIVE_LIMIT = 1
MAX_CONCURRENCY_LIMIT = 20


class JudgeCallCapExceeded(RuntimeError):

    def __init__(self, calls_used: int, cap: int) -> None:
        super().__init__(
            f"Judge-call cap exceeded: {calls_used}/{cap} calls already used. "
            f"Reduce --test scope or switch to a non-judge eval mode."
        )
        self.calls_used = calls_used
        self.cap = cap


async def _recover_effective_limit(governor: "ConcurrencyGovernor") -> None:
    await asyncio.sleep(RATE_LIMIT_RECOVERY_SECONDS)
    async with governor._rate_limit_lock:
        governor.effective_limit = governor.configured_limit
        governor._semaphore = asyncio.Semaphore(governor.effective_limit)
        governor._recovery_task = None


class ConcurrencyGovernor:

    def __init__(self, configured_limit: int, judge_call_cap: int = JUDGE_CALL_CAP) -> None:
        if not (1 <= configured_limit <= MAX_CONCURRENCY_LIMIT):
            raise ValueError(
                f"configured_limit must be between 1 and {MAX_CONCURRENCY_LIMIT} "
                f"(got {configured_limit})"
            )
        self.configured_limit = configured_limit
        self.effective_limit = configured_limit
        self._semaphore = asyncio.Semaphore(configured_limit)
        self._judge_calls_used = 0
        self._judge_call_cap = judge_call_cap
        self._rate_limit_lock = asyncio.Lock()
        self._cap_lock = asyncio.Lock()
        self._recovery_task: asyncio.Task | None = None

    @asynccontextmanager
    async def acquire(self):
        async with self._semaphore:
            yield

    async def reserve_judge_call(self) -> None:
        async with self._cap_lock:
            if self._judge_calls_used >= self._judge_call_cap:
                raise JudgeCallCapExceeded(self._judge_calls_used, self._judge_call_cap)
            self._judge_calls_used += 1

    async def on_rate_limit(self) -> None:
        async with self._rate_limit_lock:
            new_limit = max(MIN_EFFECTIVE_LIMIT, self.effective_limit // 2)
            if new_limit != self.effective_limit:
                self.effective_limit = new_limit
                self._semaphore = asyncio.Semaphore(new_limit)
            if self._recovery_task is not None and not self._recovery_task.done():
                self._recovery_task.cancel()
            self._recovery_task = asyncio.create_task(_recover_effective_limit(self))

    def remaining_budget(self) -> int:
        return self._judge_call_cap - self._judge_calls_used

    @property
    def is_sequential(self) -> bool:
        return self.configured_limit == 1
