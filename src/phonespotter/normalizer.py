"""Deterministic telephone normalization and candidate de-duplication."""

from __future__ import annotations

from collections.abc import Iterable

import phonenumbers

from .models import PhoneCandidate


def normalize_phone(raw_number: str, country: str = "DE") -> str | None:
    """Return an E.164 number or None when a value is not plausible."""
    if not raw_number or not raw_number.strip():
        return None
    try:
        parsed = phonenumbers.parse(raw_number.strip(), country.upper())
    except phonenumbers.NumberParseException:
        return None

    if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(parsed):
        return None
    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    digit_count = len(e164.lstrip("+"))
    if not 8 <= digit_count <= 15 or e164 in {"+490000000000", "+490"}:
        return None
    return e164


def normalize_and_dedupe(candidates: Iterable[PhoneCandidate], country: str) -> list[PhoneCandidate]:
    """Normalize candidates and retain the strongest record for each number."""
    by_number: dict[str, PhoneCandidate] = {}
    for candidate in candidates:
        e164 = normalize_phone(candidate.raw_number, country)
        if not e164:
            continue
        normalized = candidate.model_copy(update={"e164_number": e164})
        existing = by_number.get(e164)
        if existing is None or normalized.confidence > existing.confidence:
            by_number[e164] = normalized
    return list(by_number.values())
