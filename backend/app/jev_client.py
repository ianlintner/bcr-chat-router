"""Jev (TypeSafe) `choice` classifier client — narrow, typed, opt-in.

Follows decision-model-adapters conventions: bounded timeout, abstain on any
failure, never a generic passthrough, no raw message text in metrics.
"""
from __future__ import annotations

import time

import httpx

from .config import settings
from .metrics import JEV_FAILURES_TOTAL
from .models import DEPARTMENT_DESCRIPTIONS, Department


class JevResult:
    def __init__(self, department: Department, confidence: float, cost_usd: float | None, latency_ms: float):
        self.department = department
        self.confidence = confidence
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms


async def classify_with_jev(text: str, recent_history: list[str]) -> JevResult | None:
    """Returns None on any failure/abstain condition; caller falls back to rules."""
    if not settings.jev_enabled:
        return None

    criteria = {dept.value: desc for dept, desc in DEPARTMENT_DESCRIPTIONS.items()}
    state = {
        "message": text,
        "recent_history": recent_history[-5:],
    }
    payload = {
        "model": settings.typesafe_model,
        "state": state,
        "questions": {
            "department": {
                "type": "choice",
                "criteria": criteria,
            }
        },
    }

    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=settings.typesafe_timeout_seconds) as client:
            resp = await client.post(
                settings.typesafe_base_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.typesafe_api_key}",
                    "Content-Type": "application/json",
                },
            )
    except httpx.TimeoutException:
        JEV_FAILURES_TOTAL.labels(cause="timeout").inc()
        return None
    except httpx.HTTPError:
        JEV_FAILURES_TOTAL.labels(cause="http_error").inc()
        return None

    latency_ms = (time.monotonic() - started) * 1000.0

    if resp.status_code != 200:
        JEV_FAILURES_TOTAL.labels(cause="http_error").inc()
        return None

    try:
        data = resp.json()
        answer = data["questions"]["department"]
        winning_key = answer["choice"]
        confidence = float(answer["confidence"])
        usage = data.get("usage") or {}
        cost_usd = usage.get("cost_usd")
    except (KeyError, TypeError, ValueError):
        JEV_FAILURES_TOTAL.labels(cause="malformed").inc()
        return None

    try:
        department = Department(winning_key)
    except ValueError:
        JEV_FAILURES_TOTAL.labels(cause="malformed").inc()
        return None

    if confidence < settings.min_confidence:
        JEV_FAILURES_TOTAL.labels(cause="low_confidence").inc()
        # Not a hard failure — caller decides whether to escalate; still
        # return the result so the (low) confidence is visible downstream.

    return JevResult(department=department, confidence=confidence, cost_usd=cost_usd, latency_ms=latency_ms)
