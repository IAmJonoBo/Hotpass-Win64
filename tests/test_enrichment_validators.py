"""Validation helper coverage for enrichment validators."""

from __future__ import annotations

from datetime import timedelta

from hotpass.enrichment.validators import (
    ContactValidationService,
    EmailValidator,
    PhoneValidator,
    ValidationStatus,
    logistic_scale,
)

from tests.helpers.assertions import expect


def test_email_validator_handles_trusted_domains() -> None:
    validator = EmailValidator()
    result = validator.validate("user@example.com")
    assert result is not None, "Validator should return a result for valid email"
    expect(
        result.status is ValidationStatus.DELIVERABLE,
        "Trusted domain should be deliverable",
    )
    expect(bool(result.mx_hosts), "Trusted domains should populate MX hosts")


def test_email_validator_caches_dns_responses() -> None:
    calls: list[str] = []

    def fake_lookup(domain: str) -> tuple[str, ...]:
        calls.append(domain)
        return ("mx.test",)

    validator = EmailValidator(dns_lookup=fake_lookup, cache_ttl=timedelta(hours=1))
    first = validator.validate("user@cached.test")
    second = validator.validate("user@cached.test")
    assert first is not None and second is not None, "Validation should produce results"
    expect(len(calls) == 1, "Subsequent validations should reuse cached MX lookup")


def test_phone_validator_normalises_and_scores_numbers() -> None:
    validator = PhoneValidator()
    result = validator.validate("021 123 4567", country_code="ZA")
    assert result is not None, "Phone validator should return a result"
    expect(
        result.status in {ValidationStatus.DELIVERABLE, ValidationStatus.RISKY},
        "Number should be classified",
    )
    if result.status is ValidationStatus.DELIVERABLE:
        expect(result.confidence >= 0.85, "Deliverable numbers should have high confidence")


def test_contact_validation_service_caches_per_channel() -> None:
    service = ContactValidationService()
    summary_first = service.validate_contact(
        email="agent@example.com",
        phone="021 123 4567",
        country_code="ZA",
    )
    summary_second = service.validate_contact(
        email="agent@example.com",
        phone="021 123 4567",
        country_code="ZA",
    )
    expect(
        summary_first.email is summary_second.email,
        "Email validations should reuse cached results",
    )
    expect(
        summary_first.phone is summary_second.phone,
        "Phone validations should reuse cached results",
    )
    expect(
        isinstance(summary_first.flags(), list),
        "Summary should expose derived indicators for downstream logging",
    )


def test_logistic_scale_monotonicity() -> None:
    expect(logistic_scale(0.0) == 0.0, "Lower bound should clamp to zero")
    expect(logistic_scale(1.0) == 1.0, "Upper bound should clamp to one")
    mid = logistic_scale(0.5)
    expect(abs(mid - 0.5) < 0.05, "Midpoint should remain near 0.5 after scaling")
    expect(
        logistic_scale(0.7) > logistic_scale(0.3),
        "Function should be monotonic increasing",
    )
