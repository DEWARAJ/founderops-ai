from __future__ import annotations

import re
from typing import Protocol

from founderops.models import CandidateProfile, Evidence

KNOWN_SKILLS = (
    "Python",
    "TypeScript",
    "JavaScript",
    "React",
    "FastAPI",
    "Node.js",
    "PostgreSQL",
    "Redis",
    "Docker",
    "AWS",
    "OpenAI",
    "Claude",
    "Gemini",
    "LLM",
    "n8n",
    "Zapier",
    "Salesforce",
    "HubSpot",
)


class ResumeExtractor(Protocol):
    def extract(self, text: str) -> CandidateProfile: ...


class DeterministicResumeExtractor:
    """Offline extractor used for reproducible demos and tests."""

    def extract(self, text: str) -> CandidateProfile:
        lines = [line.strip(" -•\t") for line in text.splitlines() if line.strip()]
        lowered = text.lower()
        skills = [skill for skill in KNOWN_SKILLS if skill.lower() in lowered]
        evidence: list[Evidence] = []
        for skill in skills:
            matching = next((line for line in lines if skill.lower() in line.lower()), skill)
            evidence.append(Evidence(signal=skill, excerpt=matching[:240]))

        years = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\+?\s+years?", lowered)]
        startup = [
            line
            for line in lines
            if re.search(r"\b(startup|founder|0→1|0-to-1|zero to one|first hire)\b", line, re.I)
        ]
        achievements = [
            line
            for line in lines
            if re.search(
                r"(?:\b\d+(?:\.\d+)?%|\$\d+|\b\d+x\b|reduced|increased|grew|saved)", line, re.I
            )
        ]
        return CandidateProfile(
            skills=skills,
            years_experience=max(years, default=0),
            startup_signals=startup[:6],
            achievements=achievements[:8],
            evidence=evidence[:20],
        )


class OpenAIResumeExtractor:
    """Optional structured-output adapter; never used unless explicitly configured."""

    def __init__(self, api_key: str, model: str) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def extract(self, text: str) -> CandidateProfile:
        response = self.client.responses.parse(
            model=self.model,
            store=False,
            instructions=(
                "Extract only job-relevant facts explicitly supported by the resume. "
                "Do not infer protected traits. Every skill must have a short evidence excerpt."
            ),
            input=text,
            text_format=CandidateProfile,
        )
        if response.output_parsed is None:
            raise ValueError("The model did not return a candidate profile.")
        return response.output_parsed
