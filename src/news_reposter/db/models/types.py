"""Общие типы столбцов ORM-моделей."""

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JSON_DATA = JSON().with_variant(JSONB(), "postgresql")
