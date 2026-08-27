from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from founderops.extraction import ResumeExtractor
from founderops.models import Scorecard
from founderops.privacy import redact_for_scoring
from founderops.scoring import EvidenceScorer


class EvaluationCase(BaseModel):
    id: str
    resume_text: str
    expected_skills: list[str] = Field(default_factory=list)
    expected_years: float
    expected_recommendation: str
    must_redact: list[str] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    dataset: str
    provider: str
    cases: int
    skill_precision: float
    skill_recall: float
    skill_f1: float
    years_mae: float
    recommendation_agreement: float
    pii_redaction_rate: float
    note: str = "Synthetic benchmark; not a measure of real-world hiring validity."


def load_cases(path: Path) -> list[EvaluationCase]:
    cases = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            cases.append(EvaluationCase.model_validate_json(line))
        except ValueError as error:
            raise ValueError(f"Invalid evaluation case on line {line_number}.") from error
    if not cases:
        raise ValueError("Evaluation dataset is empty.")
    return cases


def evaluate(
    extractor: ResumeExtractor,
    scorer: EvidenceScorer,
    cases: list[EvaluationCase],
    dataset_name: str,
    provider_name: str = "deterministic",
) -> EvaluationReport:
    true_positive = 0
    false_positive = 0
    false_negative = 0
    years_error = 0.0
    correct_recommendations = 0
    pii_checks = 0
    pii_passes = 0

    for case in cases:
        redacted = redact_for_scoring(case.resume_text)
        profile = extractor.extract(redacted.text)
        scorecard: Scorecard = scorer.score(profile)
        predicted = {skill.casefold() for skill in profile.skills}
        expected = {skill.casefold() for skill in case.expected_skills}
        true_positive += len(predicted & expected)
        false_positive += len(predicted - expected)
        false_negative += len(expected - predicted)
        years_error += abs(profile.years_experience - case.expected_years)
        correct_recommendations += scorecard.recommendation == case.expected_recommendation
        for sensitive_value in case.must_redact:
            pii_checks += 1
            pii_passes += sensitive_value not in redacted.text

    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 1.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 1.0
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return EvaluationReport(
        dataset=dataset_name,
        provider=provider_name,
        cases=len(cases),
        skill_precision=round(precision, 4),
        skill_recall=round(recall, 4),
        skill_f1=round(f1, 4),
        years_mae=round(years_error / len(cases), 4),
        recommendation_agreement=round(correct_recommendations / len(cases), 4),
        pii_redaction_rate=round(pii_passes / pii_checks, 4) if pii_checks else 1.0,
    )


def run() -> None:
    from founderops.api import RESOURCE_ROOT, build_extractor

    dataset_path = RESOURCE_ROOT / "evals" / "candidate_profiles.jsonl"
    rubric_path = RESOURCE_ROOT / "configs" / "founders_initiatives.json"
    report = evaluate(
        build_extractor(),
        EvidenceScorer(rubric_path),
        load_cases(dataset_path),
        dataset_path.name,
        provider_name=os.getenv("FOUNDEROPS_PROVIDER", "deterministic"),
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    run()
