"""ORM-модели приложения."""

from news_reposter.db.models.attachment import PostAttachment
from news_reposter.db.models.audit_event import AuditEvent
from news_reposter.db.models.collection_run import CollectionRun
from news_reposter.db.models.collection_settings import CollectionSettings
from news_reposter.db.models.collection_source_run import CollectionSourceRun
from news_reposter.db.models.enums import (
    AttachmentType,
    CollectionRunStatus,
    CollectionRunTrigger,
    CollectionSourceRunStatus,
    PostStatus,
    PublicationAttemptStatus,
    PublicationStatus,
    QueueItemStatus,
)
from news_reposter.db.models.login_attempt import LoginAttempt
from news_reposter.db.models.max_channel import MAXChannel
from news_reposter.db.models.permission import Permission
from news_reposter.db.models.post import Post
from news_reposter.db.models.publication import Publication
from news_reposter.db.models.publication_attempt import PublicationAttempt
from news_reposter.db.models.queue_item import QueueItem
from news_reposter.db.models.role import Role
from news_reposter.db.models.role_permission import RolePermission
from news_reposter.db.models.source import Source
from news_reposter.db.models.target import Target
from news_reposter.db.models.target_source import TargetSource
from news_reposter.db.models.user import User
from news_reposter.db.models.user_role import UserRole
from news_reposter.db.models.user_session import UserSession
from news_reposter.db.models.user_target import UserTarget

__all__ = [
    "AttachmentType",
    "AuditEvent",
    "CollectionRun",
    "CollectionRunStatus",
    "CollectionRunTrigger",
    "CollectionSettings",
    "CollectionSourceRun",
    "CollectionSourceRunStatus",
    "MAXChannel",
    "LoginAttempt",
    "Permission",
    "Post",
    "PostAttachment",
    "PostStatus",
    "Publication",
    "PublicationAttempt",
    "PublicationAttemptStatus",
    "PublicationStatus",
    "QueueItem",
    "QueueItemStatus",
    "Role",
    "RolePermission",
    "Source",
    "Target",
    "TargetSource",
    "User",
    "UserRole",
    "UserSession",
    "UserTarget",
]
