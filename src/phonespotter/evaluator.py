"""LLM-backed candidate assessment for PhoneSpotter."""

from __future__ import annotations

import json
import os
from typing import Any

import requests

from .models import ContactInput, PhoneCandidate
from .normalizer import normalize_phone
from .providers import ProviderError, _clean_content, _extract_json_object


class OpenRouterEvaluator:
    """Uses a configured OpenRouter model to assess, not invent, candidates."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.settings = config["openrouter"]

    @property
    def api_key(self) -> str:
        return os.getenv(self.settings["api_key_env"], "").strip()

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def evaluate(
        self, contact: ContactInput, candidates: list[PhoneCandidate], target: str
    ) -> dict[str, Any]:
        if not self.available:
            raise ProviderError("OpenRouter evaluator is not configured.")
        candidate_json = [
            {
                "number": candidate.e164_number,
                "source": candidate.source,
                "suggested_type": candidate.phone_type,
                "provider_confidence": candidate.confidence,
                "evidence": candidate.notes,
            }
            for candidate in candidates
            if candidate.e164_number
        ]
        if not candidate_json:
            return {
                "direct_phone": None,
                "mobile_phone": None,
                "company_phone": None,
                "confidence": 0.0,
                "sufficient": False,
                "summary": "No valid candidate could be evaluated.",
            }

        context = {
            "person": contact.full_name or None,
            "company": contact.company,
            "email": contact.email,
            "linkedin_url": contact.linkedin_url,
            "designation": contact.designation,
            "country": contact.country,
            "target": target,
        }
        prompt = f"""Assess phone lookup candidates for a B2B contact. You must never invent, alter, or add a telephone number. You may choose only exact values from the supplied candidate list.

Contact identity:
{json.dumps(context, ensure_ascii=False)}

Normalized candidates:
{json.dumps(candidate_json, ensure_ascii=False)}

Classification rules:
- direct_phone: a business desk number or direct dial that belongs to the named person.
- mobile_phone: a business mobile number that belongs to the named person.
- company_phone: a company switchboard or general central number.
- Reject a candidate if identity/evidence is weak or it does not plausibly belong to the named person or company.
- A company central number alone is not sufficient when target is direct_or_mobile.

Reply only as JSON with this exact schema:
{{
  "direct_phone": "E.164 candidate or null",
  "mobile_phone": "E.164 candidate or null",
  "company_phone": "E.164 candidate or null",
  "confidence": 0.0,
  "sufficient": true,
  "summary": "one short sentence"
}}"""
        payload = {
            "model": self.settings["evaluation_model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        try:
            response = requests.post(
                self.settings["base_url"].rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.settings["timeout_seconds"],
            )
            response.raise_for_status()
            body = response.json()
            content = _clean_content(body["choices"][0]["message"]["content"])
            parsed = _extract_json_object(content)
        except requests.RequestException as exc:
            raise ProviderError("OpenRouter evaluation request failed.") from exc
        except (KeyError, IndexError, ValueError, ProviderError) as exc:
            raise ProviderError("OpenRouter evaluator returned no usable result.") from exc

        known_numbers = {candidate["number"] for candidate in candidate_json}
        selected: dict[str, Any] = {}
        for field in ("direct_phone", "mobile_phone", "company_phone"):
            value = parsed.get(field)
            normalized = normalize_phone(value, contact.country or "DE") if isinstance(value, str) else None
            selected[field] = normalized if normalized in known_numbers else None
        try:
            confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
        except (ValueError, TypeError):
            confidence = 0.0
        selected["confidence"] = confidence
        selected["sufficient"] = bool(parsed.get("sufficient", False))
        selected["summary"] = str(parsed.get("summary", "")).strip() or None
        return selected
