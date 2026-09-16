from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from news_reposter.db.models import (
    CollectionRun,
    CollectionRunStatus,
    CollectionRunTrigger,
    CollectionSettings,
)


class CollectionRepository:
    """Хранит настройки планировщика и журнал запусков сборщика."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_settings(self) -> CollectionSettings:
        settings = await self.session.get(CollectionSettings, 1)
        if settings is None:
            settings = CollectionSettings(collection_settings_id=1)
            self.session.add(settings)
            await self.session.commit()
        return settings

    async def update_settings(
        self,
        settings: CollectionSettings,
        **changes: object,
    ) -> CollectionSettings:
        for field, value in changes.items():
            setattr(settings, field, value)
        await self.session.commit()
        await self.session.refresh(settings)
        return settings

    async def list_runs(
        self,
        *,
        offset: int,
        limit: int,
        status: CollectionRunStatus | None = None,
        trigger: CollectionRunTrigger | None = None,
    ) -> tuple[list[CollectionRun], int]:
        filters = []
        if status is not None:
            filters.append(CollectionRun.status == status)
        if trigger is not None:
            filters.append(CollectionRun.trigger == trigger)

        count = await self.session.scalar(
            select(func.count(CollectionRun.collection_run_id)).where(*filters)
        )
        result = await self.session.scalars(
            select(CollectionRun)
            .where(*filters)
            .order_by(CollectionRun.collection_run_id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all()), int(count or 0)

    async def get_run(self, run_id: int) -> CollectionRun | None:
        return await self.session.scalar(
            select(CollectionRun)
            .options(selectinload(CollectionRun.source_runs))
            .where(CollectionRun.collection_run_id == run_id)
        )

    async def latest_run(self) -> CollectionRun | None:
        return await self.session.scalar(
            select(CollectionRun)
            .order_by(CollectionRun.collection_run_id.desc())
            .limit(1)
        )

    async def latest_success(self) -> CollectionRun | None:
        return await self.session.scalar(
            select(CollectionRun)
            .where(CollectionRun.status == CollectionRunStatus.SUCCESS)
            .order_by(CollectionRun.collection_run_id.desc())
            .limit(1)
        )

    async def consecutive_failures(self) -> int:
        statuses = list(
            (
                await self.session.scalars(
                    select(CollectionRun.status)
                    .where(CollectionRun.status != CollectionRunStatus.RUNNING)
                    .order_by(CollectionRun.collection_run_id.desc())
                    .limit(100)
                )
            ).all()
        )
        failures = 0
        for run_status in statuses:
            if run_status not in {
                CollectionRunStatus.FAILED,
                CollectionRunStatus.PARTIAL,
                CollectionRunStatus.INTERRUPTED,
            }:
                break
            failures += 1
        return failures
