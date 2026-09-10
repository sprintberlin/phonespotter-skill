"""Configuration loading for PhoneSpotter."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG: dict[str, Any] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "web_search_model": "~google/gemini-flash-latest",
        "evaluation_model": "~google/gemini-flash-latest",
        "timeout_seconds": 45,
        "web_search": {
            "engine": "native",
            "max_uses": 2,
            "max_results": 5,
            "user_location": {"type": "approximate", "country": "DE"},
        },
    },
    "lusha": {
        "enabled": True,
        "api_key_env": "LUSHA_API_KEY",
        "base_url": "https://api.lusha.com/v2/person",
        "timeout_seconds": 30,
        "require_person_identity": True,
    },
    "orchestration": {
        "provider_order": ["openrouter_web_search", "lusha"],
        "target": "direct_or_mobile",
        "minimum_confidence": 0.70,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load YAML config, merged over safe defaults."""
    config = deepcopy(DEFAULT_CONFIG)
    if path is None:
        return config

    config_path = Path(path).expanduser()
    with config_path.open("r", encoding="utf-8") as handle:
        user_config = yaml.safe_load(handle) or {}
    if not isinstance(user_config, dict):
        raise ValueError("Configuration root must be a YAML mapping.")
    return _deep_merge(config, user_config)
