from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.models import Source
from news_reposter.schemas import SourceCreate, SourceUpdate


class SourceAlreadyExistsError(RuntimeError):
    """Источник с такой ссылкой уже существует."""


class SourceRepository:
    """Выполняет CRUD-операции с источниками."""

    def __init__(self, session: AsyncSession) -> None:
        """Сохраняет сессию базы данных для последующих операций."""

        self.session = session

    async def create(self, data: SourceCreate) -> Source:
        """Создаёт источник и возвращает сохранённую запись."""

        source = Source(**data.model_dump())
        self.session.add(source)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise SourceAlreadyExistsError from exc
        await self.session.refresh(source)
        return source

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        platform: str | None,
        is_active: bool | None,
    ) -> list[Source]:
        """Возвращает источники с фильтрацией и пагинацией."""

        statement = (
            select(Source).order_by(Source.source_id).offset(offset).limit(limit)
        )
        if platform is not None:
            statement = statement.where(Source.platform == platform)
        if is_active is not None:
            statement = statement.where(Source.is_active == is_active)
        result = await self.session.scalars(statement)
        return list(result.all())

    async def get(self, source_id: int) -> Source | None:
        """Находит источник по идентификатору."""

        return await self.session.get(Source, source_id)

    async def update(self, source: Source, data: SourceUpdate) -> Source:
        """Изменяет переданные поля источника."""

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(source, field, value)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise SourceAlreadyExistsError from exc
        await self.session.refresh(source)
        return source

    async def delete(self, source: Source) -> None:
        """Удаляет источник из базы данных."""

        await self.session.delete(source)
        await self.session.commit()
