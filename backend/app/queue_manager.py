"""In-memory department queues + human handoff bookkeeping.

Deliberately simple (dict-of-lists, process memory only) — this is a
reference implementation, not a production queue. Swap for Redis/DB-backed
storage before any real deployment.
"""
from __future__ import annotations

from collections import defaultdict

from .models import ChatMessage, Department, Session


class QueueManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._queues: dict[Department, list[str]] = defaultdict(list)

    def get_or_create_session(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id=session_id)
        return self._sessions[session_id]

    def assign(
        self,
        session: Session,
        department: Department,
        escalated: bool,
        confidence: float | None = None,
    ) -> None:
        for dept, members in self._queues.items():
            if session.session_id in members:
                members.remove(session.session_id)
        session.department = department
        session.escalated = escalated
        session.confidence = confidence
        self._queues[department].append(session.session_id)

    def claim(self, session_id: str, agent_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None or not session.escalated:
            return None
        if session.claimed_by is not None and session.claimed_by != agent_id:
            raise ValueError("session is already claimed")
        session.claimed_by = agent_id
        return session

    def human_sessions(self) -> list[Session]:
        return [session for session in self._sessions.values() if session.escalated]

    def session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def record_message(self, session: Session, message: ChatMessage) -> None:
        session.history.append(message)

    def queue_depth(self, department: Department) -> int:
        return len(self._queues[department])

    def snapshot(self) -> dict[str, int]:
        return {dept.value: len(members) for dept, members in self._queues.items()}


queue_manager = QueueManager()
