"""Exercise the real Redis broker, Celery process and PostgreSQL task lease."""

import asyncio
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from test_background_postgres import create_task, isolated

from news_reposter.background.celery_app import MixedTransport
from news_reposter.background.contracts import TaskQueue, TaskState
from news_reposter.background.outbox import dispatch_once, reconcile_celery
from news_reposter.config import get_settings
from news_reposter.db.models import BackgroundTask, TaskOutbox
from news_reposter.db.session import async_session_factory

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1" or os.getenv("RUN_REDIS_TESTS") != "1",
    reason="requires disposable PostgreSQL and dedicated Redis test database",
)


def start_worker(log):
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "news_reposter.background.celery_app:celery_app",
            "worker",
            "--pool=solo",
            "--concurrency=1",
            "--queues=rewrite,collection,maintenance",
            "--loglevel=WARNING",
        ],
        stdout=log,
        stderr=subprocess.STDOUT,
    )


def stop_worker(process):
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


async def wait_for_failure(task_id):
    async with asyncio.timeout(45):
        while True:
            async with async_session_factory() as session:
                task = await session.get(BackgroundTask, task_id)
                if task.state == TaskState.FAILED:
                    return task.attempts, task.error_code
            await asyncio.sleep(0.2)


def test_real_celery_redelivery_after_redis_message_loss():
    async def scenario():
        broker_url = get_settings().redis_url
        broker = urlsplit(broker_url)
        assert broker.hostname in {"localhost", "127.0.0.1"} and broker.path == "/15"
        redis = Redis.from_url(broker_url)
        process = None
        with tempfile.TemporaryFile(mode="w+t") as log:
            try:
                first = await create_task()
                process = start_worker(log)
                assert await dispatch_once(MixedTransport())
                assert await wait_for_failure(first.task_id) == (1, "missing_actor")
                await MixedTransport().publish(first.task_id, "rewrite", uuid4())
                await asyncio.sleep(1)
                async with async_session_factory() as session:
                    assert (
                        await session.get(BackgroundTask, first.task_id)
                    ).attempts == 1

                stop_worker(process)
                process = None
                second = await create_task()
                assert await dispatch_once(MixedTransport())
                # Simulate losing the accepted Redis message while the worker is down.
                assert await redis.delete("rewrite") == 1
                async with async_session_factory() as session:
                    row = await session.scalar(
                        select(TaskOutbox).where(TaskOutbox.task_id == second.task_id)
                    )
                    row.delivered_at = datetime.now(UTC) - timedelta(minutes=3)
                    await session.commit()
                assert await reconcile_celery() == 1
                assert await dispatch_once(MixedTransport())
                process = start_worker(log)
                assert await wait_for_failure(second.task_id) == (1, "missing_actor")
                assert not get_settings().vk_access_token
                collection = await create_task(TaskQueue.COLLECTION)
                assert await dispatch_once(MixedTransport())
                assert await wait_for_failure(collection.task_id) == (
                    1,
                    "vk_not_configured",
                )
                stop_worker(process)
                process = None
                maintenance = await create_task(
                    TaskQueue.MAINTENANCE, payload={"operation": "unsupported"}
                )
                assert await dispatch_once(MixedTransport())
                assert await redis.delete("maintenance") == 1
                async with async_session_factory() as session:
                    row = await session.scalar(
                        select(TaskOutbox).where(TaskOutbox.task_id == maintenance.task_id)
                    )
                    row.delivered_at = datetime.now(UTC) - timedelta(minutes=3)
                    await session.commit()
                assert await reconcile_celery() == 1
                assert await dispatch_once(MixedTransport())
                process = start_worker(log)
                assert await wait_for_failure(maintenance.task_id) == (
                    1,
                    "unsupported_maintenance_operation",
                )
            except Exception:
                log.flush()
                log.seek(0)
                print("Celery worker log:\n", log.read()[-4000:])
                raise
            finally:
                stop_worker(process)
                await redis.aclose()

    isolated(scenario)
