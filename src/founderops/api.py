from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from founderops.documents import MAX_RESUME_BYTES, DocumentError, extract_resume_text
from founderops.evaluation import EvaluationReport, evaluate, load_cases
from founderops.extraction import DeterministicResumeExtractor, OpenAIResumeExtractor
from founderops.models import AuditEvent, CandidateCreate, CandidateRecord, ReviewCreate
from founderops.repository import Repository
from founderops.scoring import EvidenceScorer
from founderops.workflow import CandidateWorkflow, InvalidTransition

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
RESOURCE_ROOT = PACKAGE_ROOT if (PACKAGE_ROOT / "configs").exists() else PROJECT_ROOT


def build_extractor() -> DeterministicResumeExtractor | OpenAIResumeExtractor:
    provider = os.getenv("FOUNDEROPS_PROVIDER", "deterministic")
    if provider != "openai":
        return DeterministicResumeExtractor()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required when FOUNDEROPS_PROVIDER=openai")
    return OpenAIResumeExtractor(
        api_key=api_key,
        model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
    )


def create_app(database_path: Path | None = None) -> FastAPI:
    database = database_path or Path(
        os.getenv("FOUNDEROPS_DB", Path.cwd() / "data" / "founderops.db")
    )
    repository = Repository(database)
    rubric_path = RESOURCE_ROOT / "configs" / "founders_initiatives.json"
    provider = os.getenv("FOUNDEROPS_PROVIDER", "deterministic")
    workflow = CandidateWorkflow(repository, build_extractor(), EvidenceScorer(rubric_path))

    app = FastAPI(
        title="FounderOps AI",
        version="0.2.0",
        description="Auditable candidate operations with evidence scoring and human approval.",
    )
    app.state.repository = repository
    app.state.workflow = workflow

    static_dir = RESOURCE_ROOT / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "provider": provider, "decision_mode": "human_in_the_loop"}

    @app.get("/api/candidates", response_model=list[CandidateRecord])
    def list_candidates() -> list[CandidateRecord]:
        return repository.list_candidates()

    @app.post("/api/candidates", response_model=CandidateRecord, status_code=201)
    def create_candidate(
        request: CandidateCreate,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> CandidateRecord:
        return workflow.ingest(request, idempotency_key)

    @app.post("/api/candidates/upload", response_model=CandidateRecord, status_code=201)
    async def upload_candidate(
        file: Annotated[UploadFile, File()],
        name: Annotated[str, Form(min_length=1, max_length=120)],
        role: Annotated[str, Form(min_length=1, max_length=160)],
        source: Annotated[str, Form(max_length=80)] = "resume_upload",
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> CandidateRecord:
        content = await file.read(MAX_RESUME_BYTES + 1)
        try:
            resume_text = extract_resume_text(file.filename or "resume.txt", content)
        except DocumentError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        request = CandidateCreate(
            name=name,
            role=role,
            resume_text=resume_text,
            source=source,
        )
        return workflow.ingest(request, idempotency_key)

    @app.get("/api/evaluations/benchmark", response_model=EvaluationReport)
    def benchmark() -> EvaluationReport:
        dataset_path = RESOURCE_ROOT / "evals" / "candidate_profiles.jsonl"
        return evaluate(
            DeterministicResumeExtractor(),
            EvidenceScorer(rubric_path),
            load_cases(dataset_path),
            dataset_path.name,
        )

    def require_candidate(candidate_id: str) -> CandidateRecord:
        candidate = repository.get_candidate(candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return candidate

    @app.get("/api/candidates/{candidate_id}", response_model=CandidateRecord)
    def get_candidate(candidate_id: str) -> CandidateRecord:
        return require_candidate(candidate_id)

    @app.post("/api/candidates/{candidate_id}/review", response_model=CandidateRecord)
    def review_candidate(candidate_id: str, request: ReviewCreate) -> CandidateRecord:
        try:
            return workflow.review(require_candidate(candidate_id), request)
        except InvalidTransition as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/candidates/{candidate_id}/outreach", response_model=CandidateRecord)
    def draft_outreach(candidate_id: str) -> CandidateRecord:
        try:
            return workflow.draft_outreach(require_candidate(candidate_id))
        except InvalidTransition as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/candidates/{candidate_id}/audit", response_model=list[AuditEvent])
    def candidate_audit(candidate_id: str) -> list[AuditEvent]:
        require_candidate(candidate_id)
        return repository.list_audit(candidate_id)

    return app


app = create_app()
