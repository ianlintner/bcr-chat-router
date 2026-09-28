"""BCR Chat Router — FastAPI app: REST bootstrap + WebSocket chat + metrics."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from .models import ChatMessage, Department
from .queue_manager import queue_manager
from .router import routing_engine

app = FastAPI(title="BCR Chat Router", version="0.1.0")

# Process-local connection registries. A production deployment should use a
# shared pub/sub broker when running more than one worker.
_agent_connections: dict[str, WebSocket] = {}
_citizen_connections: dict[str, WebSocket] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SessionBootstrapResponse(BaseModel):
    session_id: str


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/queues/human/sessions/{session_id}/claim")
async def claim_human_session(session_id: str, payload: dict) -> dict:
    agent_id = payload.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id.strip():
        raise HTTPException(status_code=422, detail="agent_id is required")
    try:
        session = queue_manager.claim(session_id, agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if session is None:
        raise HTTPException(status_code=404, detail="escalated session not found")
    return {"session_id": session_id, "claimed_by": session.claimed_by}


@app.get("/queues/human/sessions")
async def human_sessions() -> list[dict]:
    return [
        {
            "session_id": session.session_id,
            "last_message": session.history[-1].model_dump() if session.history else None,
            "confidence": session.confidence,
            "claimed_by": session.claimed_by,
        }
        for session in queue_manager.human_sessions()
    ]


@app.websocket("/ws/agent/{session_id}")
async def ws_agent(websocket: WebSocket, session_id: str) -> None:
    agent_id = websocket.query_params.get("agent_id")
    if not agent_id:
        await websocket.close(code=1008, reason="agent_id is required")
        return
    try:
        session = queue_manager.claim(session_id, agent_id)
    except ValueError:
        await websocket.close(code=1008, reason="session is already claimed")
        return
    if session is None:
        await websocket.close(code=1008, reason="escalated session not found")
        return
    await websocket.accept()
    _agent_connections[session_id] = websocket
    try:
        await websocket.send_json({"type": "session_claimed", "session_id": session_id, "claimed_by": agent_id})
        while True:
            payload = await websocket.receive_json()
            text = payload.get("text", "")
            message = ChatMessage(session_id=session_id, sender="agent", text=text)
            queue_manager.record_message(session, message)
            citizen = _citizen_connections.get(session_id)
            if citizen:
                await citizen.send_json({"type": "message", **message.model_dump()})
    except WebSocketDisconnect:
        pass
    finally:
        if _agent_connections.get(session_id) is websocket:
            _agent_connections.pop(session_id, None)


@app.get("/queues")
async def queues() -> dict:
    return queue_manager.snapshot()


@app.post("/session", response_model=SessionBootstrapResponse)
async def create_session() -> SessionBootstrapResponse:
    import uuid

    session_id = str(uuid.uuid4())
    queue_manager.get_or_create_session(session_id)
    return SessionBootstrapResponse(session_id=session_id)


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    await websocket.accept()
    session = None
    try:
        while True:
            payload = await websocket.receive_json()
            session_id = payload.get("session_id") or "anon"
            text = payload.get("text", "")
            sender = payload.get("sender", "citizen")

            session = queue_manager.get_or_create_session(session_id)
            _citizen_connections[session_id] = websocket
            message = ChatMessage(session_id=session_id, sender=sender, text=text)
            queue_manager.record_message(session, message)

            # A claimed session is a transparent relay: do not invoke routing
            # or emit an automated reply after a human takes over.
            if session.claimed_by and sender == "citizen":
                agent = _agent_connections.get(session_id)
                if agent:
                    await agent.send_json({"type": "message", **message.model_dump()})
                continue

            recent_history = [m.text for m in session.history[-6:-1]]
            decision = await routing_engine.route(text, recent_history)
            queue_manager.assign(session, decision.department, decision.escalated, decision.confidence)

            await websocket.send_json(
                {
                    "type": "routing_decision",
                    "session_id": session_id,
                    "department": decision.department.value,
                    "confidence": round(decision.confidence, 3),
                    "source": decision.source.value,
                    "escalated": decision.escalated,
                    "latency_ms": round(decision.latency_ms, 1),
                }
            )

            reply_text = (
                "A human agent has been notified and will join shortly."
                if decision.escalated
                else f"Routed to {decision.department.value.replace('_', ' ').title()}. "
                "An agent will respond shortly."
            )
            await websocket.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "sender": "system",
                    "text": reply_text,
                }
            )
    except WebSocketDisconnect:
        return
    finally:
        if session is not None and _citizen_connections.get(session.session_id) is websocket:
            _citizen_connections.pop(session.session_id, None)
