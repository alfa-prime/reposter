"""Smoke test for two real API processes sharing PostgreSQL."""

import os
import socket
import subprocess
import sys
import tempfile
import time

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="requires disposable PostgreSQL",
)


def test_two_api_workers_start_and_serve_database_health():
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
                    for _ in range(12):
                        response = client.get(f"http://127.0.0.1:{port}/health")
                        assert response.json() == {"status": "ok"}
                        response = client.get(
                            f"http://127.0.0.1:{port}/health/database"
                        )
                        assert response.json() == {
                            "status": "ok",
                            "database": "connected",
                        }
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
