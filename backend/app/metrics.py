"""Prometheus metrics for routing decisions."""
from prometheus_client import Counter, Histogram

ROUTING_DECISIONS_TOTAL = Counter(
    "bcr_routing_decisions_total",
    "Routing decisions by resolved department and decision source",
    ["department", "source"],
)

ROUTING_ESCALATIONS_TOTAL = Counter(
    "bcr_routing_escalations_total",
    "Messages escalated to a human agent, by reason",
    ["reason"],
)

ROUTING_LATENCY_SECONDS = Histogram(
    "bcr_routing_latency_seconds",
    "Latency of a single routing decision",
    ["source"],
)

JEV_FAILURES_TOTAL = Counter(
    "bcr_jev_failures_total",
    "Jev classifier call failures by cause (timeout, http_error, malformed, low_confidence)",
    ["cause"],
)
