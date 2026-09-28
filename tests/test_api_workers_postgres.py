"""Bounded concurrent smoke test for two API processes and PostgreSQL."""

import asyncio
import os
import socket
import subprocess
import sys
import tempfile
import time

import asyncpg
import httpx
import pytest

from news_reposter.config import get_settings

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="requires disposable PostgreSQL",
)


async def exercise_database_health(port):
    settings = get_settings()
    monitor = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )
    stop = asyncio.Event()
    peak_connections = 0

    async def sample_connections():
        nonlocal peak_connections
        while not stop.is_set():
            connections = await monitor.fetchval(
                "SELECT count(*) - 1 FROM pg_stat_activity "
                "WHERE datname = current_database() AND usename = current_user"
            )
            peak_connections = max(peak_connections, connections)
            await asyncio.sleep(0.05)

    sampler = asyncio.create_task(sample_connections())
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            url = f"http://127.0.0.1:{port}/health/database"

            async def request():
                start = time.perf_counter()
                response = await client.get(url, headers={"Connection": "close"})
                assert response.status_code == 200, response.text
                assert response.json() == {"status": "ok", "database": "connected"}
                return time.perf_counter() - start

            started = time.perf_counter()
            latencies = []
            for _ in range(20):
                latencies.extend(await asyncio.gather(*(request() for _ in range(16))))
            elapsed = time.perf_counter() - started
    finally:
        stop.set()
        await sampler
        await monitor.close()

    sorted_latencies = sorted(latencies)
    p95_ms = sorted_latencies[int(len(latencies) * 0.95) - 1] * 1000
    return len(latencies), elapsed, p95_ms, peak_connections


def test_two_api_workers_handle_concurrent_database_requests():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    env = {
        **os.environ,
        "BACKGROUND_TASKS_ENABLED": "true",
        "BACKGROUND_TASK_TRANSPORT": "celery",
    }
    with tempfile.TemporaryFile(mode="w+t") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "news_reposter.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--workers",
                "2",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
        )
        healthy = False
        result = None
        try:
            with httpx.Client(timeout=2, trust_env=False) as client:
                deadline = time.monotonic() + 40
                while time.monotonic() < deadline and process.poll() is None:
                    try:
                        response = client.get(
                            f"http://127.0.0.1:{port}/health/database"
                        )
                        if response.status_code == 200:
                            assert response.json() == {
                                "status": "ok",
                                "database": "connected",
                            }
                            healthy = True
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.25)

                if healthy:
                    result = asyncio.run(exercise_database_health(port))
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        log.seek(0)
        output = log.read()

    assert healthy, f"API workers failed to serve PostgreSQL health:\n{output[-4000:]}"
    assert output.count("Started server process [") == 2, output[-4000:]
    requests, seconds, p95_ms, peak_connections = result
    print(
        f"Two API workers: {requests} concurrent DB requests in {seconds:.2f}s; "
        f"p95={p95_ms:.1f}ms; peak PostgreSQL connections={peak_connections}",
        flush=True,
    )
