"""Схемы запросов и ответов API."""

from news_reposter.schemas.max import MAXPublishResponse
from news_reposter.schemas.source import SourceCreate, SourceRead, SourceUpdate
from news_reposter.schemas.system import DatabaseHealthResponse, HealthResponse
from news_reposter.schemas.target import TargetCreate, TargetRead, TargetUpdate
from news_reposter.schemas.target_source import (
    TargetSourceCreate,
    TargetSourceRead,
    TargetSourceUpdate,
)

__all__ = [
    "DatabaseHealthResponse",
    "HealthResponse",
    "MAXPublishResponse",
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
