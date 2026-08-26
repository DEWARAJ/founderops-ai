import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RedactionResult:
    text: str
    redaction_count: int


_PATTERNS = (
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[EMAIL]"),
    (re.compile(r"(?<!\w)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\w)"), "[PHONE]"),
    (re.compile(r"\b(?:19|20)\d{2}\b(?=\s*(?:birth|born|dob))", re.I), "[DOB]"),
    (
        re.compile(
            r"\b(?:age|gender|sex|race|ethnicity|religion|marital status)\s*:\s*[^\n]+", re.I
        ),
        "[SENSITIVE_ATTRIBUTE]",
    ),
)


def redact_for_scoring(text: str) -> RedactionResult:
    """Remove direct identifiers and explicitly sensitive attributes before scoring."""
    clean = text
    count = 0
    for pattern, replacement in _PATTERNS:
        clean, matches = pattern.subn(replacement, clean)
        count += matches
    return RedactionResult(text=clean, redaction_count=count)
