"""Схемы запросов и ответов API."""

from news_reposter.schemas.auth import (
    CurrentUserResponse,
    CurrentUserRole,
    LoginRequest,
    PasswordChangeRequest,
)
from news_reposter.schemas.collection import (
    CollectionRunDetail,
    CollectionRunPage,
    CollectionRunRead,
    CollectionSettingsRead,
    CollectionSettingsUpdate,
    CollectionSourceRunRead,
    CollectionStatusRead,
)
from news_reposter.schemas.queue_item import (
    QueueItemCreate,
    QueueItemRead,
    QueueItemSchedule,
    QueueItemUpdate,
)
from news_reposter.schemas.source import SourceCreate, SourceRead, SourceUpdate
from news_reposter.schemas.system import DatabaseHealthResponse, HealthResponse
from news_reposter.schemas.target import TargetCreate, TargetRead, TargetUpdate
from news_reposter.schemas.target_source import (
    TargetSourceCreate,
    TargetSourceRead,
    TargetSourceUpdate,
)

__all__ = [
    "CollectionRunDetail",
    "CollectionRunPage",
    "CollectionRunRead",
    "CollectionSettingsRead",
    "CollectionSettingsUpdate",
    "CollectionSourceRunRead",
    "CollectionStatusRead",
    "CurrentUserResponse",
    "CurrentUserRole",
    "DatabaseHealthResponse",
    "HealthResponse",
    "LoginRequest",
    "PasswordChangeRequest",
    "QueueItemCreate",
    "QueueItemRead",
    "QueueItemSchedule",
    "QueueItemUpdate",
    "SourceCreate",
    "SourceRead",
    "SourceUpdate",
    "TargetCreate",
    "TargetRead",
    "TargetSourceCreate",
    "TargetSourceRead",
    "TargetSourceUpdate",
    "TargetUpdate",
]
