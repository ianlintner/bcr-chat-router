"""Redis-backed department queues and human handoff bookkeeping.

Sessions and department queue membership are persisted in Redis so queue state
survives a process restart and can be shared across multiple backend instances.
A Redis client can be injected for tests (see ``fakeredis``) or for applications
that manage their own connection pool.
"""
from __future__ import annotations

import os
from typing import Any

from redis import Redis

from .models import ChatMessage, Department, Session


class QueueManager:
    """Persist sessions and queue membership in Redis.

    ``REDIS_URL`` defaults to the local Redis instance used by the development
    setup (``redis://localhost:6379/0``).
    """

    _SESSION_PREFIX = "bcr:session:"
    _QUEUE_PREFIX = "bcr:queue:"
    _SESSIONS_INDEX = "bcr:sessions"

    def __init__(self, redis_client: Any | None = None, redis_url: str | None = None) -> None:
        self._redis = redis_client or Redis.from_url(
            redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )

    def _session_key(self, session_id: str) -> str:
        return f"{self._SESSION_PREFIX}{session_id}"

    def _queue_key(self, department: Department) -> str:
        return f"{self._QUEUE_PREFIX}{department.value}"

    def get_or_create_session(self, session_id: str) -> Session:
        key = self._session_key(session_id)
        stored = self._redis.get(key)
        if stored is None:
            session = Session(session_id=session_id)
            # SETNX prevents two backend instances from replacing a session
            # created concurrently; read back the winner in that case.
            if self._redis.set(key, session.model_dump_json(), nx=True):
                self._redis.sadd(self._SESSIONS_INDEX, session_id)
                return session
            stored = self._redis.get(key)
        return Session.model_validate_json(stored)

    def _save_session(self, session: Session) -> None:
        self._redis.set(self._session_key(session.session_id), session.model_dump_json())
        self._redis.sadd(self._SESSIONS_INDEX, session.session_id)

    def assign(
        self,
        session: Session,
        department: Department,
        escalated: bool,
        confidence: float | None = None,
    ) -> None:
        session.department = department
        session.escalated = escalated
        session.confidence = confidence
        session_key = self._session_key(session.session_id)
        queue_keys = [self._queue_key(dept) for dept in Department]
        with self._redis.pipeline() as pipe:
            for queue_key in queue_keys:
                pipe.lrem(queue_key, 0, session.session_id)
            pipe.rpush(self._queue_key(department), session.session_id)
            pipe.set(session_key, session.model_dump_json())
            pipe.sadd(self._SESSIONS_INDEX, session.session_id)
            pipe.execute()

    def claim(self, session_id: str, agent_id: str) -> Session | None:
        session = self.session(session_id)
        if session is None or not session.escalated:
            return None
        # SET NX on a per-session claim lock makes the check-and-set atomic
        # across backend instances, so two agents cannot both win the claim.
        lock_key = f"{self._session_key(session_id)}:claim"
        if self._redis.set(lock_key, agent_id, nx=True):
            pass
        else:
            current = self._redis.get(lock_key)
            if current != agent_id:
                raise ValueError("session is already claimed")
        session.claimed_by = agent_id
        self._save_session(session)
        return session

    def human_sessions(self) -> list[Session]:
        sessions: list[Session] = []
        for raw_session_id in self._redis.smembers(self._SESSIONS_INDEX):
            session_id = (
                raw_session_id.decode()
                if isinstance(raw_session_id, bytes)
                else str(raw_session_id)
            )
            stored = self._redis.get(self._session_key(session_id))
            if stored is None:
                continue
            session = Session.model_validate_json(stored)
            if session.escalated:
                sessions.append(session)
        return sessions

    def session(self, session_id: str) -> Session | None:
        stored = self._redis.get(self._session_key(session_id))
        if stored is None:
            return None
        return Session.model_validate_json(stored)

    def record_message(self, session: Session, message: ChatMessage) -> None:
        session.history.append(message)
        self._save_session(session)

    def queue_depth(self, department: Department) -> int:
        return self._redis.llen(self._queue_key(department))

    def reset(self) -> None:
        """Clear all persisted sessions and queues.

        Intended for tests that share the module-level ``queue_manager`` and
        need a clean slate between cases.
        """
        self._redis.flushdb()

    def snapshot(self) -> dict[str, int]:
        snapshot: dict[str, int] = {}
        for department in Department:
            depth = self.queue_depth(department)
            if depth > 0:
                snapshot[department.value] = depth
        return snapshot


queue_manager = QueueManager()
