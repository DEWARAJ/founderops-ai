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
