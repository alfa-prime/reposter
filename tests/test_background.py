import asyncio
from uuid import uuid4

import httpx
import pytest

from news_reposter.background.celery_app import MixedTransport, rewrite_task
from news_reposter.background.contracts import (
    POLICIES,
    PermanentTaskError,
    RetryableTaskError,
    TaskQueue,
)
from news_reposter.background.handlers import classify_error
from news_reposter.llm import LLMProviderError
from news_reposter.llm.gigachat import GigaChatProvider


def test_retry_after_is_not_shortened_by_backoff_cap():
    policy = POLICIES[TaskQueue.REWRITE]
    for attempt in [1, 2, 3, 100]:
        delay = policy.delay(attempt)
        assert 0 < delay <= policy.max_delay
        assert policy.delay(attempt, 1200) >= 1200


@pytest.mark.parametrize(
    "status,retryable",
    [(400, False), (401, False), (403, False), (429, True), (500, True), (503, True)],
)
def test_provider_errors_have_structured_retry_policy(status, retryable):
    response = httpx.Response(
        status, json={"message": "provider detail"}, headers={"Retry-After": "60"}
    )
    error = GigaChatProvider._http_error("GigaChat", response)
    assert error.retryable == retryable
    classified = classify_error(error)
    assert isinstance(
        classified, RetryableTaskError if retryable else PermanentTaskError
    )
    if retryable:
        assert classified.retry_after == 60


def test_only_explicit_transient_errors_are_retried():
    assert isinstance(
        classify_error(LLMProviderError("malformed response")), PermanentTaskError
    )
    assert isinstance(classify_error(ValueError("bug")), PermanentTaskError)
    assert isinstance(classify_error(httpx.ConnectError("offline")), RetryableTaskError)


def test_rewrite_transport_sends_only_the_id(monkeypatch):
    calls = []

    def publish(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(rewrite_task, "apply_async", publish)
    task_id, event_id = uuid4(), uuid4()
    asyncio.run(MixedTransport().publish(task_id, "rewrite", event_id))
    assert calls == [
        ((), {"args": (str(task_id),), "queue": "rewrite", "task_id": str(event_id)})
    ]
