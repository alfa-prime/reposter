"""Measure journal plans on synthetic data in an explicitly selected test DB.

Requires JOURNAL_BENCHMARK_DATABASE_URL, pointing to a disposable PostgreSQL DB
with migrations applied. All synthetic rows are rolled back on exit.
"""

import asyncio
import json
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main() -> None:
    database_url = os.environ["JOURNAL_BENCHMARK_DATABASE_URL"]
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(text("SET LOCAL statement_timeout = '30s'"))
                await connection.execute(
                    text("""
                    INSERT INTO audit_events(action, subject_type, subject_id, details, created_at)
                    SELECT 'benchmark.journal', 'queue_item', n,
                        json_build_object('target_id', n % 20 + 1),
                        now() - (100001 - n) * interval '1 second'
                    FROM generate_series(1, 100000) AS n
                """)
                )
                await connection.execute(
                    text("""
                    INSERT INTO collection_runs(trigger, status, started_at,
                        sources_total, sources_checked, sources_succeeded, sources_failed,
                        posts_found, posts_created, queue_items_created)
                    SELECT CASE WHEN n % 2 = 0 THEN 'manual' ELSE 'scheduled' END,
                        CASE WHEN n % 3 = 0 THEN 'failed' ELSE 'success' END,
                        now() - (50001 - n) * interval '1 second',
                        0, 0, 0, 0, 0, 0, 0 FROM generate_series(1, 50000) AS n
                """)
                )
                # Analyze only the explicitly selected disposable database.
                await connection.execute(text("ANALYZE audit_events"))
                await connection.execute(text("ANALYZE collection_runs"))
                boundary = (
                    await connection.execute(
                        text("""
                    SELECT created_at, audit_event_id FROM audit_events
                    WHERE subject_type='queue_item' AND target_id=9
                    ORDER BY created_at DESC, audit_event_id DESC OFFSET 3999 LIMIT 1
                """)
                    )
                ).one()
                common = """SELECT ae.*, actor.*, qi.queue_item_id FROM audit_events ae
                    LEFT JOIN users actor ON actor.user_id=ae.actor_user_id
                    LEFT JOIN queue_items qi ON ae.subject_type='queue_item' AND qi.queue_item_id=ae.subject_id
                    WHERE ae.subject_type='queue_item' AND ae.target_id=9"""
                queries = {
                    "editorial_first_page": (
                        common
                        + " ORDER BY ae.created_at DESC, ae.audit_event_id DESC LIMIT 21",
                        {},
                    ),
                    "editorial_deep_offset": (
                        common
                        + " ORDER BY ae.created_at DESC, ae.audit_event_id DESC OFFSET 4000 LIMIT 21",
                        {},
                    ),
                    "editorial_deep_cursor": (
                        common
                        + " AND (ae.created_at, ae.audit_event_id) < (:created_at, :row_id) ORDER BY ae.created_at DESC, ae.audit_event_id DESC LIMIT 21",
                        {
                            "created_at": boundary.created_at,
                            "row_id": boundary.audit_event_id,
                        },
                    ),
                    "collection_filtered_cursor": (
                        "SELECT * FROM collection_runs WHERE status='success' AND trigger='manual' AND collection_run_id < 10000 ORDER BY collection_run_id DESC LIMIT 21",
                        {},
                    ),
                }
                print("Synthetic rows: audit_events=100000, collection_runs=50000")
                for name, (sql, parameters) in queries.items():
                    # Warm once, then capture the measured plan.
                    await connection.execute(text(sql), parameters)
                    raw = await connection.scalar(
                        text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql),
                        parameters,
                    )
                    plan = json.loads(raw) if isinstance(raw, str) else raw
                    print(f"\n{name}: {plan[0]['Execution Time']} ms")
                    print(json.dumps(plan, indent=2, default=str))
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
