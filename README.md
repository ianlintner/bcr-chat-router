# BCR Chat Router

Customer chat routing backend for the (fictional) **Bureau of Citizen Response (BCR)** —
a federal-style agency handling citizen inquiries across Benefits, Billing/Payments,
Technical/Digital Services, and General Affairs.

Routes each incoming chat message to the right **department queue** (or straight to a
**human agent**) using [TypeSafe Jev](https://typesafe.ai) `choice` classification, with a
deterministic keyword-rule fallback so routing never blocks on an external API.

## Why

Government-style contact centers need reliable, auditable routing: every message must land
in a labeled queue, low-confidence or sensitive messages must escalate to a human, and the
whole thing needs to run without hand-rolling an LLM chat framework. This repo is a minimal,
inspectable reference — not a chat-framework replacement — built in the spirit of embeddable
widgets like [langflow-embedded-chat](https://github.com/langflow-ai/langflow-embedded-chat):
a small web component front end + a plain FastAPI/WebSocket backend.

## Architecture

```
frontend/widget.js        <script> embeddable chat widget (Web Component, no build step)
frontend/demo.html        Static demo page hosting the widget

backend/app/main.py       FastAPI app: REST session bootstrap + WebSocket chat endpoint
backend/app/router.py     RoutingEngine: Jev "choice" classifier + keyword-rule fallback
backend/app/queue_manager.py  Redis-backed department queues + human-agent handoff
backend/app/models.py     Pydantic message/session/routing models
backend/app/metrics.py    Prometheus counters/histograms
backend/tests/            Routing and human-handoff API/WebSocket tests
```

Routing decision flow per message:

1. `RoutingEngine.classify()` asks Jev a single `choice` question over the department
   labels (`benefits`, `billing`, `technical`, `general`, `escalate_human`), state = the
   message + short recent history.
2. If Jev is disabled, times out, or returns malformed/low-confidence output, fall back to
   a deterministic keyword-rule classifier — routing must never abstain into nothing.
3. `QueueManager` places the session in the resolved department queue. Any message tagged
   `escalate_human`, or below `MIN_CONFIDENCE`, always lands in the **human queue**
   regardless of which label won — confidence gates the *routing*, never the escalation.
4. All routing decisions (label, confidence, source=`jev`/`rule`, latency, cost) are
   exported as Prometheus metrics — no raw message text in metric labels.
5. The Human Agent Desk polls `GET /queues/human/sessions` for escalated sessions, including
   the last message and routing confidence. An agent claims one with
   `POST /queues/human/sessions/{session_id}/claim` (or by connecting to
   `WS /ws/agent/{session_id}?agent_id=...`). Once claimed, citizen messages bypass routing
   and are relayed to that agent; agent messages are relayed back over the citizen chat socket.
   The reference implementation keeps these connections in process memory.

Jev is opt-in: set `TYPESAFE_API_KEY` to enable it. With no key set, the service runs
entirely on the rule-based fallback (useful for local dev / CI, and honestly labeled in
metrics as `source="rule"`).

## Departments (fictional)

| Label | Queue | Description |
|---|---|---|
| `benefits` | Benefits & Entitlements | Applications, eligibility, payment status |
| `billing` | Billing & Payments | Invoices, refunds, payment disputes |
| `technical` | Digital Services | Portal logins, forms, technical errors |
| `general` | General Affairs | Anything not covered above |
| `escalate_human` | Human Agent Desk | Complaints, legal threats, self-harm mentions, anything the citizen explicitly asks for a human for |

## Running locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Start Redis locally (for example, with Docker):
docker run --rm -p 6379:6379 redis:7-alpine
cp ../.env.example .env   # optional: set TYPESAFE_API_KEY to enable Jev
uvicorn app.main:app --reload --port 8000
```

Queue sessions and department membership are stored in Redis. Set `REDIS_URL` to
use another Redis instance (default: `redis://localhost:6379/0`).

Open `frontend/demo.html` in a browser (or serve it) — it embeds the widget against
`ws://localhost:8000/ws/chat`.

Metrics: `GET http://localhost:8000/metrics` (Prometheus text format).
Health: `GET http://localhost:8000/healthz`.

## Testing

```bash
cd backend
pytest
```

Tests run entirely against the rule-based fallback (no live Jev calls, no network).

## Status

Early reference implementation. See the GitHub Project board for planned work
(multi-agent presence, persistent queue storage, auth).

## License

MIT — see `LICENSE`.
