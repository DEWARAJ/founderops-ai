from pathlib import Path

from founderops.evaluation import evaluate, load_cases
from founderops.extraction import DeterministicResumeExtractor
from founderops.scoring import EvidenceScorer

PROJECT_ROOT = Path(__file__).parents[1]


def test_synthetic_benchmark_is_reproducible_and_disclosed() -> None:
    dataset = PROJECT_ROOT / "evals" / "candidate_profiles.jsonl"
    cases = load_cases(dataset)
    report = evaluate(
        DeterministicResumeExtractor(),
        EvidenceScorer(PROJECT_ROOT / "configs" / "founders_initiatives.json"),
        cases,
        dataset.name,
    )

    assert report.cases == 10
    assert 0.75 <= report.skill_f1 <= 1
    assert report.years_mae == 0
    assert report.pii_redaction_rate == 1
    assert "Synthetic benchmark" in report.note


def test_rejects_empty_evaluation_dataset(tmp_path: Path) -> None:
    dataset = tmp_path / "empty.jsonl"
    dataset.write_text("\n", encoding="utf-8")

    try:
        load_cases(dataset)
    except ValueError as error:
        assert "empty" in str(error)
    else:
        raise AssertionError("Expected empty evaluation dataset to be rejected")
