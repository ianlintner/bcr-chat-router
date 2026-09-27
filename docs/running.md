# Running locally

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # optional: set TYPESAFE_API_KEY to enable Jev
uvicorn app.main:app --reload --port 8000
```

Open `frontend/demo.html` directly in a browser (or serve it with any static
file server) — it embeds `<bcr-chat-widget ws-url="ws://localhost:8000/ws/chat">`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Liveness check |
| `GET` | `/metrics` | Prometheus text exposition |
| `GET` | `/queues` | Current queue depths per department |
| `POST` | `/session` | Bootstrap a new session id (optional — the widget also generates its own) |
| `WS` | `/ws/chat` | Chat + routing stream |

## Tests

```bash
cd backend
pytest -v
```

All 6 tests run entirely against the rule-based fallback — no live Jev calls,
no network access required, safe for CI. This is also what the `CI` GitHub
Actions workflow (`.github/workflows/ci.yml`) runs on every push/PR to `main`.

## Configuration reference

See `.env.example` at the repo root:

```
TYPESAFE_API_KEY=              # unset = rule-based fallback only
TYPESAFE_MODEL=jev-latest
TYPESAFE_BASE_URL=https://api.typesafe.ai/v1/systemone
TYPESAFE_TIMEOUT_SECONDS=4
MIN_CONFIDENCE=0.55
```
