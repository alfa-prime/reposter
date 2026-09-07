"""Схемы запросов и ответов API."""

from news_reposter.schemas.source import SourceCreate, SourceRead, SourceUpdate
from news_reposter.schemas.target import TargetCreate, TargetRead, TargetUpdate

__all__ = [
    "SourceCreate",
    "SourceRead",
    "SourceUpdate",
    "TargetCreate",
    "TargetRead",
    "TargetUpdate",
]
