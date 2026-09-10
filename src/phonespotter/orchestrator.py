"""Ordered, cost-conscious provider orchestration."""

from __future__ import annotations

from typing import Any

from .evaluator import OpenRouterEvaluator
from .models import ContactInput, EnrichmentResult, PhoneCandidate, ProviderAttempt
from .normalizer import normalize_and_dedupe
from .providers import LushaProvider, OpenRouterWebSearchProvider, ProviderError


class PhoneSpotter:
    """Run enabled providers in order and stop on a verified direct/mobile number."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.providers = {
            "openrouter_web_search": OpenRouterWebSearchProvider(config),
            "lusha": LushaProvider(config),
        }
        self.evaluator = OpenRouterEvaluator(config)

    def lookup(self, contact: ContactInput) -> EnrichmentResult:
        if not contact.full_name and not contact.company:
            return EnrichmentResult(
                status="error",
                error="At least a person name or company is required.",
            )
        if not self.evaluator.available:
            return EnrichmentResult(
                status="error",
                error="OpenRouter is not configured. Set the configured API key environment variable.",
            )

        orchestration = self.config["orchestration"]
        provider_order = orchestration["provider_order"]
        minimum_confidence = float(orchestration["minimum_confidence"])
        target = orchestration["target"]
        all_candidates: list[PhoneCandidate] = []
        providers_checked: list[str] = []
        provider_attempts: list[ProviderAttempt] = []
        latest_evaluation: dict[str, Any] | None = None

        for provider_name in provider_order:
            provider = self.providers.get(provider_name)
            if provider is None:
                provider_attempts.append(
                    ProviderAttempt(provider=provider_name, status="skipped", detail="Provider is not implemented.")
                )
                continue
            if provider_name == "lusha" and not provider.can_lookup(contact):
                provider_attempts.append(
                    ProviderAttempt(
                        provider=provider_name,
                        status="skipped",
                        detail="Provider is unavailable or the contact lacks sufficient identity data.",
                    )
                )
                continue
            if provider_name == "openrouter_web_search" and not provider.available:
                provider_attempts.append(
                    ProviderAttempt(provider=provider_name, status="skipped", detail="Provider is not configured.")
                )
                continue

            providers_checked.append(provider_name)
            try:
                raw_candidates = provider.lookup(contact)
            except ProviderError as exc:
                # Continue with a later provider. Error details must not reveal API internals or secrets.
                provider_attempts.append(ProviderAttempt(provider=provider_name, status="failed", detail=str(exc)))
                continue

            normalized = normalize_and_dedupe(raw_candidates, contact.country or "DE")
            if not normalized:
                # Empty provider result: no evaluation cost; proceed immediately.
                provider_attempts.append(
                    ProviderAttempt(provider=provider_name, status="no_candidates", detail="No valid telephone candidate returned.")
                )
                continue

            known_by_number = {
                candidate.e164_number: candidate
                for candidate in all_candidates
                if candidate.e164_number
            }
            for candidate in normalized:
                if not candidate.e164_number:
                    continue
                existing = known_by_number.get(candidate.e164_number)
                if existing is None:
                    all_candidates.append(candidate)
                    known_by_number[candidate.e164_number] = candidate
                elif candidate.confidence > existing.confidence or (
                    candidate.phone_type in {"direct", "mobile"} and existing.phone_type == "company_hq"
                ):
                    all_candidates[all_candidates.index(existing)] = candidate
                    known_by_number[candidate.e164_number] = candidate

            # Every non-empty provider result is evaluated. A later provider may corroborate
            # or improve the classification of a number returned by an earlier one.
            try:
                evaluation = self.evaluator.evaluate(contact, all_candidates, target)
            except ProviderError as exc:
                # Valid candidates remain available for a later provider, but we cannot certify them.
                provider_attempts.append(
                    ProviderAttempt(provider=provider_name, status="failed", detail=f"Candidate evaluation failed: {exc}")
                )
                continue
            provider_attempts.append(
                ProviderAttempt(provider=provider_name, status="evaluated", detail=f"{len(normalized)} valid candidate(s) returned.")
            )
            latest_evaluation = evaluation

            has_personal = bool(evaluation.get("direct_phone") or evaluation.get("mobile_phone"))
            sufficient = bool(evaluation.get("sufficient"))
            if has_personal and sufficient and float(evaluation.get("confidence", 0.0)) >= minimum_confidence:
                return self._result_from_evaluation(
                    evaluation=evaluation,
                    candidates=all_candidates,
                    providers_checked=providers_checked,
                    provider_attempts=provider_attempts,
                    successful_provider=provider_name,
                    status="found",
                )

        if latest_evaluation:
            has_personal = bool(
                latest_evaluation.get("direct_phone") or latest_evaluation.get("mobile_phone")
            )
            status = "found" if has_personal else "partial" if latest_evaluation.get("company_phone") else "not_found"
            return self._result_from_evaluation(
                evaluation=latest_evaluation,
                candidates=all_candidates,
                providers_checked=providers_checked,
                provider_attempts=provider_attempts,
                successful_provider=self._source_for_best(
                    latest_evaluation,
                    all_candidates,
                    latest_evaluation.get("mobile_phone")
                    or latest_evaluation.get("direct_phone")
                    or latest_evaluation.get("company_phone"),
                ),
                status=status,
            )
        return EnrichmentResult(
            status="not_found",
            providers_checked=providers_checked,
            provider_attempts=provider_attempts,
            candidates=all_candidates,
            evaluation_summary="No provider returned a usable phone candidate.",
        )

    @staticmethod
    def _source_for_best(
        evaluation: dict[str, Any], candidates: list[PhoneCandidate], best_phone: str | None
    ) -> str | None:
        if not best_phone:
            return None
        for candidate in reversed(candidates):
            if candidate.e164_number == best_phone:
                return candidate.source
        return None

    @staticmethod
    def _result_from_evaluation(
        *,
        evaluation: dict[str, Any],
        candidates: list[PhoneCandidate],
        providers_checked: list[str],
        provider_attempts: list[ProviderAttempt],
        successful_provider: str | None,
        status: str,
    ) -> EnrichmentResult:
        direct_phone = evaluation.get("direct_phone")
        mobile_phone = evaluation.get("mobile_phone")
        company_phone = evaluation.get("company_phone")
        if mobile_phone:
            best_phone, best_phone_type = mobile_phone, "mobile"
        elif direct_phone:
            best_phone, best_phone_type = direct_phone, "direct"
        elif company_phone:
            best_phone, best_phone_type = company_phone, "company_hq"
        else:
            best_phone, best_phone_type = None, None
        return EnrichmentResult(
            status=status,
            direct_phone=direct_phone,
            mobile_phone=mobile_phone,
            company_phone=company_phone,
            best_phone=best_phone,
            best_phone_type=best_phone_type,
            confidence=float(evaluation.get("confidence", 0.0)),
            providers_checked=providers_checked,
            provider_attempts=provider_attempts,
            successful_provider=successful_provider,
            candidates=candidates,
            evaluation_summary=evaluation.get("summary"),
        )
