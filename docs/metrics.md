# Metrics

Exposed at `GET /metrics` in Prometheus text format. No raw message text or
citizen identity ever appears in a label — labels are limited to the fixed
department enum, decision source, and failure cause.

| Metric | Type | Labels | What it measures |
|---|---|---|---|
| `bcr_routing_decisions_total` | Counter | `department`, `source` (`jev`/`rule`) | Every routing decision made, by resolved department and which classifier produced it |
| `bcr_routing_escalations_total` | Counter | `reason` (`low_confidence`/`rule_or_model_flagged`) | Escalations to the human queue, split by why |
| `bcr_routing_latency_seconds` | Histogram | `source` | End-to-end latency of a single routing decision, including the Jev round trip when used |
| `bcr_jev_failures_total` | Counter | `cause` (`timeout`/`http_error`/`malformed`/`low_confidence`) | Jev call failures/abstains — this is what tells you whether the rule fallback is doing most of the work |

## Reading these correctly

- `bcr_jev_failures_total` counting `low_confidence` does **not** mean the
  call failed — Jev still returned a usable (if low-confidence) answer; it's
  tracked here because it's the signal that triggers the escalation floor,
  not because the HTTP call errored.
- Compare `source="jev"` vs `source="rule"` counts on
  `bcr_routing_decisions_total` to see, at a glance, whether Jev is even
  configured/reachable in a given environment — with no API key set, 100%
  of decisions will show `source="rule"`.
- There is currently no Grafana dashboard shipped in this repo (tracked in
  [Roadmap](roadmap.md)); these metrics are designed to be scraped by any
  standard Prometheus setup pointed at `/metrics`.
