# BCR Chat Router

Documentation for the **Bureau of Citizen Response (BCR) Chat Router** — a
reference implementation of rules-based + [TypeSafe Jev](https://typesafe.ai)-assisted
customer chat routing, built for a fictional government agency.

Repository: [github.com/ianlintner/bcr-chat-router](https://github.com/ianlintner/bcr-chat-router)

## What this is

A minimal, inspectable backend that takes an incoming citizen chat message and
routes it to one of four department queues, or escalates it straight to a
human agent — without hand-rolling an LLM chat framework. The frontend is a
zero-build embeddable Web Component in the spirit of
[langflow-embedded-chat](https://github.com/langflow-ai/langflow-embedded-chat).

## What this is not

- Not a production contact-center platform. Queue state is in-process memory
  (see [Roadmap](roadmap.md) for a Redis-backed persistence task already
  queued).
- Not a general-purpose LLM chat framework. The only model call in the whole
  system is a single, narrowly-typed Jev `choice` classification per message.
- Not an authentication or authorization system. There is no login, no
  per-citizen identity, no session encryption — add these before pointing
  this at anything resembling real citizen data.

## Start here

- [Architecture](architecture.md) — components, request flow, embeddable widget
- [Routing & privacy](routing.md) — the Jev/rule decision boundary, what data leaves the process, confidence handling
- [Running locally](running.md) — dev setup, tests, demo page
- [Metrics](metrics.md) — the Prometheus surface and what each metric actually measures
- [Roadmap](roadmap.md) — known gaps and queued follow-up work
