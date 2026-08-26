from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class CandidateStatus(StrEnum):
    INGESTED = "ingested"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    OUTREACH_DRAFTED = "outreach_drafted"


class Evidence(BaseModel):
    signal: str
    excerpt: str
    source: str = "resume"


class CandidateProfile(BaseModel):
    skills: list[str] = Field(default_factory=list)
    years_experience: float = 0
    startup_signals: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class DimensionScore(BaseModel):
    name: str
    score: float = Field(ge=0, le=100)
    weight: float = Field(gt=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    rationale: str


class Scorecard(BaseModel):
    overall: float = Field(ge=0, le=100)
    recommendation: str
    dimensions: list[DimensionScore]
    missing_evidence: list[str] = Field(default_factory=list)
    rubric_version: str


class Review(BaseModel):
    decision: str
    reviewer: str
    notes: str = ""
    reviewed_at: datetime = Field(default_factory=utc_now)


class OutreachDraft(BaseModel):
    subject: str
    body: str
    generated_at: datetime = Field(default_factory=utc_now)


class CandidateRecord(BaseModel):
    id: str
    name: str
    role: str
    source: str
    status: CandidateStatus
    profile: CandidateProfile
    scorecard: Scorecard
    review: Review | None = None
    outreach: OutreachDraft | None = None
    created_at: datetime
    updated_at: datetime


class CandidateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=160)
    resume_text: str = Field(min_length=40, max_length=100_000)
    source: str = Field(default="portfolio_demo", max_length=80)


class ReviewCreate(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    reviewer: str = Field(min_length=2, max_length=120)
    notes: str = Field(default="", max_length=2_000)


class AuditEvent(BaseModel):
    id: int
    candidate_id: str
    action: str
    actor: str
    payload: dict[str, Any]
    created_at: datetime
