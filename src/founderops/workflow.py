from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from founderops.extraction import ResumeExtractor
from founderops.models import (
    CandidateCreate,
    CandidateRecord,
    CandidateStatus,
    OutreachDraft,
    Review,
    ReviewCreate,
)
from founderops.privacy import redact_for_scoring
from founderops.repository import Repository
from founderops.scoring import EvidenceScorer


class InvalidTransition(ValueError):
    pass


class CandidateWorkflow:
    def __init__(
        self, repository: Repository, extractor: ResumeExtractor, scorer: EvidenceScorer
    ) -> None:
        self.repository = repository
        self.extractor = extractor
        self.scorer = scorer

    def ingest(
        self, request: CandidateCreate, idempotency_key: str | None = None
    ) -> CandidateRecord:
        if idempotency_key:
            existing_id = self.repository.lookup_idempotency_key(idempotency_key)
            if existing_id and (existing := self.repository.get_candidate(existing_id)):
                return existing

        redacted = redact_for_scoring(request.resume_text)
        profile = self.extractor.extract(redacted.text)
        scorecard = self.scorer.score(profile)
        now = datetime.now(UTC)
        candidate = CandidateRecord(
            id=f"cand_{uuid4().hex[:12]}",
            name=request.name,
            role=request.role,
            source=request.source,
            status=CandidateStatus.PENDING_REVIEW,
            profile=profile,
            scorecard=scorecard,
            created_at=now,
            updated_at=now,
        )
        self.repository.save_candidate(candidate)
        self.repository.add_audit(
            candidate.id,
            "candidate_scored",
            "system",
            {
                "redactions": redacted.redaction_count,
                "rubric_version": scorecard.rubric_version,
                "overall": scorecard.overall,
                "note": "Recommendation only; no automated employment decision.",
            },
        )
        if idempotency_key:
            self.repository.save_idempotency_key(idempotency_key, candidate.id)
        return candidate

    def review(self, candidate: CandidateRecord, request: ReviewCreate) -> CandidateRecord:
        if candidate.status is not CandidateStatus.PENDING_REVIEW:
            raise InvalidTransition(f"Cannot review candidate in status '{candidate.status}'.")
        candidate.review = Review(**request.model_dump())
        candidate.status = (
            CandidateStatus.APPROVED if request.decision == "approve" else CandidateStatus.REJECTED
        )
        candidate.updated_at = datetime.now(UTC)
        self.repository.save_candidate(candidate)
        self.repository.add_audit(
            candidate.id,
            f"candidate_{request.decision}d",
            request.reviewer,
            {"notes": request.notes},
        )
        return candidate

    def draft_outreach(self, candidate: CandidateRecord) -> CandidateRecord:
        if candidate.status is not CandidateStatus.APPROVED:
            raise InvalidTransition("A human approval is required before outreach can be drafted.")
        strongest = sorted(
            candidate.scorecard.dimensions, key=lambda item: item.score, reverse=True
        )[:2]
        strengths = " and ".join(item.name.replace("_", " ") for item in strongest)
        candidate.outreach = OutreachDraft(
            subject=f"A builder opportunity: {candidate.role}",
            body=(
                f"Hi {candidate.name},\n\n"
                f"Your evidence in {strengths} stood out during our review for the "
                f"{candidate.role} role. We would like to learn more about the systems "
                "you have shipped and the impact you owned.\n\n"
                "Would you be open to a short introductory conversation next week?\n\n"
                "Best,\nFounderOps Recruiting"
            ),
        )
        candidate.status = CandidateStatus.OUTREACH_DRAFTED
        candidate.updated_at = datetime.now(UTC)
        self.repository.save_candidate(candidate)
        self.repository.add_audit(
            candidate.id, "outreach_drafted", "system", {"delivery": "not_sent"}
        )
        return candidate
