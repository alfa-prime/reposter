"""Операции чтения и записи данных приложения."""

from news_reposter.repositories.collection import CollectionRepository
from news_reposter.repositories.queue_item import (
    QueueItemAlreadyExistsError,
    QueueItemRepository,
)
from news_reposter.repositories.role import RoleRepository
from news_reposter.repositories.source import SourceAlreadyExistsError, SourceRepository
from news_reposter.repositories.target import TargetAlreadyExistsError, TargetRepository
from news_reposter.repositories.target_source import (
    TargetSourceAlreadyExistsError,
    TargetSourceRepository,
)
from news_reposter.repositories.user import UserRepository

__all__ = [
    "CollectionRepository",
    "QueueItemAlreadyExistsError",
    "QueueItemRepository",
    "RoleRepository",
    "SourceAlreadyExistsError",
    "SourceRepository",
    "TargetAlreadyExistsError",
    "TargetRepository",
    "TargetSourceAlreadyExistsError",
    "TargetSourceRepository",
    "UserRepository",
]
