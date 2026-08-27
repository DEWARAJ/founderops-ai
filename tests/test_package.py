from founderops.api import RESOURCE_ROOT


def test_runtime_resources_are_available() -> None:
    assert (RESOURCE_ROOT / "configs" / "founders_initiatives.json").is_file()
    assert (RESOURCE_ROOT / "evals" / "candidate_profiles.jsonl").is_file()
    assert (RESOURCE_ROOT / "static" / "index.html").is_file()
