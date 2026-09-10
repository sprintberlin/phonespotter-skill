from phonespotter.models import ContactInput, PhoneCandidate
from phonespotter.orchestrator import PhoneSpotter


class FakeWeb:
    available = True

    def lookup(self, contact):
        return [PhoneCandidate(raw_number="030 123456", source="openrouter_web_search", phone_type="company_hq", confidence=0.9)]


class FakeLusha:
    def can_lookup(self, contact):
        return True

    def lookup(self, contact):
        return [PhoneCandidate(raw_number="0171 1234567", source="lusha", phone_type="mobile", confidence=0.9)]


class FakeEvaluator:
    available = True

    def __init__(self):
        self.calls = 0

    def evaluate(self, contact, candidates, target):
        self.calls += 1
        numbers = {candidate.source: candidate.e164_number for candidate in candidates}
        if "lusha" not in numbers:
            return {
                "direct_phone": None,
                "mobile_phone": None,
                "company_phone": numbers["openrouter_web_search"],
                "confidence": 0.9,
                "sufficient": False,
                "summary": "Only a company number.",
            }
        return {
            "direct_phone": None,
            "mobile_phone": numbers["lusha"],
            "company_phone": numbers.get("openrouter_web_search"),
            "confidence": 0.9,
            "sufficient": True,
            "summary": "Mobile found.",
        }


def config():
    return {
        "orchestration": {
            "provider_order": ["openrouter_web_search", "lusha"],
            "target": "direct_or_mobile",
            "minimum_confidence": 0.7,
        }
    }


def test_company_central_triggers_lusha_fallback() -> None:
    service = PhoneSpotter.__new__(PhoneSpotter)
    service.config = config()
    service.providers = {"openrouter_web_search": FakeWeb(), "lusha": FakeLusha()}
    service.evaluator = FakeEvaluator()

    result = service.lookup(ContactInput(first_name="Max", last_name="Mustermann", company="Example GmbH"))

    assert result.status == "found"
    assert result.company_phone == "+4930123456"
    assert result.mobile_phone == "+491711234567"
    assert result.providers_checked == ["openrouter_web_search", "lusha"]
    assert service.evaluator.calls == 2


def test_empty_response_skips_evaluation_and_continues() -> None:
    class EmptyWeb(FakeWeb):
        def lookup(self, contact):
            return []

    service = PhoneSpotter.__new__(PhoneSpotter)
    service.config = config()
    service.providers = {"openrouter_web_search": EmptyWeb(), "lusha": FakeLusha()}
    service.evaluator = FakeEvaluator()

    result = service.lookup(ContactInput(first_name="Max", last_name="Mustermann", company="Example GmbH"))

    assert result.status == "found"
    assert result.providers_checked == ["openrouter_web_search", "lusha"]
    assert service.evaluator.calls == 1
