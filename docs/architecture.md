# Architecture

```
frontend/widget.js        <script> embeddable chat widget (Web Component, no build step)
frontend/demo.html        Static demo page hosting the widget

backend/app/main.py       FastAPI app: REST session bootstrap + WebSocket chat endpoint
backend/app/router.py     RoutingEngine: Jev "choice" classifier + keyword-rule fallback
backend/app/jev_client.py Narrow, opt-in Jev HTTP client (bounded timeout, typed response)
backend/app/rules.py      Deterministic keyword-based fallback classifier
backend/app/queue_manager.py  In-memory department queues + human-agent handoff
backend/app/models.py     Pydantic message/session/routing models
backend/app/metrics.py    Prometheus counters/histograms
```

## Request flow

1. The widget opens a WebSocket to `/ws/chat` and sends `{session_id, sender, text}`.
2. `main.py` looks up or creates the `Session`, appends the message, and calls
   `RoutingEngine.route()`.
3. `RoutingEngine` asks `jev_client.classify_with_jev()` for a decision. This
   call is **opt-in** — it does nothing and returns `None` unless
   `TYPESAFE_API_KEY` is set.
4. If Jev is disabled, times out, errors, or returns a malformed response,
   the engine falls back to `rules.classify_by_rules()` — a deterministic
   keyword matcher. Routing never abstains into nothing; worst case is
   `general` at 0.5 confidence.
5. `QueueManager.assign()` places the session in the resolved department
   queue. Confidence below `MIN_CONFIDENCE`, or a resolved label of
   `escalate_human`, forces routing into the **Human Agent Desk** queue
   regardless of which label the classifier actually picked — the
   escalation gate is independent of (and stricter than) the department
   label itself.
6. The decision (department, confidence, source, latency, cost) is recorded
   in Prometheus and echoed back over the WebSocket as a `routing_decision`
   event, followed by a `message` event with the citizen-facing reply text.

## Departments (fictional)

| Label | Queue | Description |
|---|---|---|
| `benefits` | Benefits & Entitlements | Applications, eligibility, payment status |
| `billing` | Billing & Payments | Invoices, refunds, payment disputes |
| `technical` | Digital Services | Portal logins, forms, technical errors |
| `general` | General Affairs | Anything not covered above |
| `escalate_human` | Human Agent Desk | Complaints, legal threats, self-harm mentions, explicit requests for a human |

## Embeddable widget

`frontend/widget.js` defines `<bcr-chat-widget ws-url="...">` as a plain
Custom Element with a Shadow DOM — no bundler, no framework runtime, one
`<script>` tag. It only knows how to render messages and open a WebSocket;
all routing logic lives server-side, so the widget itself carries no
policy and can be embedded on any citizen-facing page without a build step.
