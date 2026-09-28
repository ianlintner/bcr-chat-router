"""Shared pytest fixtures.

The application exposes a module-level ``queue_manager`` singleton that talks to
Redis via ``REDIS_URL``. CI has no Redis service, so we swap that singleton's
client for an in-memory ``fakeredis`` instance for the whole test session. This
keeps the tests hermetic while still exercising the real Redis code paths.
"""
import fakeredis
import pytest

from app.queue_manager import queue_manager


@pytest.fixture(scope="session", autouse=True)
def _redis_backed_singleton():
    queue_manager._redis = fakeredis.FakeRedis(decode_responses=True)
    yield


@pytest.fixture(autouse=True)
def clean_queue():
    queue_manager.reset()
    yield
    queue_manager.reset()
