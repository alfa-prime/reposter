"""Business adapters; a Celery consumer can invoke the same fenced runner."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from types import SimpleNamespace

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.auth.context import AuthContext
from news_reposter.auth.rbac import PermissionCode
from news_reposter.background.contracts import (
    PermanentTaskError,
    RetryableTaskError,
    ReviewRequired,
    TaskQueue,
    TaskState,
)
from news_reposter.background.intents import publication_snapshot, rewrite_snapshot
from news_reposter.background.store import finish, owned
from news_reposter.db.models import (
    BackgroundTask,
    CollectionRunTrigger,
    PublicationAttemptStatus,
    PublicationStatus,
    QueueItemStatus,
)
from news_reposter.db.session import async_session_factory
from news_reposter.llm import LLMProviderError, RewriteRequest, build_llm_provider
from news_reposter.repositories.user import UserRepository
from news_reposter.services.audit import record_editorial_event
from news_reposter.services.collector import (
    CollectionAlreadyRunningError,
    collect_active_sources_once,
)
from news_reposter.services.media_cleanup import cleanup_media_once
from news_reposter.services.publisher import (
    PublicationError,
    PublicationUnknownError,
    _loaded_item,
    publish_queue_item,
)


@dataclass
class Completion:
    result: dict
    apply: Callable[[AsyncSession], Awaitable[None]] | None = None
    completed: bool = False


async def authorize(
    session: AsyncSession, task: BackgroundTask, permission: PermissionCode
) -> None:
    if task.actor_user_id is None:
        if task.queue == TaskQueue.REWRITE:
            raise PermanentTaskError("missing_actor")
        return
    user = await UserRepository(session).get_by_id_for_update(task.actor_user_id)
    if user is None or not user.is_active or user.must_change_password:
        raise PermanentTaskError("actor_disabled")
    context = AuthContext.from_session(SimpleNamespace(user=user))
    if permission.value not in context.permission_codes:
        raise PermanentTaskError("permission_revoked")
    if task.target_id is not None and not context.can_access_target(task.target_id):
        raise PermanentTaskError("target_access_revoked")


async def rewrite(task: BackgroundTask, client: httpx.AsyncClient) -> Completion:
    async with async_session_factory() as session:
        await authorize(session, task, PermissionCode.QUEUE_REWRITE)
        item = await _loaded_item(session, task.subject_id, for_update=True)
        if item is None:
            raise PermanentTaskError("material_deleted")
        if rewrite_snapshot(item) != task.payload["snapshot"] or item.status not in {
            QueueItemStatus.PENDING,
            QueueItemStatus.REWRITING,
            QueueItemStatus.REJECTED,
        }:
            raise PermanentTaskError("material_changed")
        await session.commit()
    try:
        provider = build_llm_provider(client)
    except (RuntimeError, ValueError) as exc:
        raise PermanentTaskError("llm_not_configured") from exc
    snapshot = task.payload["snapshot"]
    result = await provider.rewrite(
        RewriteRequest(
            text=snapshot["source_text"], system_prompt=snapshot["system_prompt"]
        )
    )

    async def apply(session: AsyncSession):
        await authorize(session, task, PermissionCode.QUEUE_REWRITE)
        current = await _loaded_item(session, task.subject_id, for_update=True)
        if current is None or rewrite_snapshot(current) != snapshot:
            raise PermanentTaskError("material_changed")
        previous_status = current.status.value
        current.rewritten_text = result.text
        current.status = QueueItemStatus.REWRITING
        await record_editorial_event(
            session,
            actor_user_id=task.actor_user_id,
            item=current,
            action="editorial.rewritten",
            details={
                "previous_status": previous_status,
                "status": current.status.value,
                "task_id": str(task.task_id),
            },
            commit=False,
        )

    return Completion(
        {"queue_item_id": task.subject_id, "provider": result.provider}, apply
    )


async def publication(task: BackgroundTask, client: httpx.AsyncClient) -> Completion:
    result = {"queue_item_id": task.subject_id}
    manual_retry = (
        task.payload.get("trigger") == "manual_retry"
        and task.payload.get("accept_duplicate_risk") is True
    )

    async def confirmed(session, item):
        await finish(
            session, task.task_id, task.lease_token, TaskState.SUCCEEDED, result=result
        )
        if task.actor_user_id is not None:
            await record_editorial_event(
                session,
                actor_user_id=task.actor_user_id,
                item=item,
                action="editorial.published",
                details={"task_id": str(task.task_id)},
                commit=False,
            )
            if manual_retry:
                await record_editorial_event(
                    session,
                    actor_user_id=task.actor_user_id,
                    item=item,
                    action="editorial.publication_retried",
                    details={
                        "task_id": str(task.task_id),
                        "accepted_duplicate_risk": True,
                    },
                    commit=False,
                )

    async with async_session_factory() as session:
        await owned(session, task.task_id, task.lease_token)
        await authorize(session, task, PermissionCode.QUEUE_PUBLISH)
        item = await _loaded_item(session, task.subject_id, for_update=True)
        if item is None:
            raise PermanentTaskError("material_deleted")
        if item.publication and item.publication.status == PublicationStatus.PUBLISHED:
            return Completion(
                {"queue_item_id": task.subject_id, "already_published": True}
            )
        if item.publication and item.publication.status == PublicationStatus.PUBLISHING:
            raise ReviewRequired("publication_outcome_unknown")
        if item.publication and item.publication.status == PublicationStatus.UNKNOWN:
            latest = max(
                item.publication.attempt_history,
                key=lambda attempt: attempt.attempt_number,
                default=None,
            )
            checked = (
                latest is not None
                and latest.status == PublicationAttemptStatus.UNKNOWN
                and latest.check_count >= 1
            )
            if (
                not manual_retry
                or item.status != QueueItemStatus.PUBLICATION_UNKNOWN
                or not checked
            ):
                raise ReviewRequired("publication_outcome_unknown")
        if publication_snapshot(item) != task.payload["snapshot"]:
            raise PermanentTaskError("material_changed")
        # Keep the item row locked until publisher reserves its sending attempt.
        try:
            await publish_queue_item(
                session,
                task.subject_id,
                client,
                actor_user_id=task.actor_user_id,
                trigger=task.payload["trigger"],
                task_id=task.task_id,
                on_success=confirmed,
                allow_unknown_retry=manual_retry,
            )
        except PublicationUnknownError as exc:
            raise ReviewRequired("publication_outcome_unknown") from exc
        except PublicationError as exc:
            # A definitive 429 or a pre-send transient upload failure can be retried.
            cause = exc.__cause__
            status = getattr(cause, "status_code", None)
            if status == 429 or (status is not None and status >= 500):
                raise RetryableTaskError("publication_provider_unavailable") from exc
            raise PermanentTaskError("publication_rejected") from exc
    return Completion(result, completed=True)


async def collection(task: BackgroundTask, client: httpx.AsyncClient) -> Completion:
    async with async_session_factory() as session:
        await authorize(session, task, PermissionCode.COLLECTION_RUN)
        await session.commit()
    from news_reposter.config import get_settings

    if not get_settings().vk_access_token:
        raise PermanentTaskError("vk_not_configured")
    try:
        summary = await collect_active_sources_once(
            client, CollectionRunTrigger(task.payload["trigger"]), task_id=task.task_id
        )
    except CollectionAlreadyRunningError as exc:
        raise RetryableTaskError("collection_busy") from exc
    # Per-source failures are recorded in collection history; avoid restarting all
    # sources blindly. A later scheduled run retries through their checkpoints.
    return Completion({**summary, "partial": bool(summary["errors"])})


async def maintenance(task: BackgroundTask, client: httpx.AsyncClient) -> Completion:
    if task.payload != {"operation": "media_cleanup"}:
        raise PermanentTaskError("unsupported_maintenance_operation")
    removed_temp, removed_orphans = await cleanup_media_once()
    return Completion(
        {"removed_temp": removed_temp, "removed_orphans": removed_orphans}
    )


HANDLERS = {
    TaskQueue.REWRITE: rewrite,
    TaskQueue.COLLECTION: collection,
    TaskQueue.PUBLICATION: publication,
    TaskQueue.MAINTENANCE: maintenance,
}


def classify_error(error: Exception) -> Exception:
    if isinstance(error, (PermanentTaskError, ReviewRequired, RetryableTaskError)):
        return error
    if isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code == 429 or error.response.status_code >= 500:
            value = error.response.headers.get("Retry-After", "")
            try:
                retry_after = float(value)
            except ValueError:
                retry_after = None
            return RetryableTaskError("http_provider_unavailable", retry_after)
        return PermanentTaskError("http_provider_rejected")
    if isinstance(error, (httpx.TransportError, TimeoutError)):
        return RetryableTaskError("provider_timeout")
    if isinstance(error, LLMProviderError):
        if error.retryable:
            return RetryableTaskError("llm_provider_unavailable", error.retry_after)
        return PermanentTaskError("llm_provider_error")
    return PermanentTaskError("unexpected_task_error")
