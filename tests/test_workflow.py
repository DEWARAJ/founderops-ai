from pathlib import Path

import pytest

from founderops.extraction import DeterministicResumeExtractor
from founderops.models import CandidateCreate, CandidateStatus, ReviewCreate
from founderops.repository import Repository
from founderops.scoring import EvidenceScorer
from founderops.workflow import CandidateWorkflow, InvalidTransition

PROJECT_ROOT = Path(__file__).parents[1]


@pytest.fixture
def workflow(tmp_path: Path) -> CandidateWorkflow:
    return CandidateWorkflow(
        Repository(tmp_path / "test.db"),
        DeterministicResumeExtractor(),
        EvidenceScorer(PROJECT_ROOT / "configs" / "founders_initiatives.json"),
    )


def sample_request() -> CandidateCreate:
    return CandidateCreate(
        name="Maya Chen",
        role="Founders Initiatives — AI Agents",
        resume_text=(
            "Software engineer with 3+ years at an early-stage startup.\n"
            "Owned a zero to one Python, FastAPI, PostgreSQL, Redis and Docker platform.\n"
            "Integrated OpenAI, LLM evaluations, HubSpot API and idempotent webhooks.\n"
            "Reduced manual review time by 42% and deployed on AWS.\n"
        ),
    )


def test_ingest_scores_evidence_and_queues_human_review(workflow: CandidateWorkflow) -> None:
    candidate = workflow.ingest(sample_request())

    assert candidate.status is CandidateStatus.PENDING_REVIEW
    assert candidate.scorecard.overall > 60
    assert candidate.profile.evidence
    assert workflow.repository.list_audit(candidate.id)[0].action == "candidate_scored"


def test_outreach_is_blocked_until_human_approval(workflow: CandidateWorkflow) -> None:
    candidate = workflow.ingest(sample_request())

    with pytest.raises(InvalidTransition, match="human approval"):
        workflow.draft_outreach(candidate)

    candidate = workflow.review(
        candidate,
        ReviewCreate(decision="approve", reviewer="A. Reviewer", notes="Evidence checked."),
    )
    candidate = workflow.draft_outreach(candidate)

    assert candidate.status is CandidateStatus.OUTREACH_DRAFTED
    assert candidate.outreach is not None
    assert "Maya Chen" in candidate.outreach.body


def test_rejected_candidate_cannot_receive_outreach(workflow: CandidateWorkflow) -> None:
    candidate = workflow.ingest(sample_request())
    candidate = workflow.review(candidate, ReviewCreate(decision="reject", reviewer="A. Reviewer"))

    with pytest.raises(InvalidTransition):
        workflow.draft_outreach(candidate)


def test_idempotent_ingestion_returns_original_candidate(workflow: CandidateWorkflow) -> None:
    first = workflow.ingest(sample_request(), idempotency_key="request-123")
    second = workflow.ingest(sample_request(), idempotency_key="request-123")

    assert first.id == second.id
    assert len(workflow.repository.list_candidates()) == 1
