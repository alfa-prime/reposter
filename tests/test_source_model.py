from sqlalchemy import Boolean, DateTime, String

from news_reposter.db.models import Source


def test_source_table_structure() -> None:
    """Проверяет основные поля и ограничения таблицы источников."""

    table = Source.__table__

    assert table.name == "sources"
    assert table.c.id.primary_key is True
    assert isinstance(table.c.name.type, String)
    assert table.c.name.type.length == 200
    assert table.c.platform.type.length == 32
    assert table.c.url.type.length == 2048
    assert isinstance(table.c.is_active.type, Boolean)
    assert isinstance(table.c.created_at.type, DateTime)
    assert isinstance(table.c.updated_at.type, DateTime)
    assert any(
        constraint.name == "uq_sources_url" for constraint in table.constraints
    )
    assert "ix_sources_platform_is_active" in {
        index.name for index in table.indexes
    }
