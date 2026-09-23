from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditEventRead(BaseModel):
    audit_event_id: int
    actor_user_id: int | None
    actor_name: str | None
    actor_username: str | None
    action: str
    subject_type: str
    subject_id: int
    subject_name: str | None
    subject_username: str | None
    details: dict[str, Any]
    created_at: datetime


class AuditEventPage(BaseModel):
    items: list[AuditEventRead]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
