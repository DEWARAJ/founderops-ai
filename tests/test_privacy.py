from founderops.privacy import redact_for_scoring


def test_redacts_direct_identifiers_and_sensitive_attributes() -> None:
    result = redact_for_scoring(
        "alex@example.com | (415) 555-0188\nGender: nonbinary\nPython engineer"
    )

    assert "alex@example.com" not in result.text
    assert "555-0188" not in result.text
    assert "nonbinary" not in result.text
    assert result.redaction_count == 3
    assert "Python engineer" in result.text
