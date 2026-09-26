"""Rule-based fallback classifier.

Deterministic keyword rules used when Jev is disabled/unavailable or returns
low-confidence output. Never abstains: worst case routes to `general`, and
crisis/complaint keywords always force `escalate_human`.
"""
from __future__ import annotations

from .models import Department

_ESCALATION_KEYWORDS = [
    "lawyer", "lawsuit", "sue", "attorney", "suicide", "kill myself",
    "self harm", "self-harm", "emergency", "speak to a human", "human agent",
    "real person", "supervisor", "manager", "furious", "unacceptable",
]

_KEYWORD_RULES: dict[Department, list[str]] = {
    Department.BENEFITS: [
        "benefit", "eligibility", "eligible", "application", "apply",
        "entitlement", "enrollment", "enroll",
    ],
    Department.BILLING: [
        "invoice", "bill", "billing", "refund", "charge", "payment",
        "overcharged", "dispute", "receipt",
    ],
    Department.TECHNICAL: [
        "login", "log in", "password", "portal", "error", "form won't",
        "website", "app crash", "technical", "upload", "download",
    ],
}


def classify_by_rules(text: str) -> tuple[Department, float]:
    lowered = text.lower()

    for kw in _ESCALATION_KEYWORDS:
        if kw in lowered:
            return Department.ESCALATE_HUMAN, 0.99

    best_dept: Department | None = None
    best_hits = 0
    for dept, keywords in _KEYWORD_RULES.items():
        hits = sum(1 for kw in keywords if kw in lowered)
        if hits > best_hits:
            best_hits = hits
            best_dept = dept

    if best_dept is None:
        return Department.GENERAL, 0.5

    # Confidence scales with keyword hits but is capped; this is a heuristic,
    # not a calibrated probability.
    confidence = min(0.6 + 0.15 * best_hits, 0.95)
    return best_dept, confidence
