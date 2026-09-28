from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from news_reposter.background.contracts import TaskQueue, TaskState


class TaskSubmission(BaseModel):
    idempotency_key: str = Field(
        min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"
    )


class PublicationRetrySubmission(TaskSubmission):
    checked_channel: Literal[True]
    accept_duplicate_risk: Literal[True]


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    task_id: UUID
    queue: TaskQueue
    state: TaskState
    subject_id: int | None
    target_id: int | None
    attempts: int
    max_attempts: int
    available_at: datetime
    created_at: datetime
    finished_at: datetime | None
    error_code: str | None
    result: dict | None
