from __future__ import annotations

import json
from pathlib import Path

from founderops.models import CandidateProfile, DimensionScore, Scorecard


class EvidenceScorer:
    def __init__(self, rubric_path: Path) -> None:
        self.rubric = json.loads(rubric_path.read_text(encoding="utf-8"))

    def score(self, profile: CandidateProfile) -> Scorecard:
        corpus = " ".join(
            profile.skills
            + profile.startup_signals
            + profile.achievements
            + [e.excerpt for e in profile.evidence]
        ).lower()
        dimensions: list[DimensionScore] = []
        missing: list[str] = []
        for item in self.rubric["dimensions"]:
            matched = [keyword for keyword in item["keywords"] if keyword.lower() in corpus]
            evidence = [
                e.excerpt
                for e in profile.evidence
                if e.signal.lower() in {m.lower() for m in matched}
            ]
            evidence.extend(
                signal
                for signal in profile.startup_signals
                if any(m.lower() in signal.lower() for m in matched)
            )
            evidence.extend(
                signal
                for signal in profile.achievements
                if any(m.lower() in signal.lower() for m in matched)
            )
            coverage = min(
                len(set(keyword.lower() for keyword in matched)) / item["target_matches"], 1
            )
            metric_bonus = (
                0.15 if any(char.isdigit() for value in evidence for char in value) else 0
            )
            raw = min((coverage + metric_bonus) * 100, 100)
            if not matched:
                missing.append(item["name"])
            dimensions.append(
                DimensionScore(
                    name=item["name"],
                    score=round(raw, 1),
                    weight=item["weight"],
                    evidence=list(dict.fromkeys(evidence))[:4],
                    rationale=(
                        f"Matched {len(set(matched))} rubric signals with "
                        f"{len(set(evidence))} supporting excerpts."
                    ),
                )
            )
        overall = round(sum(item.score * item.weight for item in dimensions), 1)
        recommendation = (
            "strong_review"
            if overall >= 75
            else "review"
            if overall >= 45
            else "insufficient_evidence"
        )
        return Scorecard(
            overall=overall,
            recommendation=recommendation,
            dimensions=dimensions,
            missing_evidence=missing,
            rubric_version=self.rubric["version"],
        )
