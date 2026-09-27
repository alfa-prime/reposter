import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from alembic.config import Config
from sqlalchemy import delete, event, select, text
from test_auth_postgres import run_postgres_scenario

from alembic import command
from news_reposter.api.dependencies import get_current_auth
from news_reposter.api.journal_session import get_journal_session
from news_reposter.auth.rbac import PermissionCode
from news_reposter.config import get_settings
from news_reposter.db.models import (
    AuditEvent,
    CollectionRun,
    CollectionRunStatus,
    CollectionRunTrigger,
)
from news_reposter.db.session import async_session_factory, engine
from news_reposter.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="requires an isolated PostgreSQL test database",
)


def allow_journals() -> None:
    app.dependency_overrides[get_current_auth] = lambda: SimpleNamespace(
        user=SimpleNamespace(must_change_password=False),
        permission_codes=frozenset(
            {PermissionCode.AUDIT_READ.value, PermissionCode.SCHEDULER_READ.value}
        ),
    )


def test_editorial_cursor_handles_equal_timestamps_insertions_and_deleted_boundary() -> (
    None
):
    async def scenario() -> None:
        action = f"test-{uuid4().hex}"
        timestamp = datetime.now(UTC)
        statements = []

        def observe(_conn, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        event.listen(engine.sync_engine, "before_cursor_execute", observe)
        allow_journals()
        try:
            async with async_session_factory() as session:
                rows = [
                    AuditEvent(
                        action=action,
                        subject_type="queue_item",
                        subject_id=i + 1,
                        details={"target_id": 9},
                        created_at=timestamp - timedelta(seconds=i // 15),
                    )
                    for i in range(45)
                ]
                session.add_all(rows)
                session.add(
                    AuditEvent(
                        action=action,
                        subject_type="user",
                        subject_id=1,
                        details={"target_id": 9},
                        created_at=timestamp,
                    )
                )
                await session.commit()
                expected = [
                    row.audit_event_id
                    for row in sorted(
                        rows,
                        key=lambda row: (row.created_at, row.audit_event_id),
                        reverse=True,
                    )
                ]
            statements.clear()
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://test"
            ) as client:
                params = {
                    "pagination": "cursor",
                    "limit": 7,
                    "action": action,
                    "target_id": 9,
                }
                first = await client.get("/api/v1/admin/audit/editorial", params=params)
                assert first.status_code == 200, first.text
                page = first.json()
                assert page["total"] is None
                assert all(
                    row["target_id"] == 9 and not row["material_exists"]
                    for row in page["items"]
                )
                seen = [row["audit_event_id"] for row in page["items"]]
                assert seen == expected[:7]
                boundary = seen[-1]
                async with async_session_factory() as session:
                    session.add(
                        AuditEvent(
                            action=action,
                            subject_type="queue_item",
                            subject_id=999,
                            details={"target_id": 9},
                            created_at=timestamp + timedelta(seconds=1),
                        )
                    )
                    await session.execute(
                        delete(AuditEvent).where(AuditEvent.audit_event_id == boundary)
                    )
                    await session.commit()
                bad_filter = await client.get(
                    "/api/v1/admin/audit/editorial",
                    params={**params, "target_id": 10, "cursor": page["next_cursor"]},
                )
                assert bad_filter.status_code == 422
                while page["has_more"]:
                    response = await client.get(
                        "/api/v1/admin/audit/editorial",
                        params={**params, "cursor": page["next_cursor"]},
                    )
                    assert response.status_code == 200, response.text
                    page = response.json()
                    seen.extend(row["audit_event_id"] for row in page["items"])
                assert seen == expected
                assert page["next_cursor"] is None
                assert not any(
                    "count(" in statement.lower() for statement in statements
                )
                legacy = await client.get(
                    "/api/v1/admin/audit/editorial",
                    params={"action": action, "target_id": 9, "offset": 7, "limit": 7},
                )
                assert legacy.status_code == 200
                assert legacy.json()["total"] == 45
                assert any("count(" in statement.lower() for statement in statements)
                assert (
                    await client.get(
                        "/api/v1/admin/audit/editorial", params={"offset": 10001}
                    )
                ).status_code == 422
        finally:
            app.dependency_overrides.clear()
            event.remove(engine.sync_engine, "before_cursor_execute", observe)
            async with async_session_factory() as session:
                await session.execute(
                    delete(AuditEvent).where(AuditEvent.action == action)
                )
                await session.commit()

    run_postgres_scenario(scenario)


def test_collection_cursor_preserves_history_when_new_runs_arrive() -> None:
    async def scenario() -> None:
        allow_journals()
        ids = []
        try:
            async with async_session_factory() as session:
                rows = [
                    CollectionRun(
                        trigger=CollectionRunTrigger.MANUAL,
                        status=CollectionRunStatus.SUCCESS,
                    )
                    for _ in range(25)
                ]
                session.add_all(rows)
                await session.commit()
                ids.extend(row.collection_run_id for row in rows)
            expected = sorted(ids, reverse=True)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://test"
            ) as client:
                params = {
                    "pagination": "cursor",
                    "limit": 5,
                    "status": "success",
                    "trigger": "manual",
                }
                response = await client.get(
                    "/api/v1/system/collection/runs", params=params
                )
                assert response.status_code == 200, response.text
                page = response.json()
                seen = [row["collection_run_id"] for row in page["items"]]
                assert page["total"] is None
                async with async_session_factory() as session:
                    row = CollectionRun(
                        trigger=CollectionRunTrigger.MANUAL,
                        status=CollectionRunStatus.SUCCESS,
                    )
                    session.add(row)
                    await session.commit()
                    ids.append(row.collection_run_id)
                while page["has_more"]:
                    response = await client.get(
                        "/api/v1/system/collection/runs",
                        params={**params, "cursor": page["next_cursor"]},
                    )
                    assert response.status_code == 200, response.text
                    page = response.json()
                    seen.extend(row["collection_run_id"] for row in page["items"])
                assert seen == expected
        finally:
            app.dependency_overrides.clear()
            async with async_session_factory() as session:
                await session.execute(
                    delete(CollectionRun).where(
                        CollectionRun.collection_run_id.in_(ids)
                    )
                )
                await session.commit()

    run_postgres_scenario(scenario)


def test_statement_timeout_is_503_and_does_not_leak_to_the_next_transaction() -> None:
    async def scenario() -> None:
        settings = get_settings()
        previous_timeout = settings.database_journal_timeout_seconds
        settings.database_journal_timeout_seconds = 0.02
        try:
            async with async_session_factory() as session:
                dependency = get_journal_session(session)
                await anext(dependency)
                try:
                    await session.execute(text("SELECT pg_sleep(0.2)"))
                except Exception as exc:
                    with pytest.raises(Exception) as error:
                        await dependency.athrow(exc)
                    assert error.value.status_code == 503
                else:
                    pytest.fail(
                        "server-side statement timeout did not cancel the query"
                    )
                assert await session.scalar(text("SHOW statement_timeout")) == "0"
                assert await session.scalar(text("SELECT 1")) == 1
        finally:
            settings.database_journal_timeout_seconds = previous_timeout

    run_postgres_scenario(scenario)


def test_migration_backfills_snapshot_without_rejecting_malformed_historical_json() -> (
    None
):
    # This test is for the disposable CI database, never for a production DB.
    config = Config("alembic.ini")
    action = f"migration-{uuid4().hex}"
    command.downgrade(config, "0018_publication_recovery")

    async def seed() -> None:
        async with async_session_factory() as session:
            for value in ["9", '"9"', "null", '"bad"', "2147483648", "-1", "true"]:
                await session.execute(
                    text(
                        "INSERT INTO audit_events(action, subject_type, subject_id, details) VALUES (:action, 'queue_item', 1, CAST(:details AS json))"
                    ),
                    {"action": action, "details": '{"target_id":' + value + "}"},
                )
            await session.commit()

    try:
        run_postgres_scenario(seed)
        command.upgrade(config, "head")

        async def verify() -> None:
            async with async_session_factory() as session:
                values = list(
                    await session.scalars(
                        select(AuditEvent.target_id)
                        .where(AuditEvent.action == action)
                        .order_by(AuditEvent.audit_event_id)
                    )
                )
                assert values == [9, 9, None, None, None, None, None]
                # An old writer supplies JSON only; the generated column still fills.
                row = AuditEvent(
                    action=action,
                    subject_type="queue_item",
                    subject_id=1,
                    details={"target_id": 12},
                )
                session.add(row)
                await session.flush()
                assert row.target_id == 12
                await session.execute(
                    delete(AuditEvent).where(AuditEvent.action == action)
                )
                await session.commit()

        run_postgres_scenario(verify)
    finally:
        command.upgrade(config, "head")


def test_user_audit_cursor_and_legacy_count_use_the_same_filters() -> None:
    async def scenario() -> None:
        action = f"user-test-{uuid4().hex}"
        timestamp = datetime.now(UTC)
        allow_journals()
        try:
            async with async_session_factory() as session:
                rows = [
                    AuditEvent(
                        action=action,
                        subject_type="user",
                        subject_id=999,
                        details={},
                        created_at=timestamp,
                    )
                    for _ in range(3)
                ]
                session.add_all(rows)
                session.add(
                    AuditEvent(
                        action=action,
                        subject_type="queue_item",
                        subject_id=999,
                        details={},
                        created_at=timestamp,
                    )
                )
                await session.commit()
                expected = sorted([row.audit_event_id for row in rows], reverse=True)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://test"
            ) as client:
                params = {"pagination": "cursor", "limit": 2, "action": action}
                first = await client.get("/api/v1/admin/audit", params=params)
                assert first.status_code == 200, first.text
                page = first.json()
                assert page["total"] is None
                assert [row["audit_event_id"] for row in page["items"]] == expected[:2]
                second = await client.get(
                    "/api/v1/admin/audit",
                    params={**params, "cursor": page["next_cursor"]},
                )
                assert second.status_code == 200, second.text
                assert [
                    row["audit_event_id"] for row in second.json()["items"]
                ] == expected[2:]
                assert not second.json()["has_more"]
                legacy = await client.get(
                    "/api/v1/admin/audit", params={"action": action}
                )
                assert legacy.json()["total"] == 3
        finally:
            app.dependency_overrides.clear()
            async with async_session_factory() as session:
                await session.execute(
                    delete(AuditEvent).where(AuditEvent.action == action)
                )
                await session.commit()

    run_postgres_scenario(scenario)
