"""Provider adapters for OpenRouter grounded web search and Lusha."""

from __future__ import annotations

import json
import os
from typing import Any

import requests

from .models import ContactInput, PhoneCandidate


class ProviderError(RuntimeError):
    """Expected provider failure that should not leak secrets."""


def _clean_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "".join(
            item.get("text", "") if isinstance(item, dict) else str(item) for item in content
        ).strip()
    return str(content or "").strip()


def _extract_json_object(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`").replace("json\n", "", 1).strip()
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ProviderError("OpenRouter returned no usable JSON object.")
    try:
        parsed = json.loads(content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ProviderError("OpenRouter response JSON could not be parsed.") from exc
    if not isinstance(parsed, dict):
        raise ProviderError("OpenRouter response is not a JSON object.")
    return parsed


def _contact_context(contact: ContactInput) -> str:
    fields = {
        "person": contact.full_name or None,
        "company": contact.company,
        "email": contact.email,
        "linkedin_url": contact.linkedin_url,
        "designation": contact.designation,
        "country": contact.country,
    }
    return "\n".join(f"{key}: {value}" for key, value in fields.items() if value)


class OpenRouterWebSearchProvider:
    name = "openrouter_web_search"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.settings = config["openrouter"]

    @property
    def api_key(self) -> str:
        return os.getenv(self.settings["api_key_env"], "").strip()

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def lookup(self, contact: ContactInput) -> list[PhoneCandidate]:
        if not self.available:
            raise ProviderError("OpenRouter is not configured.")

        prompt = f"""Research public business telephone numbers for this contact using web search.

{_contact_context(contact)}

Goal: Find a direct business number or mobile number for the named person. A verified company central number is useful as a fallback, but it is not a direct number.

Use official company imprint/contact/team pages first. Never invent a number. A number must only be returned when it is publicly supported by the search results and clearly belongs to the named person or company.

Respond only with this JSON object:
{{
  "candidates": [
    {{"number": "raw phone number", "type": "direct|mobile|company_hq", "confidence": 0.0, "notes": "short public source evidence"}}
  ]
}}
If nothing reliable is found, return {{"candidates": []}}."""
        search = self.settings["web_search"]
        tool_parameters = {
            "engine": search.get("engine", "native"),
            "max_uses": search.get("max_uses", 2),
            "max_results": search.get("max_results", 5),
        }
        if search.get("user_location"):
            tool_parameters["user_location"] = search["user_location"]

        payload = {
            "model": self.settings["web_search_model"],
            "messages": [
                {"role": "system", "content": "You are a precise B2B contact-data researcher. Use the available web search tool before answering. Never invent data."},
                {"role": "user", "content": prompt},
            ],
            "tools": [{"type": "openrouter:web_search", "parameters": tool_parameters}],
            # OpenRouter server tools are handled internally. Do not force `required`:
            # some Gemini routes return finish_reason=error after a forced search.
            "temperature": 0,
            "max_tokens": 1500,
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
        except requests.RequestException as exc:
            raise ProviderError("OpenRouter web search request failed.") from exc
        except ValueError as exc:
            raise ProviderError("OpenRouter web search returned invalid JSON.") from exc

        try:
            content = _clean_content(body["choices"][0]["message"]["content"])
            parsed = _extract_json_object(content)
        except (KeyError, IndexError, ProviderError) as exc:
            raise ProviderError("OpenRouter web search returned no usable result.") from exc

        candidates: list[PhoneCandidate] = []
        for item in parsed.get("candidates", []):
            if not isinstance(item, dict) or not item.get("number"):
                continue
            phone_type = str(item.get("type", "unknown")).lower()
            if phone_type not in {"direct", "mobile", "company_hq"}:
                phone_type = "unknown"
            try:
                confidence = max(0.0, min(1.0, float(item.get("confidence", 0))))
            except (ValueError, TypeError):
                confidence = 0.0
            candidates.append(
                PhoneCandidate(
                    raw_number=str(item["number"]),
                    phone_type=phone_type,
                    source=self.name,
                    confidence=confidence,
                    notes=str(item.get("notes", "")).strip() or None,
                )
            )
        return candidates


class LushaProvider:
    name = "lusha"

    def __init__(self, config: dict[str, Any]) -> None:
        self.settings = config["lusha"]

    @property
    def api_key(self) -> str:
        return os.getenv(self.settings["api_key_env"], "").strip()

    @property
    def available(self) -> bool:
        return bool(self.settings.get("enabled", True) and self.api_key)

    def can_lookup(self, contact: ContactInput) -> bool:
        if not self.available:
            return False
        if not self.settings.get("require_person_identity", True):
            return True
        return bool(contact.first_name and contact.last_name and (contact.company or contact.email or contact.linkedin_url))

    def lookup(self, contact: ContactInput) -> list[PhoneCandidate]:
        if not self.can_lookup(contact):
            raise ProviderError("Lusha is unavailable or has insufficient identity data.")
        params: dict[str, str] = {}
        if contact.first_name:
            params["firstName"] = contact.first_name
        if contact.last_name:
            params["lastName"] = contact.last_name
        if contact.email and "@" in contact.email:
            params["email"] = contact.email
            domain = contact.email.rsplit("@", 1)[1].lower()
            # Freemail domains are not a meaningful company signal. Preserve the supplied company.
            if domain not in {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com", "icloud.com", "gmx.de", "web.de"}:
                params["companyDomain"] = domain
        if contact.company:
            params["companyName"] = contact.company
        if contact.linkedin_url:
            params["linkedinUrl"] = contact.linkedin_url

        try:
            response = requests.get(
                self.settings["base_url"],
                headers={"api_key": self.api_key},
                params=params,
                timeout=self.settings["timeout_seconds"],
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise ProviderError("Lusha lookup request failed.") from exc
        except ValueError as exc:
            raise ProviderError("Lusha returned invalid JSON.") from exc

        contact_node = payload.get("contact") if isinstance(payload, dict) else None
        if not isinstance(contact_node, dict) or contact_node.get("isCreditCharged") is False:
            return []
        data = contact_node.get("data")
        if not isinstance(data, dict):
            return []

        candidates: list[PhoneCandidate] = []
        for phone in data.get("phoneNumbers", []) or []:
            if not isinstance(phone, dict) or not phone.get("number"):
                continue
            kind = str(phone.get("phoneType", "unknown")).lower()
            if kind == "mobile":
                phone_type = "mobile"
            elif kind in {"direct", "work", "office"}:
                phone_type = "direct"
            else:
                phone_type = "unknown"
            candidates.append(
                PhoneCandidate(
                    raw_number=str(phone["number"]),
                    phone_type=phone_type,
                    source=self.name,
                    confidence=0.85 if phone_type in {"direct", "mobile"} else 0.60,
                    notes=f"Lusha type: {kind}",
                )
            )
        return candidates
