from phonespotter.models import PhoneCandidate
from phonespotter.normalizer import normalize_and_dedupe, normalize_phone


def test_normalizes_german_number_to_e164() -> None:
    assert normalize_phone("030 123456", "DE") == "+4930123456"


def test_rejects_invalid_number() -> None:
    assert normalize_phone("0000", "DE") is None


def test_deduplicates_by_e164_and_preserves_stronger_candidate() -> None:
    candidates = [
        PhoneCandidate(raw_number="030 123456", source="web", confidence=0.5),
        PhoneCandidate(raw_number="+49 30 123456", source="lusha", confidence=0.9),
    ]
    result = normalize_and_dedupe(candidates, "DE")
    assert len(result) == 1
    assert result[0].e164_number == "+4930123456"
    assert result[0].source == "lusha"
