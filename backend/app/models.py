"""Pydantic models for chat sessions, messages, and routing decisions."""
from __future__ import annotations

import time
import uuid
from enum import Enum

from pydantic import BaseModel, Field


class Department(str, Enum):
    BENEFITS = "benefits"
    BILLING = "billing"
    TECHNICAL = "technical"
    GENERAL = "general"
    ESCALATE_HUMAN = "escalate_human"


DEPARTMENT_QUEUE_NAMES: dict[Department, str] = {
    Department.BENEFITS: "Benefits & Entitlements",
    Department.BILLING: "Billing & Payments",
    Department.TECHNICAL: "Digital Services",
    Department.GENERAL: "General Affairs",
    Department.ESCALATE_HUMAN: "Human Agent Desk",
}

DEPARTMENT_DESCRIPTIONS: dict[Department, str] = {
    Department.BENEFITS: "Applications, eligibility checks, benefit/entitlement payment status",
    Department.BILLING: "Invoices, refunds, payment disputes, billing errors",
    Department.TECHNICAL: "Portal logins, online forms, technical/digital service errors",
    Department.GENERAL: "General inquiries not covered by another category",
    Department.ESCALATE_HUMAN: (
        "Complaints, legal threats, mentions of self-harm or crisis, explicit requests "
        "for a human agent, or anything the citizen is clearly frustrated about"
    ),
}


class RoutingSource(str, Enum):
    JEV = "jev"
    RULE = "rule"


class ChatMessage(BaseModel):
    session_id: str
    sender: str  # "citizen" | "agent" | "system"
    text: str
    timestamp: float = Field(default_factory=time.time)


class RoutingDecision(BaseModel):
    department: Department
    confidence: float
    source: RoutingSource
    escalated: bool
    latency_ms: float
    cost_usd: float | None = None


class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = Field(default_factory=time.time)
    department: Department | None = None
    escalated: bool = False
    confidence: float | None = None
    claimed_by: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
