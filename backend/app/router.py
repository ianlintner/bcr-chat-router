"""RoutingEngine: Jev-first classification with deterministic rule fallback."""
from __future__ import annotations

import time

from .config import settings
from .jev_client import classify_with_jev
from .metrics import ROUTING_DECISIONS_TOTAL, ROUTING_ESCALATIONS_TOTAL, ROUTING_LATENCY_SECONDS
from .models import Department, RoutingDecision, RoutingSource
from .rules import classify_by_rules


class RoutingEngine:
    async def route(self, text: str, recent_history: list[str]) -> RoutingDecision:
        started = time.monotonic()

        jev_result = await classify_with_jev(text, recent_history)

        if jev_result is not None:
            department = jev_result.department
            confidence = jev_result.confidence
            source = RoutingSource.JEV
            cost_usd = jev_result.cost_usd
        else:
            department, confidence = classify_by_rules(text)
            source = RoutingSource.RULE
            cost_usd = None

        escalated = department == Department.ESCALATE_HUMAN or confidence < settings.min_confidence
        if escalated and department != Department.ESCALATE_HUMAN:
            reason = "low_confidence"
            ROUTING_ESCALATIONS_TOTAL.labels(reason=reason).inc()
        elif department == Department.ESCALATE_HUMAN:
            ROUTING_ESCALATIONS_TOTAL.labels(reason="rule_or_model_flagged").inc()

        latency_ms = (time.monotonic() - started) * 1000.0

        ROUTING_DECISIONS_TOTAL.labels(department=department.value, source=source.value).inc()
        ROUTING_LATENCY_SECONDS.labels(source=source.value).observe(latency_ms / 1000.0)

        return RoutingDecision(
            department=department,
            confidence=confidence,
            source=source,
            escalated=escalated,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
        )


routing_engine = RoutingEngine()
