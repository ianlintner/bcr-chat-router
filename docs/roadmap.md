# Roadmap

Known gaps, tracked as kanban tasks against this repo (project `bcr-chat-router`,
completion contract `ianlintner/bcr-chat-router` — they land as PRs, not direct
pushes to `main`):

- **Persist queue state in Redis** — replace the in-memory
  `QueueManager` (`backend/app/queue_manager.py`) with Redis-backed storage
  so queue state survives restarts and can be shared across multiple
  backend instances, while keeping the same public interface.
- **Human-agent presence & session claim** — a minimal surface for a human
  agent to see the Human Agent Desk queue and claim a session, after which
  further messages on that session bypass routing and relay directly to the
  claiming agent.

Other gaps not yet queued as tasks:

- No PII redaction before messages are sent to Jev.
- No authentication/authorization layer for citizens or agents.
- No Grafana dashboard for the Prometheus metrics in `metrics.md`.
- No persistent session history beyond process memory (tied to the Redis
  task above).

Check current status with `hermes kanban --board bcr-chat-router list` or the
[GitHub Project board](https://github.com/users/ianlintner/projects) for this
repo.
