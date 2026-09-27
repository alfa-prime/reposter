from dataclasses import dataclass
from enum import StrEnum
from random import uniform


class TaskQueue(StrEnum):
    REWRITE = "rewrite"
    COLLECTION = "collection"
    PUBLICATION = "publication"
    MAINTENANCE = "maintenance"


class TaskState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NEEDS_REVIEW = "needs_review"


TERMINAL_STATES = frozenset(
    {TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED, TaskState.NEEDS_REVIEW}
)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    timeout_seconds: int
    base_delay: int
    max_delay: int

    def delay(self, attempt: int, retry_after: float | None = None) -> float:
        exponential = min(
            self.max_delay, self.base_delay * 2 ** min(max(0, attempt - 1), 20)
        )
        # A provider's Retry-After is a lower bound, never shortened by our cap.
        return max(uniform(exponential / 2, exponential), retry_after or 0)


POLICIES = {
    TaskQueue.REWRITE: RetryPolicy(3, 180, 15, 300),
    TaskQueue.COLLECTION: RetryPolicy(3, 1800, 30, 600),
    TaskQueue.PUBLICATION: RetryPolicy(3, 600, 15, 300),
    TaskQueue.MAINTENANCE: RetryPolicy(2, 900, 60, 600),
}


class RetryableTaskError(RuntimeError):
    def __init__(self, code: str, retry_after: float | None = None):
        super().__init__(code)
        self.retry_after = retry_after


class PermanentTaskError(RuntimeError):
    pass


class ReviewRequired(RuntimeError):
    pass


class LostLease(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


class ActiveTaskConflict(RuntimeError):
    pass
