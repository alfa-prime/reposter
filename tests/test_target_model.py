from sqlalchemy import Boolean, DateTime, String, UniqueConstraint

from news_reposter.db.models import Target


def test_target_table_structure() -> None:
    """Проверяет основные поля и ограничения таблицы целей."""

    table = Target.__table__

    assert table.name == "targets"
    assert table.c.target_id.primary_key is True
    assert isinstance(table.c.name.type, String)
    assert table.c.platform.type.length == 32
    assert table.c.external_id.type.length == 255
    assert table.c.url.nullable is True
    assert isinstance(table.c.is_active.type, Boolean)
    assert isinstance(table.c.created_at.type, DateTime)
    assert isinstance(table.c.updated_at.type, DateTime)
    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_targets_platform_external_id"
        for constraint in table.constraints
    )
    assert "ix_targets_platform_is_active" in {
        index.name for index in table.indexes
    }
