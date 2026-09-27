"""Crash/replay/concurrency tests against a disposable PostgreSQL database."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete, func, select, update
from test_auth_postgres import run_postgres_scenario

from news_reposter.background import handlers, worker
from news_reposter.background.contracts import (
    ActiveTaskConflict,
    IdempotencyConflict,
    LostLease,
    RetryableTaskError,
    ReviewRequired,
    TaskQueue,
    TaskState,
)
from news_reposter.background.intents import publication_snapshot, rewrite_snapshot
from news_reposter.background.outbox import PostgresTransport, dispatch_once
from news_reposter.background.store import (
    claim,
    enqueue,
    finish,
    heartbeat,
    recover_expired,
)
from news_reposter.config import get_settings
from news_reposter.db.models import (
    AuditEvent,
    BackgroundTask,
    Post,
    Publication,
    PublicationAttempt,
    PublicationAttemptStatus,
    PublicationStatus,
    QueueItem,
    QueueItemStatus,
    Role,
    Source,
    Target,
    TaskDelivery,
    TaskOutbox,
    User,
)
from news_reposter.db.session import async_session_factory
from news_reposter.llm import RewriteResult
from news_reposter.services.publisher import _loaded_item

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1", reason="requires disposable PostgreSQL"
)


def isolated(scenario):
    async def run():
        try:
            await scenario()
        finally:
            async with async_session_factory() as session:
                await session.execute(
                    delete(BackgroundTask).where(
                        BackgroundTask.target_id.in_(
                            select(Target.target_id).where(
                                Target.name == "Background test"
                            )
                        )
                    )
                )
                await session.execute(
                    delete(BackgroundTask).where(
                        BackgroundTask.idempotency_key.like("test:%")
                    )
                )
                await session.execute(
                    delete(Source).where(Source.name == "Background test")
                )
                await session.execute(
                    delete(Target).where(Target.name == "Background test")
                )
                await session.execute(
                    delete(User).where(User.display_name == "Background test")
                )
                await session.commit()

    run_postgres_scenario(run)


async def create_task(queue=TaskQueue.REWRITE, **kwargs):
    async with async_session_factory() as session:
        task = await enqueue(
            session, queue, "test:" + uuid4().hex, kwargs.pop("payload", {}), **kwargs
        )
        await session.commit()
        return task


async def deliver_and_claim(task):
    await PostgresTransport().publish(task.task_id, task.queue.value, uuid4())
    async with async_session_factory() as session:
        claimed = await claim(session, task.queue, 90)
        await session.commit()
        assert claimed.task_id == task.task_id
        return claimed


async def expire(task):
    async with async_session_factory() as session:
        await session.execute(
            update(BackgroundTask)
            .where(BackgroundTask.task_id == task.task_id)
            .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()


async def material(status=QueueItemStatus.PENDING):
    async with async_session_factory() as session:
        suffix = uuid4().hex
        source = Source(
            name="Background test", platform="vk", url="https://test/" + suffix
        )
        target = Target(
            name="Background test",
            platform="max",
            external_id=str(int(suffix[:12], 16)),
            rewrite_prompt="Rewrite carefully",
        )
        role = await session.scalar(select(Role).where(Role.code == "administrator"))
        user = User(
            username=suffix,
            username_normalized=suffix,
            display_name="Background test",
            password_hash="unused",
            must_change_password=False,
            is_active=True,
            roles=[role],
        )
        session.add_all([source, target, user])
        await session.flush()
        post = Post(
            source_id=source.source_id,
            external_post_id=suffix,
            original_text="original text",
        )
        session.add(post)
        await session.flush()
        item = QueueItem(
            post_id=post.post_id,
            target_id=target.target_id,
            status=status,
            rewritten_text="editor text",
        )
        session.add(item)
        await session.commit()
        return item.queue_item_id, target.target_id, user.user_id


def test_transactional_intent_idempotency_and_active_subject():
    async def scenario():
        key = "test:" + uuid4().hex
        async with async_session_factory() as session:
            task = await enqueue(
                session, TaskQueue.REWRITE, key, {"v": 1}, subject_id=987654
            )
            task_id = task.task_id
            await session.rollback()
        async with async_session_factory() as session:
            assert await session.get(BackgroundTask, task_id) is None
            assert (
                await session.scalar(
                    select(TaskOutbox).where(TaskOutbox.task_id == task_id)
                )
                is None
            )

        async def submit():
            async with async_session_factory() as session:
                task = await enqueue(
                    session, TaskQueue.REWRITE, key, {"v": 1}, subject_id=987654
                )
                await session.commit()
                return task.task_id

        ids = await asyncio.gather(submit(), submit())
        assert ids[0] == ids[1]
        async with async_session_factory() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(TaskOutbox)
                    .where(TaskOutbox.task_id == ids[0])
                )
                == 1
            )
            with pytest.raises(IdempotencyConflict):
                await enqueue(
                    session, TaskQueue.REWRITE, key, {"v": 2}, subject_id=987654
                )
            await session.rollback()
            with pytest.raises(ActiveTaskConflict):
                await enqueue(
                    session,
                    TaskQueue.REWRITE,
                    "test:" + uuid4().hex,
                    {},
                    subject_id=987654,
                )
            await session.rollback()
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(BackgroundTask)
                    .where(BackgroundTask.idempotency_key == key)
                )
                == 1
            )

    isolated(scenario)


def test_lost_ack_redelivery_does_not_duplicate_execution(monkeypatch):
    async def scenario():
        task = await create_task()

        class LostAck:
            async def publish(self, task_id, queue, event_id):
                await PostgresTransport().publish(task_id, queue, event_id)
                raise ConnectionError("accepted but acknowledgement lost")

        assert await dispatch_once(LostAck())
        async with async_session_factory() as session:
            row = await session.scalar(
                select(TaskOutbox).where(TaskOutbox.task_id == task.task_id)
            )
            assert row.delivered_at is None and row.attempts == 1
            row.available_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()
        assert await dispatch_once(PostgresTransport())
        calls = []

        async def handler(task, client):
            calls.append(task.task_id)
            return handlers.Completion({"ok": True})

        monkeypatch.setitem(worker.HANDLERS, TaskQueue.REWRITE, handler)
        assert await worker.run_once(TaskQueue.REWRITE, None)
        assert not await worker.run_once(TaskQueue.REWRITE, None)
        assert calls == [task.task_id]
        async with async_session_factory() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(TaskDelivery)
                    .where(TaskDelivery.task_id == task.task_id)
                )
                == 1
            )
            assert (
                await session.get(BackgroundTask, task.task_id)
            ).state == TaskState.SUCCEEDED

    isolated(scenario)


def test_claim_skips_locked_and_isolates_queues():
    async def scenario():
        task = await create_task()
        await PostgresTransport().publish(task.task_id, task.queue.value, uuid4())
        async with async_session_factory() as first, async_session_factory() as second:
            selected = await claim(first, TaskQueue.REWRITE, 90)
            assert selected is not None
            assert await claim(second, TaskQueue.REWRITE, 90) is None
            assert await claim(second, TaskQueue.PUBLICATION, 90) is None
            await second.rollback()
            await first.commit()

    isolated(scenario)


def test_expiry_fences_old_worker_and_preserves_business_changes():
    async def scenario():
        task = await deliver_and_claim(await create_task())
        old_token = task.lease_token
        await expire(task)
        async with async_session_factory() as session:
            assert not await heartbeat(session, task.task_id, old_token, 90)
            assert await recover_expired(session) == 1
            await session.commit()
            recovered = await session.get(BackgroundTask, task.task_id)
            assert recovered.state == TaskState.RETRY_WAIT
            recovered.available_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()
        async with async_session_factory() as session:
            replacement = await claim(session, TaskQueue.REWRITE, 90)
            assert replacement.lease_token != old_token
            await session.commit()
        applied = []

        async def apply(session):
            applied.append(True)

        async with async_session_factory() as session:
            with pytest.raises(LostLease):
                await finish(
                    session, task.task_id, old_token, TaskState.SUCCEEDED, apply=apply
                )
            await session.rollback()
            assert not applied
            await finish(
                session, task.task_id, replacement.lease_token, TaskState.SUCCEEDED
            )
            await session.commit()

    isolated(scenario)


def test_retry_budget_and_unknown_publication_are_terminal(monkeypatch):
    async def scenario():
        task = await create_task()
        await PostgresTransport().publish(task.task_id, task.queue.value, uuid4())

        async def retry(task, client):
            raise RetryableTaskError("provider_unavailable", 120)

        monkeypatch.setitem(worker.HANDLERS, TaskQueue.REWRITE, retry)
        for attempt in range(1, 4):
            assert await worker.run_once(TaskQueue.REWRITE, None)
            async with async_session_factory() as session:
                current = await session.get(BackgroundTask, task.task_id)
                assert current.attempts == attempt
                assert current.state == (
                    TaskState.FAILED if attempt == 3 else TaskState.RETRY_WAIT
                )
                if attempt < 3:
                    assert current.available_at > datetime.now(UTC) + timedelta(
                        seconds=110
                    )
                    current.available_at = datetime.now(UTC) - timedelta(seconds=1)
                await session.commit()
        publication = await create_task(TaskQueue.PUBLICATION)
        await PostgresTransport().publish(
            publication.task_id, publication.queue.value, uuid4()
        )
        calls = []

        async def uncertain(task, client):
            calls.append(True)
            raise ReviewRequired("publication_outcome_unknown")

        monkeypatch.setitem(worker.HANDLERS, TaskQueue.PUBLICATION, uncertain)
        await worker.run_once(TaskQueue.PUBLICATION, None)
        assert not await worker.run_once(TaskQueue.PUBLICATION, None)
        async with async_session_factory() as session:
            assert (
                await session.get(BackgroundTask, publication.task_id)
            ).state == TaskState.NEEDS_REVIEW
            assert calls == [True]

    isolated(scenario)


def test_failed_completion_rolls_back_business_changes():
    async def scenario():
        task = await deliver_and_claim(await create_task())
        action = "background-test:" + uuid4().hex

        async def apply(session):
            session.add(
                AuditEvent(action=action, subject_type="task", subject_id=1, details={})
            )
            await session.flush()
            raise ValueError("failed before final commit")

        async with async_session_factory() as session:
            with pytest.raises(ValueError):
                await finish(
                    session,
                    task.task_id,
                    task.lease_token,
                    TaskState.SUCCEEDED,
                    apply=apply,
                )
            await session.rollback()
        async with async_session_factory() as session:
            assert (
                await session.get(BackgroundTask, task.task_id)
            ).state == TaskState.RUNNING
            assert (
                await session.scalar(
                    select(AuditEvent).where(AuditEvent.action == action)
                )
                is None
            )

    isolated(scenario)


def test_rewrite_does_not_overwrite_new_editor_text(monkeypatch):
    async def scenario():
        item_id, target_id, user_id = await material()
        async with async_session_factory() as session:
            snapshot = rewrite_snapshot(await _loaded_item(session, item_id))
        task = await create_task(
            subject_id=item_id,
            target_id=target_id,
            actor_user_id=user_id,
            payload={"snapshot": snapshot},
        )
        await PostgresTransport().publish(task.task_id, task.queue.value, uuid4())

        class Provider:
            async def rewrite(self, request):
                async with async_session_factory() as session:
                    await session.execute(
                        update(QueueItem)
                        .where(QueueItem.queue_item_id == item_id)
                        .values(rewritten_text="newer editor text")
                    )
                    await session.commit()
                return RewriteResult(
                    text="old LLM result", provider="fake", model="fake"
                )

        monkeypatch.setattr(handlers, "build_llm_provider", lambda client: Provider())
        await worker.run_once(TaskQueue.REWRITE, None)
        async with async_session_factory() as session:
            current = await session.get(BackgroundTask, task.task_id)
            assert (
                current.state == TaskState.FAILED
                and current.error_code == "material_changed"
            )
            assert (
                await session.get(QueueItem, item_id)
            ).rewritten_text == "newer editor text"

    isolated(scenario)


def test_deleted_actor_cannot_become_system_task(monkeypatch):
    async def scenario():
        item_id, target_id, user_id = await material()
        async with async_session_factory() as session:
            snapshot = rewrite_snapshot(await _loaded_item(session, item_id))
        task = await create_task(
            subject_id=item_id,
            target_id=target_id,
            actor_user_id=user_id,
            payload={"snapshot": snapshot},
        )
        await PostgresTransport().publish(task.task_id, task.queue.value, uuid4())
        async with async_session_factory() as session:
            await session.execute(delete(User).where(User.user_id == user_id))
            await session.commit()
        monkeypatch.setattr(
            handlers,
            "build_llm_provider",
            lambda client: pytest.fail("deleted user must not run LLM"),
        )
        await worker.run_once(TaskQueue.REWRITE, None)
        async with async_session_factory() as session:
            current = await session.get(BackgroundTask, task.task_id)
            assert current.actor_user_id == user_id
            assert (
                current.state == TaskState.FAILED
                and current.error_code == "actor_disabled"
            )

    isolated(scenario)


def test_publication_confirms_domain_and_task_in_one_commit(monkeypatch):
    from news_reposter.services import publisher

    async def scenario():
        item_id, target_id, _ = await material(QueueItemStatus.APPROVED)
        async with async_session_factory() as session:
            snapshot = publication_snapshot(await _loaded_item(session, item_id))
        task = await create_task(
            TaskQueue.PUBLICATION,
            subject_id=item_id,
            target_id=target_id,
            payload={"snapshot": snapshot, "trigger": "scheduled"},
        )
        await PostgresTransport().publish(task.task_id, task.queue.value, uuid4())
        calls = []

        async def send(client, **kwargs):
            calls.append(True)
            return {
                "message": {"body": {"mid": "test-mid"}, "url": "https://test/message"}
            }

        monkeypatch.setattr(publisher, "_publish_with_media_retry", send)
        settings = get_settings()
        old = settings.max_access_token
        settings.max_access_token = "test-token"
        try:
            await worker.run_once(TaskQueue.PUBLICATION, None)
            async with async_session_factory() as session:
                assert (
                    await session.get(BackgroundTask, task.task_id)
                ).state == TaskState.SUCCEEDED
                item = await _loaded_item(session, item_id)
                assert item.status == QueueItemStatus.PUBLISHED
                assert item.publication.status == PublicationStatus.PUBLISHED
                attempt = await session.scalar(
                    select(PublicationAttempt).where(
                        PublicationAttempt.background_task_id == task.task_id
                    )
                )
                assert attempt.status == PublicationAttemptStatus.CONFIRMED
            assert not await worker.run_once(TaskQueue.PUBLICATION, None)
            assert calls == [True]
        finally:
            settings.max_access_token = old

    isolated(scenario)


def test_crashed_sender_requires_review_and_marks_only_its_attempt():
    async def scenario():
        item_id, _, _ = await material(QueueItemStatus.APPROVED)
        task = await deliver_and_claim(
            await create_task(TaskQueue.PUBLICATION, subject_id=item_id)
        )
        async with async_session_factory() as session:
            pub = Publication(
                queue_item_id=item_id, status=PublicationStatus.PUBLISHING, attempts=1
            )
            session.add(pub)
            await session.flush()
            attempt = PublicationAttempt(
                publication_id=pub.publication_id,
                background_task_id=task.task_id,
                attempt_number=1,
                status=PublicationAttemptStatus.SENDING,
                trigger="scheduled",
                prepared_text="text",
                content_fingerprint="0" * 64,
            )
            session.add(attempt)
            await session.commit()
            attempt_id = attempt.publication_attempt_id
        await expire(task)
        async with async_session_factory() as session:
            await recover_expired(session)
            await session.commit()
            assert (
                await session.get(BackgroundTask, task.task_id)
            ).state == TaskState.NEEDS_REVIEW
            assert (
                await session.get(PublicationAttempt, attempt_id)
            ).status == PublicationAttemptStatus.UNKNOWN
            assert (
                await session.get(QueueItem, item_id)
            ).status == QueueItemStatus.PUBLICATION_UNKNOWN
            assert (
                await session.get(Publication, pub.publication_id)
            ).status == PublicationStatus.UNKNOWN

    isolated(scenario)


def test_submission_repeat_csrf_scope_and_pending_cancellation():
    from news_reposter.api.dependencies import get_current_auth
    from news_reposter.auth.context import AuthContext
    from news_reposter.auth.rbac import PermissionCode
    from news_reposter.auth.session_tokens import hash_token
    from news_reposter.main import app

    async def scenario():
        item_id, target_id, user_id = await material()
        token = "test-csrf-token"
        auth = AuthContext(
            session=SimpleNamespace(csrf_token_hash=hash_token(token)),
            user=SimpleNamespace(user_id=user_id, must_change_password=False),
            role_codes=frozenset({"editor"}),
            permission_codes=frozenset(
                {PermissionCode.QUEUE_READ.value, PermissionCode.QUEUE_REWRITE.value}
            ),
            target_ids=frozenset({target_id}),
        )
        app.dependency_overrides[get_current_auth] = lambda: auth
        settings = get_settings()
        previous = settings.background_tasks_enabled
        settings.background_tasks_enabled = True
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="https://test",
                cookies={settings.auth_csrf_cookie_name: token},
            ) as client:
                url = f"/api/v1/queue/{item_id}/rewrite-task"
                data = {"idempotency_key": "one-operation"}
                assert (await client.post(url, json=data)).status_code == 403
                headers = {"X-CSRF-Token": token, "Origin": "https://test"}
                assert (
                    await client.post(
                        url,
                        json=data,
                        headers={**headers, "Origin": "https://evil.test"},
                    )
                ).status_code == 403
                settings.background_tasks_enabled = False
                assert (
                    await client.post(url, json=data, headers=headers)
                ).status_code == 503
                settings.background_tasks_enabled = True
                first = await client.post(url, json=data, headers=headers)
                assert first.status_code == 202, first.text
                task_id = first.json()["task_id"]
                assert (
                    "payload" not in first.json() and "lease_token" not in first.json()
                )
                async with async_session_factory() as session:
                    await session.execute(
                        update(QueueItem)
                        .where(QueueItem.queue_item_id == item_id)
                        .values(
                            rewritten_text="later edit", status=QueueItemStatus.APPROVED
                        )
                    )
                    await session.commit()
                repeat = await client.post(url, json=data, headers=headers)
                assert repeat.status_code == 202 and repeat.json()["task_id"] == task_id
                assert (await client.get(f"/api/v1/tasks/{task_id}")).status_code == 200
                cancelled = await client.post(
                    f"/api/v1/tasks/{task_id}/cancel", headers=headers
                )
                assert (
                    cancelled.status_code == 200
                    and cancelled.json()["state"] == "cancelled"
                )
                assert (
                    await client.post(
                        f"/api/v1/tasks/{task_id}/cancel", headers=headers
                    )
                ).status_code == 200
                forbidden = AuthContext(
                    session=auth.session,
                    user=auth.user,
                    role_codes=auth.role_codes,
                    permission_codes=auth.permission_codes,
                    target_ids=frozenset(),
                )
                app.dependency_overrides[get_current_auth] = lambda: forbidden
                assert (await client.get(f"/api/v1/tasks/{task_id}")).status_code == 404
        finally:
            settings.background_tasks_enabled = previous
            app.dependency_overrides.clear()

    isolated(scenario)


def test_collection_recovery_does_not_interrupt_other_runs():
    from news_reposter.db.models import (
        CollectionRun,
        CollectionRunStatus,
        CollectionRunTrigger,
    )

    async def scenario():
        task = await deliver_and_claim(await create_task(TaskQueue.COLLECTION))
        async with async_session_factory() as session:
            own = CollectionRun(
                trigger=CollectionRunTrigger.SCHEDULED,
                status=CollectionRunStatus.RUNNING,
                background_task_id=task.task_id,
            )
            unrelated = CollectionRun(
                trigger=CollectionRunTrigger.MANUAL, status=CollectionRunStatus.RUNNING
            )
            session.add_all([own, unrelated])
            await session.commit()
            ids = [own.collection_run_id, unrelated.collection_run_id]
        try:
            await expire(task)
            async with async_session_factory() as session:
                await recover_expired(session)
                await session.commit()
                assert (
                    await session.get(CollectionRun, ids[0])
                ).status == CollectionRunStatus.INTERRUPTED
                assert (
                    await session.get(CollectionRun, ids[1])
                ).status == CollectionRunStatus.RUNNING
        finally:
            async with async_session_factory() as session:
                await session.execute(
                    delete(CollectionRun).where(
                        CollectionRun.collection_run_id.in_(ids)
                    )
                )
                await session.commit()

    isolated(scenario)


def test_publication_confirmation_losing_lease_does_not_commit_domain(monkeypatch):
    from news_reposter.services import publisher

    async def scenario():
        item_id, target_id, _ = await material(QueueItemStatus.APPROVED)
        async with async_session_factory() as session:
            snapshot = publication_snapshot(await _loaded_item(session, item_id))
        task = await create_task(
            TaskQueue.PUBLICATION,
            subject_id=item_id,
            target_id=target_id,
            payload={"snapshot": snapshot, "trigger": "scheduled"},
        )
        await PostgresTransport().publish(task.task_id, task.queue.value, uuid4())

        async def send(client, **kwargs):
            return {"message": {"body": {"mid": "test-mid"}}}

        async def lease_lost(*args, **kwargs):
            raise LostLease("lease lost after external send")

        monkeypatch.setattr(publisher, "_publish_with_media_retry", send)
        monkeypatch.setattr(handlers, "finish", lease_lost)
        settings = get_settings()
        old = settings.max_access_token
        settings.max_access_token = "test-token"
        try:
            await worker.run_once(TaskQueue.PUBLICATION, None)
            async with async_session_factory() as session:
                assert (
                    await session.get(BackgroundTask, task.task_id)
                ).state == TaskState.RUNNING
                item = await _loaded_item(session, item_id)
                assert item.publication.status == PublicationStatus.PUBLISHING
                attempt = await session.scalar(
                    select(PublicationAttempt).where(
                        PublicationAttempt.background_task_id == task.task_id
                    )
                )
                assert attempt.status == PublicationAttemptStatus.SENDING
            await expire(task)
            async with async_session_factory() as session:
                await recover_expired(session)
                await session.commit()
                assert (
                    await session.get(BackgroundTask, task.task_id)
                ).state == TaskState.NEEDS_REVIEW
                assert (
                    await session.get(QueueItem, item_id)
                ).status == QueueItemStatus.PUBLICATION_UNKNOWN
        finally:
            settings.max_access_token = old

    isolated(scenario)


def test_scheduler_skips_closed_schedule_slot_and_allows_reschedule():
    from news_reposter.services.publication_scheduler import enqueue_due_publications

    async def scenario():
        item_id, _, _ = await material(QueueItemStatus.SCHEDULED)
        async with async_session_factory() as session:
            await session.execute(
                update(QueueItem)
                .where(QueueItem.queue_item_id == item_id)
                .values(scheduled_at=datetime.now(UTC) - timedelta(minutes=5))
            )
            await session.commit()
            assert await enqueue_due_publications(session) == 1
            await session.commit()
            assert await enqueue_due_publications(session) == 0
            task = await session.scalar(
                select(BackgroundTask).where(BackgroundTask.subject_id == item_id)
            )
            task.state = TaskState.CANCELLED
            await session.commit()
            assert await enqueue_due_publications(session) == 0
            await session.execute(
                update(QueueItem)
                .where(QueueItem.queue_item_id == item_id)
                .values(scheduled_at=datetime.now(UTC) - timedelta(minutes=1))
            )
            await session.commit()
            assert await enqueue_due_publications(session) == 1
            await session.commit()

    isolated(scenario)
