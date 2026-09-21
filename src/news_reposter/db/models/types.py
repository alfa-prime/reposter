"""Общие типы столбцов ORM-моделей."""

from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JSON_DATA = JSON().with_variant(JSONB(), "postgresql")
IPAddress = str | IPv4Address | IPv6Address
