from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.models import Target
from news_reposter.schemas import TargetCreate, TargetUpdate


class TargetAlreadyExistsError(RuntimeError):
    """Цель с такой платформой и внешним ID уже существует."""


class TargetRepository:
    """Выполняет CRUD-операции с целями публикаций."""

    def __init__(self, session: AsyncSession) -> None:
        """Сохраняет сессию базы данных для последующих операций."""

        self.session = session

    async def create(self, data: TargetCreate) -> Target:
        """Создаёт цель публикации и возвращает сохранённую запись."""

        target = Target(**data.model_dump())
        self.session.add(target)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise TargetAlreadyExistsError from exc
        await self.session.refresh(target)
        return target

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        platform: str | None,
        is_active: bool | None,
    ) -> list[Target]:
        """Возвращает цели с фильтрацией и пагинацией."""

        statement = (
            select(Target).order_by(Target.target_id).offset(offset).limit(limit)
        )
        if platform is not None:
            statement = statement.where(Target.platform == platform)
        if is_active is not None:
            statement = statement.where(Target.is_active == is_active)
        result = await self.session.scalars(statement)
        return list(result.all())

    async def get(self, target_id: int) -> Target | None:
        """Находит цель публикации по идентификатору."""

        return await self.session.get(Target, target_id)

    async def update(self, target: Target, data: TargetUpdate) -> Target:
        """Изменяет переданные поля цели публикации."""

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(target, field, value)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise TargetAlreadyExistsError from exc
        await self.session.refresh(target)
        return target

    async def delete(self, target: Target) -> None:
        """Удаляет цель публикации из базы данных."""

        await self.session.delete(target)
        await self.session.commit()
