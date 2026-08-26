from types import SimpleNamespace

from founderops.extraction import OpenAIResumeExtractor
from founderops.models import CandidateProfile


class FakeResponses:
    def __init__(self, profile: CandidateProfile) -> None:
        self.profile = profile
        self.request: dict[str, object] = {}

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.request = kwargs
        return SimpleNamespace(output_parsed=self.profile)


def test_openai_adapter_uses_typed_responses_without_storage() -> None:
    profile = CandidateProfile(skills=["Python"])
    responses = FakeResponses(profile)
    extractor = OpenAIResumeExtractor.__new__(OpenAIResumeExtractor)
    extractor.client = SimpleNamespace(responses=responses)
    extractor.model = "test-model"

    result = extractor.extract("Redacted resume with Python evidence")

    assert result == profile
    assert responses.request["text_format"] is CandidateProfile
    assert responses.request["store"] is False
    assert responses.request["model"] == "test-model"
