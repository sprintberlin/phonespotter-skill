from phonespotter.evaluator import OpenRouterEvaluator
from phonespotter.models import ContactInput, PhoneCandidate


class FakeResponse:
    def __init__(self, content: str) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


def test_rejects_hallucinated_candidate(monkeypatch) -> None:
    evaluator = OpenRouterEvaluator({"openrouter": {
        "api_key_env": "FAKE_KEY",
        "evaluation_model": "test-model",
        "base_url": "https://example.com/v1",
        "timeout_seconds": 10,
    }})
    monkeypatch.setenv("FAKE_KEY", "test-key")
    monkeypatch.setattr(
        "requests.post",
        lambda *args, **kwargs: FakeResponse(
            '{"direct_phone":"+4930999999","mobile_phone":null,"company_phone":null,"confidence":0.9,"sufficient":true,"summary":"Hallucinated"}'
        ),
    )

    candidates = [
        PhoneCandidate(raw_number="030 123456", e164_number="+4930123456", source="web", confidence=0.8)
    ]
    result = evaluator.evaluate(
        ContactInput(first_name="Max", last_name="Mustermann", company="Test GmbH"),
        candidates,
        "direct_or_mobile",
    )
    assert result["direct_phone"] is None
    assert result["confidence"] == 0.9


def test_accepts_normalized_variant_of_known_candidate(monkeypatch) -> None:
    evaluator = OpenRouterEvaluator({"openrouter": {
        "api_key_env": "FAKE_KEY",
        "evaluation_model": "test-model",
        "base_url": "https://example.com/v1",
        "timeout_seconds": 10,
    }})
    monkeypatch.setenv("FAKE_KEY", "test-key")
    monkeypatch.setattr(
        "requests.post",
        lambda *args, **kwargs: FakeResponse(
            '{"direct_phone":"030 123456","mobile_phone":null,"company_phone":null,"confidence":0.95,"sufficient":true,"summary":"Matched"}'
        ),
    )

    candidates = [
        PhoneCandidate(raw_number="030 123456", e164_number="+4930123456", source="web", confidence=0.8)
    ]
    result = evaluator.evaluate(
        ContactInput(first_name="Max", last_name="Mustermann", company="Test GmbH", country="DE"),
        candidates,
        "direct_or_mobile",
    )
    assert result["direct_phone"] == "+4930123456"
