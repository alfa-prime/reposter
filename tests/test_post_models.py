from sqlalchemy import CheckConstraint, UniqueConstraint, inspect

from news_reposter.db.models import (
    AttachmentType,
    Post,
    PostAttachment,
    PostStatus,
    Publication,
    PublicationStatus,
)


def constraint_names(model: type[object]) -> set[str | None]:
    """Возвращает имена ограничений таблицы ORM-модели."""

    return {constraint.name for constraint in model.__table__.constraints}


def test_post_table_structure() -> None:
    """Проверяет поля, статусы и защиту постов от дублей."""

    table = Post.__table__

    assert table.c.post_id.primary_key is True
    assert table.c.source_id.nullable is False
    source_fk = next(iter(table.c.source_id.foreign_keys))
    assert source_fk.target_fullname == "sources.source_id"
    assert source_fk.ondelete == "RESTRICT"
    assert table.c.external_post_id.type.length == 255
    assert table.c.original_text.nullable is False
    assert table.c.rewritten_text.nullable is True
    assert table.c.status.default.arg == PostStatus.RECEIVED
    assert set(table.c.status.type.enums) == {status.value for status in PostStatus}
    assert "uq_posts_source_id_external_post_id" in constraint_names(Post)
    assert {index.name for index in table.indexes} == {
        "ix_posts_source_id_status",
        "ix_posts_status_received_at",
    }


def test_attachment_table_structure() -> None:
    """Проверяет связь вложений с постом и порядок вложений."""

    table = PostAttachment.__table__

    assert table.c.attachment_id.primary_key is True
    post_fk = next(iter(table.c.post_id.foreign_keys))
    assert post_fk.target_fullname == "posts.post_id"
    assert post_fk.ondelete == "CASCADE"
    assert set(table.c.attachment_type.type.enums) == {
        item.value for item in AttachmentType
    }
    assert "uq_post_attachments_post_id_position" in constraint_names(
        PostAttachment
    )
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_post_attachments_position"
        for constraint in table.constraints
    )


def test_publication_table_structure() -> None:
    """Проверяет очередь публикаций и её связи с постом и целью."""

    table = Publication.__table__

    assert table.c.publication_id.primary_key is True
    post_fk = next(iter(table.c.post_id.foreign_keys))
    target_fk = next(iter(table.c.target_id.foreign_keys))
    assert post_fk.target_fullname == "posts.post_id"
    assert post_fk.ondelete == "CASCADE"
    assert target_fk.target_fullname == "targets.target_id"
    assert target_fk.ondelete == "RESTRICT"
    assert table.c.status.default.arg == PublicationStatus.PENDING
    assert set(table.c.status.type.enums) == {
        status.value for status in PublicationStatus
    }
    assert "uq_publications_post_id_target_id" in constraint_names(Publication)
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_publications_attempts"
        for constraint in table.constraints
    )


def test_post_relationships() -> None:
    """Проверяет ORM-связи между моделями очереди."""

    post_relationships = inspect(Post).relationships
    publication_relationships = inspect(Publication).relationships

    assert post_relationships.source.mapper.class_.__name__ == "Source"
    assert post_relationships.attachments.mapper.class_ is PostAttachment
    assert post_relationships.publications.mapper.class_ is Publication
    assert publication_relationships.target.mapper.class_.__name__ == "Target"
