from pathlib import Path

from fastapi.testclient import TestClient

from founderops.api import create_app


def test_api_happy_path_and_audit(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    payload = {
        "name": "Maya Chen",
        "role": "Founders Initiatives — AI Agents",
        "resume_text": (
            "Engineer with 3+ years at a startup. Built Python and FastAPI services with Docker. "
            "Integrated OpenAI LLM workflows and HubSpot API webhooks. Reduced review time by 42%."
        ),
        "source": "test",
    }

    created = client.post("/api/candidates", json=payload, headers={"Idempotency-Key": "api-1"})
    assert created.status_code == 201
    candidate_id = created.json()["id"]

    blocked = client.post(f"/api/candidates/{candidate_id}/outreach")
    assert blocked.status_code == 409

    reviewed = client.post(
        f"/api/candidates/{candidate_id}/review",
        json={"decision": "approve", "reviewer": "Test Reviewer", "notes": "Checked"},
    )
    assert reviewed.status_code == 200

    drafted = client.post(f"/api/candidates/{candidate_id}/outreach")
    assert drafted.status_code == 200
    assert drafted.json()["status"] == "outreach_drafted"

    audit = client.get(f"/api/candidates/{candidate_id}/audit")
    assert [event["action"] for event in audit.json()] == [
        "candidate_scored",
        "candidate_approved",
        "outreach_drafted",
    ]


def test_missing_candidate_is_404(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    assert client.get("/api/candidates/does-not-exist").status_code == 404


def test_uploads_text_resume_and_runs_workflow(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "upload.db"))
    response = client.post(
        "/api/candidates/upload",
        data={"name": "Maya Chen", "role": "Founders Initiatives — AI Agents"},
        files={
            "file": (
                "maya-resume.txt",
                b"Engineer with 3+ years building Python, FastAPI and OpenAI workflows. "
                b"Reduced review time by 42% at a startup.",
                "text/plain",
            )
        },
        headers={"Idempotency-Key": "upload-1"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "pending_review"
    assert "Python" in response.json()["profile"]["skills"]


def test_upload_rejects_unsupported_file_type(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "upload.db"))
    response = client.post(
        "/api/candidates/upload",
        data={"name": "Maya Chen", "role": "Founders Initiatives — AI Agents"},
        files={"file": ("resume.exe", b"not a resume" * 10, "application/octet-stream")},
    )

    assert response.status_code == 422
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_rejects_oversized_resume(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "oversized.db"))
    response = client.post(
        "/api/candidates/upload",
        data={"name": "Maya Chen", "role": "Founders Initiatives — AI Agents"},
        files={"file": ("resume.txt", b"a" * (5 * 1024 * 1024 + 1), "text/plain")},
    )

    assert response.status_code == 422
    assert "5 MB" in response.json()["detail"]


def test_benchmark_endpoint_discloses_synthetic_dataset(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "benchmark.db"))

    response = client.get("/api/evaluations/benchmark")

    assert response.status_code == 200
    assert response.json()["cases"] == 10
    assert response.json()["provider"] == "deterministic"
    assert "Synthetic benchmark" in response.json()["note"]
