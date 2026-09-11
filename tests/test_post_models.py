from sqlalchemy import CheckConstraint, inspect

from news_reposter.db.models import (
    AttachmentType,
    Post,
    PostAttachment,
    PostStatus,
    Publication,
    PublicationStatus,
    QueueItem,
    QueueItemStatus,
    TargetSource,
)


def constraint_names(model: type[object]) -> set[str | None]:
    """Возвращает имена ограничений таблицы ORM-модели."""

    return {constraint.name for constraint in model.__table__.constraints}


def test_post_table_structure() -> None:
    """Проверяет поля исходного поста и защиту от дублей."""

    table = Post.__table__

    assert table.c.post_id.primary_key is True
    assert table.c.source_id.nullable is False
    source_fk = next(iter(table.c.source_id.foreign_keys))
    assert source_fk.target_fullname == "sources.source_id"
    assert source_fk.ondelete == "RESTRICT"
    assert table.c.external_post_id.type.length == 255
    assert table.c.original_text.nullable is False
    assert "rewritten_text" not in table.c
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


def test_target_source_table_structure() -> None:
    """Проверяет привязку источника к конкретной цели публикации."""

    table = TargetSource.__table__

    assert table.c.target_source_id.primary_key is True
    target_fk = next(iter(table.c.target_id.foreign_keys))
    source_fk = next(iter(table.c.source_id.foreign_keys))
    assert target_fk.target_fullname == "targets.target_id"
    assert target_fk.ondelete == "CASCADE"
    assert source_fk.target_fullname == "sources.source_id"
    assert source_fk.ondelete == "CASCADE"
    assert table.c.is_active.default.arg is True
    assert table.c.rewrite_enabled.default.arg is True
    assert "uq_target_sources_target_id_source_id" in constraint_names(TargetSource)


def test_queue_item_table_structure() -> None:
    """Проверяет редакционную очередь для конкретного целевого канала."""

    table = QueueItem.__table__

    assert table.c.queue_item_id.primary_key is True
    post_fk = next(iter(table.c.post_id.foreign_keys))
    target_fk = next(iter(table.c.target_id.foreign_keys))
    assert post_fk.target_fullname == "posts.post_id"
    assert post_fk.ondelete == "CASCADE"
    assert target_fk.target_fullname == "targets.target_id"
    assert target_fk.ondelete == "CASCADE"
    assert table.c.rewritten_text.nullable is True
    assert table.c.status.default.arg == QueueItemStatus.PENDING
    assert set(table.c.status.type.enums) == {
        status.value for status in QueueItemStatus
    }
    assert "uq_queue_items_post_id_target_id" in constraint_names(QueueItem)


def test_publication_table_structure() -> None:
    """Проверяет техническое состояние отправки элемента очереди."""

    table = Publication.__table__

    assert table.c.publication_id.primary_key is True
    queue_item_fk = next(iter(table.c.queue_item_id.foreign_keys))
    assert queue_item_fk.target_fullname == "queue_items.queue_item_id"
    assert queue_item_fk.ondelete == "CASCADE"
    assert table.c.queue_item_id.unique is True
    assert table.c.status.default.arg == PublicationStatus.PENDING
    assert set(table.c.status.type.enums) == {
        status.value for status in PublicationStatus
    }
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_publications_attempts"
        for constraint in table.constraints
    )


def test_queue_relationships() -> None:
    """Проверяет ORM-связи новой целевой очереди."""

    post_relationships = inspect(Post).relationships
    queue_relationships = inspect(QueueItem).relationships
    publication_relationships = inspect(Publication).relationships
    target_source_relationships = inspect(TargetSource).relationships

    assert post_relationships.source.mapper.class_.__name__ == "Source"
    assert post_relationships.attachments.mapper.class_ is PostAttachment
    assert post_relationships.queue_items.mapper.class_ is QueueItem
    assert queue_relationships.post.mapper.class_ is Post
    assert queue_relationships.target.mapper.class_.__name__ == "Target"
    assert queue_relationships.publication.mapper.class_ is Publication
    assert publication_relationships.queue_item.mapper.class_ is QueueItem
    assert target_source_relationships.target.mapper.class_.__name__ == "Target"
    assert target_source_relationships.source.mapper.class_.__name__ == "Source"
