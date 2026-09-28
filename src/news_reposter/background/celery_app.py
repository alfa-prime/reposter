"""Redis delivery for task IDs; PostgreSQL owns execution and retry state."""

import asyncio
from uuid import UUID

from celery import Celery

from news_reposter.background.contracts import TaskQueue
from news_reposter.background.outbox import PostgresTransport
from news_reposter.config import get_settings

celery_app = Celery("news_reposter", broker=get_settings().redis_url)
celery_app.conf.update(
    task_ignore_result=True,
    task_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": 3600},
)


@celery_app.task(name="news_reposter.rewrite")
def rewrite_task(task_id: str) -> None:
    run_task(task_id, TaskQueue.REWRITE)


@celery_app.task(name="news_reposter.collection")
def collection_task(task_id: str) -> None:
    run_task(task_id, TaskQueue.COLLECTION)


@celery_app.task(name="news_reposter.maintenance")
def maintenance_task(task_id: str) -> None:
    run_task(task_id, TaskQueue.MAINTENANCE)


def run_task(task_id: str, queue: TaskQueue) -> None:
    # A new event loop per delivery needs a fresh SQLAlchemy pool each time.
    from news_reposter.background.worker import run_once
    from news_reposter.db.session import close_database
    from news_reposter.http_client import create_http_client

    async def run() -> None:
        client = create_http_client()
        try:
            await run_once(queue, client, task_id=UUID(task_id))
        finally:
            await client.aclose()
            await close_database()

    asyncio.run(run())


class MixedTransport:
    """Use Redis for rewrite, collection and maintenance; PG for publication."""

    def __init__(self) -> None:
        self.postgres = PostgresTransport()

    async def publish(self, task_id: UUID, queue: str, event_id: UUID) -> None:
        task = {
            TaskQueue.REWRITE: rewrite_task,
            TaskQueue.COLLECTION: collection_task,
            TaskQueue.MAINTENANCE: maintenance_task,
        }.get(queue)
        if task is not None:
            await asyncio.to_thread(
                task.apply_async,
                args=(str(task_id),),
                queue=queue,
                task_id=str(event_id),
            )
        else:
            await self.postgres.publish(task_id, queue, event_id)
