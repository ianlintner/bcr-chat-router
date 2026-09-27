# Routing & privacy

## Decision boundary

Following the project's decision-model-adapters conventions, the decision
plane (Jev) and the execution plane (queue assignment, replies) are kept
strictly separate:

- Jev returns **only** a `choice` answer over a fixed, code-defined label
  set (`benefits`, `billing`, `technical`, `general`, `escalate_human`) plus
  a confidence and usage/cost figure. It never picks an execution target,
  never sees or returns free-form text back into the reply path, and has no
  permission to act.
- All authorization, queue placement, and reply text are decided in plain
  Python (`router.py`, `queue_manager.py`, `main.py`), independent of what
  Jev returned.

## What data leaves the process

When `TYPESAFE_API_KEY` is set, each routed message sends to `api.typesafe.ai`:

- The citizen's current message text.
- Up to the last 5 messages of that session's history (for context).
- The fixed criteria map (department names + descriptions) — no other
  metadata, no session ID, no IP, no identity.

When the key is unset, **nothing leaves the process** — the rule-based
fallback runs entirely locally and is the default for dev/CI.

## Confidence handling

- Jev confidence and the rule engine's heuristic confidence are **not**
  compared numerically against each other; each source's confidence only
  gates its own decision.
- `MIN_CONFIDENCE` (default `0.55`) is a floor for the *escalation* decision,
  not a threshold you can tune per department. Any decision below it always
  adds `escalated = true` regardless of which department label won —
  low-confidence traffic never gets silently pinned to a queue.
- `escalate_human` as a returned label is unconditional and independent of
  confidence: certain keyword classes (legal threats, self-harm mentions,
  explicit request for a human) force escalation even if the rest of the
  message looks like ordinary billing/benefits traffic.

## Failure handling

`jev_client.classify_with_jev()` treats every failure mode as **abstain**,
never as a degraded-but-usable answer:

| Cause | Behavior |
|---|---|
| No API key configured | Returns `None` immediately, no network call |
| Timeout (`TYPESAFE_TIMEOUT_SECONDS`, default 4s) | Returns `None`, counted in `bcr_jev_failures_total{cause="timeout"}` |
| Non-200 response / HTTP error | Returns `None`, `cause="http_error"` |
| Missing/malformed `choice`/`confidence`/`usage` fields | Returns `None`, `cause="malformed"` |
| Winning key outside the fixed department enum | Returns `None`, `cause="malformed"` |

On any `None`, `RoutingEngine` falls back to the deterministic rule matcher —
routing throughput is never blocked on Jev's availability.

## What is intentionally out of scope today

- No per-citizen authentication — see [Roadmap](roadmap.md).
- No encryption at rest for session history (in-memory only, process
  lifetime).
- No PII redaction before the Jev call — do not point this at real citizen
  data without adding one; this is a routing reference, not a compliance
  artifact.
