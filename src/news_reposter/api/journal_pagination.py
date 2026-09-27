"""Bounded, versioned cursor pagination shared by journal endpoints."""

import json
from base64 import b64decode, urlsafe_b64encode
from binascii import Error as Base64Error
from datetime import datetime
from hashlib import sha256
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError, field_validator


class JournalCursor(BaseModel):
    version: Literal[1] = 1
    context: str
    row_id: int = Field(gt=0, le=2147483647, strict=True)
    created_at: datetime | None = None

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("cursor timestamp must include a timezone")
        return value


def cursor_context(kind: str, filters: dict[str, object]) -> str:
    payload = json.dumps([kind, filters], sort_keys=True, default=str)
    return sha256(payload.encode()).hexdigest()


def encode_cursor(context: str, row_id: int, created_at: datetime | None = None) -> str:
    cursor = JournalCursor(context=context, row_id=row_id, created_at=created_at)
    return urlsafe_b64encode(cursor.model_dump_json().encode()).decode().rstrip("=")


def decode_cursor(
    value: str | None, context: str, *, audit: bool = False
) -> JournalCursor | None:
    if value is None:
        return None
    try:
        if not value or len(value) > 512:
            raise ValueError("invalid cursor length")
        raw = b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        cursor = JournalCursor.model_validate_json(raw)
        if cursor.context != context or (cursor.created_at is not None) != audit:
            raise ValueError("cursor does not match the journal filters")
        return cursor
    except (ValueError, Base64Error, ValidationError) as exc:
        raise HTTPException(
            status_code=422, detail="Недействительный курсор журнала"
        ) from exc


def validate_pagination(pagination: str, cursor: str | None, offset: int) -> None:
    if (pagination == "cursor" and offset != 0) or (
        pagination == "offset" and cursor is not None
    ):
        raise HTTPException(
            status_code=422, detail="Курсор и OFFSET нельзя использовать вместе"
        )
