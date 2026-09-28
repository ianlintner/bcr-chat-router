import fakeredis

from app.models import ChatMessage, Department
from app.queue_manager import QueueManager


def test_sessions_and_queues_persist_between_managers():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    first_manager = QueueManager(redis_client=redis_client)
    session = first_manager.get_or_create_session("session-1")
    first_manager.record_message(
        session,
        ChatMessage(session_id="session-1", sender="citizen", text="I need help"),
    )
    first_manager.assign(session, Department.BENEFITS, escalated=False)

    restarted_manager = QueueManager(redis_client=redis_client)
    restored = restarted_manager.get_or_create_session("session-1")

    assert restored.session_id == "session-1"
    assert [message.text for message in restored.history] == ["I need help"]
    assert restored.department == Department.BENEFITS
    assert restored.escalated is False
    assert restarted_manager.queue_depth(Department.BENEFITS) == 1
    assert restarted_manager.snapshot() == {"benefits": 1}


def test_assign_moves_existing_session_without_duplicate_queue_membership():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    manager = QueueManager(redis_client=redis_client)
    session = manager.get_or_create_session("session-2")

    manager.assign(session, Department.BILLING, escalated=False)
    manager.assign(session, Department.TECHNICAL, escalated=True)

    assert manager.queue_depth(Department.BILLING) == 0
    assert manager.queue_depth(Department.TECHNICAL) == 1
    restored = manager.get_or_create_session("session-2")
    assert restored.department == Department.TECHNICAL
    assert restored.escalated is True


def test_assign_records_confidence():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    manager = QueueManager(redis_client=redis_client)
    session = manager.get_or_create_session("session-3")

    manager.assign(session, Department.GENERAL, escalated=False, confidence=0.42)

    restored = manager.get_or_create_session("session-3")
    assert restored.confidence == 0.42


def test_claim_and_human_sessions_survive_restart():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    manager = QueueManager(redis_client=redis_client)
    session = manager.get_or_create_session("session-4")
    manager.assign(session, Department.ESCALATE_HUMAN, escalated=True)

    restarted_manager = QueueManager(redis_client=redis_client)
    assert [s.session_id for s in restarted_manager.human_sessions()] == ["session-4"]

    claimed = restarted_manager.claim("session-4", "agent-1")
    assert claimed is not None
    assert claimed.claimed_by == "agent-1"
    # The claim is persisted, so a restarted manager sees it too.
    reloaded = QueueManager(redis_client=redis_client).session("session-4")
    assert reloaded is not None
    assert reloaded.claimed_by == "agent-1"


def test_claim_rejects_second_agent_and_missing_session():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    manager = QueueManager(redis_client=redis_client)
    session = manager.get_or_create_session("session-5")
    manager.assign(session, Department.ESCALATE_HUMAN, escalated=True)
    manager.claim("session-5", "agent-1")

    try:
        manager.claim("session-5", "agent-2")
    except ValueError as exc:
        assert "already claimed" in str(exc)
    else:  # pragma: no cover - the claim must be rejected
        raise AssertionError("second claim should raise ValueError")

    # The original agent can re-claim (idempotent) and unknown sessions return None.
    reclaimed = manager.claim("session-5", "agent-1")
    assert reclaimed is not None
    assert reclaimed.claimed_by == "agent-1"
    assert manager.claim("missing-session", "agent-1") is None
    assert manager.session("missing-session") is None
