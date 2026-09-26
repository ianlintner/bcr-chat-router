import pytest

from app.models import Department
from app.router import routing_engine


@pytest.mark.asyncio
async def test_benefits_routing():
    decision = await routing_engine.route("I want to check my benefit eligibility application", [])
    assert decision.department == Department.BENEFITS
    assert decision.source.value == "rule"


@pytest.mark.asyncio
async def test_billing_routing():
    decision = await routing_engine.route("I was overcharged on my last invoice, I need a refund", [])
    assert decision.department == Department.BILLING


@pytest.mark.asyncio
async def test_technical_routing():
    decision = await routing_engine.route("I can't log in to the portal, password error", [])
    assert decision.department == Department.TECHNICAL


@pytest.mark.asyncio
async def test_general_fallback():
    decision = await routing_engine.route("Hi, what are your office hours?", [])
    assert decision.department == Department.GENERAL


@pytest.mark.asyncio
async def test_escalation_keyword_forces_human():
    decision = await routing_engine.route("I want to speak to a human agent right now, this is unacceptable", [])
    assert decision.department == Department.ESCALATE_HUMAN
    assert decision.escalated is True


@pytest.mark.asyncio
async def test_low_confidence_forces_escalation_flag():
    # Empty-ish/ambiguous text -> general with default 0.5 confidence, below
    # MIN_CONFIDENCE (0.55) -> escalated flag should still be set even though
    # the department itself is "general".
    decision = await routing_engine.route("hmm", [])
    assert decision.department == Department.GENERAL
    assert decision.escalated is True
