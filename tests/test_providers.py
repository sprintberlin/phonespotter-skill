from phonespotter.models import ContactInput
from phonespotter.providers import OpenRouterWebSearchProvider


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": '{"candidates":[]}'}}]}


def test_web_search_forces_a_search_tool_call(monkeypatch):
    monkeypatch.setenv("FAKE_OPENROUTER", "key")
    captured = {}

    def request(*args, **kwargs):
        captured.update(kwargs["json"])
        return FakeResponse()

    monkeypatch.setattr("requests.post", request)
    provider = OpenRouterWebSearchProvider({"openrouter": {
        "api_key_env": "FAKE_OPENROUTER",
        "web_search_model": "google/gemini-3.7-flash",
        "base_url": "https://example.com/v1",
        "timeout_seconds": 10,
        "web_search": {"engine": "native", "max_uses": 2, "max_results": 5},
    }})
    assert provider.lookup(ContactInput(company="Example GmbH", country="DE")) == []
    assert captured["tool_choice"] == "required"
    assert captured["tools"][0]["type"] == "openrouter:web_search"
