from __future__ import annotations

import hashlib
import hmac
import re
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from founderops.models import CandidateCreate

MAX_RETELL_WEBHOOK_BYTES = 1 * 1024 * 1024
SIGNATURE_TOLERANCE_MS = 5 * 60 * 1000
_SIGNATURE_PATTERN = re.compile(r"v=(\d+),d=([0-9a-fA-F]{64})")


class RetellTranscriptTurn(BaseModel):
    role: str
    content: str = ""


class RetellCall(BaseModel):
    call_id: str = Field(min_length=1, max_length=160)
    agent_id: str | None = None
    call_status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    retell_llm_dynamic_variables: dict[str, Any] = Field(default_factory=dict)
    collected_dynamic_variables: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int | None = Field(default=None, ge=0)
    transcript: str = ""
    transcript_object: list[RetellTranscriptTurn] = Field(default_factory=list)
    disconnection_reason: str | None = None
    opt_out_sensitive_data_storage: bool | None = None
    call_analysis: dict[str, Any] | None = None


class RetellWebhookEvent(BaseModel):
    event: str
    call: RetellCall


class RetellWebhookReceipt(BaseModel):
    accepted: bool = True
    action: Literal["candidate_created", "duplicate", "ignored"]
    event: str
    call_id: str
    candidate_id: str | None = None
    message: str


class RetellPayloadError(ValueError):
    pass


def verify_retell_signature(
    raw_body: bytes,
    api_key: str,
    signature: str | None,
    *,
    now_ms: int | None = None,
) -> bool:
    """Verify Retell's timestamped HMAC-SHA256 signature over the raw request body."""
    if not api_key or not signature:
        return False
    match = _SIGNATURE_PATTERN.fullmatch(signature.strip())
    if not match:
        return False
    timestamp_text, supplied_digest = match.groups()
    timestamp = int(timestamp_text)
    current_time = int(time.time() * 1000) if now_ms is None else now_ms
    if abs(current_time - timestamp) > SIGNATURE_TOLERANCE_MS:
        return False
    expected_digest = hmac.new(
        api_key.encode("utf-8"),
        raw_body + timestamp_text.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_digest, supplied_digest.lower())


def candidate_answers(call: RetellCall) -> str:
    """Return candidate utterances only, excluding agent prompts from scoring evidence."""
    turns = [
        turn.content.strip()
        for turn in call.transcript_object
        if turn.role.casefold() == "user"
    ]
    if turns:
        return "\n".join(turn for turn in turns if turn)

    user_lines: list[str] = []
    for line in call.transcript.splitlines():
        speaker, separator, content = line.partition(":")
        if separator and speaker.strip().casefold() == "user":
            user_lines.append(content.strip())
    return "\n".join(line for line in user_lines if line)


def candidate_request_from_call(
    call: RetellCall,
    *,
    default_role: str = "Founders Initiatives — AI Agents",
) -> CandidateCreate:
    transcript = candidate_answers(call)
    if len(transcript) < 40:
        raise RetellPayloadError("The analyzed call has insufficient candidate speech to score.")
    if len(transcript) > 100_000:
        raise RetellPayloadError("The analyzed call exceeds the evidence processing limit.")

    context = {
        **call.metadata,
        **call.retell_llm_dynamic_variables,
        **call.collected_dynamic_variables,
    }
    name = _first_text(context, "candidate_name", "customer_name", "name")
    role = _first_text(context, "target_role", "role")
    return CandidateCreate(
        name=(name or f"Voice candidate {call.call_id[-6:]}")[:120],
        role=(role or default_role)[:160],
        resume_text=transcript,
        source=f"retell_voice:{call.call_id}"[:80],
    )


def _first_text(values: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = values.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
