import pytest
from fastapi.testclient import TestClient

from app.main import app, human_sessions
from app.models import ChatMessage, Department
from app.queue_manager import queue_manager


@pytest.fixture(autouse=True)
def clean_queue():
    queue_manager._sessions.clear()
    queue_manager._queues.clear()
    yield
    queue_manager._sessions.clear()
    queue_manager._queues.clear()


def escalated_session(session_id="human-1"):
    session = queue_manager.get_or_create_session(session_id)
    queue_manager.record_message(
        session, ChatMessage(session_id=session_id, sender="citizen", text="I need a human")
    )
    queue_manager.assign(session, Department.ESCALATE_HUMAN, True, 0.42)
    return session


def test_human_queue_lists_last_message_and_confidence():
    escalated_session()
    response = TestClient(app).get("/queues/human/sessions")
    assert response.status_code == 200
    assert response.json()[0]["session_id"] == "human-1"
    assert response.json()[0]["last_message"]["text"] == "I need a human"
    assert response.json()[0]["confidence"] == 0.42


def test_agent_can_claim_only_escalated_session():
    escalated_session()
    client = TestClient(app)
    response = client.post(
        "/queues/human/sessions/human-1/claim", json={"agent_id": "agent-7"}
    )
    assert response.status_code == 200
    assert response.json()["claimed_by"] == "agent-7"
    conflict = client.post(
        "/queues/human/sessions/human-1/claim", json={"agent_id": "agent-8"}
    )
    assert conflict.status_code == 409


def test_claimed_chat_skips_routing_and_relays_to_agent():
    escalated_session()
    client = TestClient(app)
    with client.websocket_connect("/ws/agent/human-1?agent_id=agent-7") as agent:
        assert agent.receive_json()["type"] == "session_claimed"
        with client.websocket_connect("/ws/chat") as citizen:
            citizen.send_json(
                {"session_id": "human-1", "sender": "citizen", "text": "Are you there?"}
            )
            relayed = agent.receive_json()
            assert relayed["type"] == "message"
            assert relayed["sender"] == "citizen"
            assert relayed["text"] == "Are you there?"
            # No routing_decision or automated reply is emitted.
            session = queue_manager.session("human-1")
            assert session is not None
            assert session.history[-1].text == "Are you there?"
            agent.send_json({"text": "Yes, I can help."})
            reply = citizen.receive_json()
            assert reply["sender"] == "agent"
            assert reply["text"] == "Yes, I can help."
