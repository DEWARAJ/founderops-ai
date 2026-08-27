from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from founderops.api import create_app
from founderops.retell import (
    RetellCall,
    candidate_answers,
    candidate_request_from_call,
    verify_retell_signature,
)

FIXTURE = Path(__file__).parents[1] / "examples" / "retell_call_analyzed.json"
SECRET = "retell_test_webhook_key"


def _payload() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _signature(body: bytes, timestamp: int, secret: str = SECRET) -> str:
    digest = hmac.new(
        secret.encode(), body + str(timestamp).encode(), hashlib.sha256
    ).hexdigest()
    return f"v={timestamp},d={digest}"


def test_verifies_signature_and_rejects_tampering_and_replay() -> None:
    body = b'{"event":"call_analyzed"}'
    now = 1_800_000_000_000
    signature = _signature(body, now)

    assert verify_retell_signature(body, SECRET, signature, now_ms=now)
    assert not verify_retell_signature(body + b" ", SECRET, signature, now_ms=now)
    assert not verify_retell_signature(body, SECRET, signature, now_ms=now + 300_001)
    assert not verify_retell_signature(body, SECRET, "invalid", now_ms=now)
    assert not verify_retell_signature(body, "", signature, now_ms=now)
    assert not verify_retell_signature(body, SECRET, None, now_ms=now)


def test_uses_only_candidate_turns_for_evidence() -> None:
    call = RetellCall.model_validate(_payload()["call"])

    transcript = candidate_answers(call)
    request = candidate_request_from_call(call)

    assert "TypeScript" in transcript
    assert "Tell me about Python" not in transcript
    assert request.name == "Maya Patel"
    assert request.source == "retell_voice:call_portfolio_001"


def test_falls_back_to_plain_transcript_without_using_phone_identity() -> None:
    call = RetellCall(
        call_id="call_abcdef123456",
        transcript=(
            "Agent: Tell me about the role.\n"
            "User: I have 3 years building Python and FastAPI services.\n"
            "Agent: What impact did you have?\n"
            "User: I reduced processing time by 25% at a startup."
        ),
    )

    request = candidate_request_from_call(call)

    assert "Tell me about the role" not in request.resume_text
    assert request.name == "Voice candidate 123456"
    assert request.role == "Founders Initiatives — AI Agents"


def test_rejects_excessive_candidate_transcript() -> None:
    call = RetellCall(
        call_id="call_too_large",
        transcript_object=[{"role": "user", "content": "x" * 100_001}],
    )

    with pytest.raises(ValueError, match="processing limit"):
        candidate_request_from_call(call)


def test_signed_call_analyzed_webhook_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RETELL_WEBHOOK_API_KEY", SECRET)
    client = TestClient(create_app(tmp_path / "retell.db"))
    body = FIXTURE.read_bytes()
    timestamp = int(time.time() * 1000)
    headers = {
        "Content-Type": "application/json",
        "X-Retell-Signature": _signature(body, timestamp),
    }

    created = client.post("/api/integrations/retell/webhook", content=body, headers=headers)
    duplicate = client.post("/api/integrations/retell/webhook", content=body, headers=headers)

    assert created.status_code == 202
    assert created.json()["action"] == "candidate_created"
    assert duplicate.status_code == 202
    assert duplicate.json()["action"] == "duplicate"
    assert duplicate.json()["candidate_id"] == created.json()["candidate_id"]

    candidate = client.get(f"/api/candidates/{created.json()['candidate_id']}").json()
    assert candidate["name"] == "Maya Patel"
    assert candidate["status"] == "pending_review"
    assert "TypeScript" in candidate["profile"]["skills"]
    assert "Python" not in candidate["profile"]["skills"]
    assert "OpenAI" not in candidate["profile"]["skills"]
    assert "HubSpot" not in candidate["profile"]["skills"]

    audit = client.get(f"/api/candidates/{candidate['id']}/audit").json()
    assert [event["action"] for event in audit] == [
        "candidate_scored",
        "retell_call_ingested",
    ]
    assert audit[0]["payload"]["redactions"] == 2
    assert audit[1]["payload"]["transcript_persisted"] is False


def test_webhook_rejects_invalid_signature(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RETELL_WEBHOOK_API_KEY", SECRET)
    client = TestClient(create_app(tmp_path / "invalid-retell.db"))

    response = client.post(
        "/api/integrations/retell/webhook",
        content=FIXTURE.read_bytes(),
        headers={"Content-Type": "application/json", "X-Retell-Signature": "invalid"},
    )

    assert response.status_code == 401


def test_webhook_requires_configuration_and_valid_json(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("RETELL_WEBHOOK_API_KEY", raising=False)
    client = TestClient(create_app(tmp_path / "configuration-retell.db"))
    body = b"not-json"
    timestamp = int(time.time() * 1000)

    missing_configuration = client.post(
        "/api/integrations/retell/webhook",
        content=body,
        headers={"X-Retell-Signature": _signature(body, timestamp)},
    )
    assert missing_configuration.status_code == 503

    monkeypatch.setenv("RETELL_WEBHOOK_API_KEY", SECRET)
    invalid_payload = client.post(
        "/api/integrations/retell/webhook",
        content=body,
        headers={"X-Retell-Signature": _signature(body, timestamp)},
    )
    assert invalid_payload.status_code == 422


def test_webhook_acknowledges_non_analysis_events(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RETELL_WEBHOOK_API_KEY", SECRET)
    client = TestClient(create_app(tmp_path / "ignored-retell.db"))
    payload = _payload()
    payload["event"] = "call_ended"
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = int(time.time() * 1000)

    response = client.post(
        "/api/integrations/retell/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Retell-Signature": _signature(body, timestamp),
        },
    )

    assert response.status_code == 202
    assert response.json()["action"] == "ignored"
    assert client.get("/api/candidates").json() == []
