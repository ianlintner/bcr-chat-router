"""BCR Chat Router — FastAPI app: REST bootstrap + WebSocket chat + metrics."""
from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from .models import ChatMessage, Department
from .queue_manager import queue_manager
from .router import routing_engine

app = FastAPI(title="BCR Chat Router", version="0.1.0")

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
            message = ChatMessage(session_id=session_id, sender=sender, text=text)
            queue_manager.record_message(session, message)

            recent_history = [m.text for m in session.history[-6:-1]]
            decision = await routing_engine.route(text, recent_history)
            queue_manager.assign(session, decision.department, decision.escalated)

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
