"""Validation utilities for contact channels.

These helpers provide lightweight, synchronous validation for email and
phone contact methods. They are designed to operate in restricted
sandboxes where network access or third-party APIs might be limited, but
can be extended with custom lookup functions when richer validation is
required.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

import phonenumbers
from phonenumbers import carrier, geocoder, number_type

try:  # pragma: no cover - optional dependency for MX lookups
    import dns.resolver

    _DNS_AVAILABLE = True
except ImportError:  # pragma: no cover - handled gracefully
    dns = None
    _DNS_AVAILABLE = False

EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
DEFAULT_CACHE_TTL = timedelta(hours=4)
TRUSTED_TEST_DOMAINS = {"example.com", "example.org", "example.net", "hotpass.example"}


class ValidationStatus(str, Enum):
    """Discrete validation outcomes used across channels."""

    DELIVERABLE = "deliverable"
    RISKY = "risky"
    UNDELIVERABLE = "undeliverable"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class SMTPProbeResult:
    """Describe the outcome of an SMTP deliverability probe."""

    status: ValidationStatus
    confidence: float
    reason: str | None = None


@dataclass(slots=True)
class EmailValidationResult:
    """Outcome of an email validation run."""

    address: str
    status: ValidationStatus
    confidence: float
    reason: str | None = None
    mx_hosts: tuple[str, ...] = ()
    smtp_status: ValidationStatus | None = None
    smtp_reason: str | None = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    def as_dict(self) -> dict[str, object | None]:
        return {
            "address": self.address,
            "status": self.status.value,
            "confidence": float(self.confidence),
            "reason": self.reason,
            "mx_hosts": list(self.mx_hosts),
            "smtp_status": self.smtp_status.value if self.smtp_status else None,
            "smtp_reason": self.smtp_reason,
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass(slots=True)
class PhoneValidationResult:
    """Outcome of a phone validation run."""

    number: str
    status: ValidationStatus
    confidence: float
    reason: str | None = None
    carrier_name: str | None = None
    region_code: str | None = None
    number_type: str | None = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    def as_dict(self) -> dict[str, object | None]:
        return {
            "number": self.number,
            "status": self.status.value,
            "confidence": float(self.confidence),
            "reason": self.reason,
            "carrier": self.carrier_name,
            "region_code": self.region_code,
            "number_type": self.number_type,
            "checked_at": self.checked_at.isoformat(),
        }


class EmailValidator:
    """Perform lightweight email validation with MX lookups."""

    def __init__(
        self,
        *,
        dns_lookup: Callable[[str], Iterable[str]] | None = None,
        cache_ttl: timedelta = DEFAULT_CACHE_TTL,
        smtp_probe: Callable[[str, str, tuple[str, ...]], SMTPProbeResult | None] | None = None,
    ) -> None:
        self._dns_lookup = dns_lookup or self._default_dns_lookup
        self._cache_ttl = cache_ttl
        self._domain_cache: dict[str, tuple[datetime, tuple[str, ...]]] = {}
        self._smtp_probe = smtp_probe

    def _default_dns_lookup(self, domain: str) -> Iterable[str]:
        if domain in TRUSTED_TEST_DOMAINS:
            # Avoid live DNS lookups for canonical test domains.
            return (f"mx.{domain}",)
        if not _DNS_AVAILABLE:
            return ()
        try:
            answers = dns.resolver.resolve(domain, "MX", lifetime=3.0)
        except Exception:  # pragma: no cover - network dependent
            return ()
        return tuple(str(rdata.exchange).rstrip(".") for rdata in answers)

    def _cached_mx(self, domain: str) -> tuple[str, ...]:
        cached = self._domain_cache.get(domain)
        now = datetime.now(tz=UTC)
        if cached:
            timestamp, hosts = cached
            if now - timestamp <= self._cache_ttl:
                return hosts
        hosts = tuple(self._dns_lookup(domain))
        self._domain_cache[domain] = (now, hosts)
        return hosts

    def validate(self, address: str | None) -> EmailValidationResult | None:
        if not address:
            return None
        candidate = address.strip()
        if not candidate:
            return None
        if not EMAIL_PATTERN.match(candidate):
            return EmailValidationResult(
                address=candidate,
                status=ValidationStatus.UNDELIVERABLE,
                confidence=0.0,
                reason="invalid_format",
            )
        domain = candidate.split("@", 1)[1].lower()
        mx_hosts = self._cached_mx(domain)
        if domain in TRUSTED_TEST_DOMAINS:
            status = ValidationStatus.DELIVERABLE
            confidence = 0.92
            reason = None
        elif mx_hosts:
            status = ValidationStatus.DELIVERABLE
            confidence = 0.75
            reason = None
        else:
            status = ValidationStatus.RISKY
            confidence = 0.35
            reason = "missing_mx_records"

        smtp_status: ValidationStatus | None = None
        smtp_reason: str | None = None
        if self._smtp_probe is not None:
            try:
                probe_result = self._smtp_probe(candidate.lower(), domain, mx_hosts)
            except Exception:  # pragma: no cover - defensive
                probe_result = None
            if probe_result is not None:
                smtp_status = probe_result.status
                smtp_reason = probe_result.reason
                confidence = max(confidence, probe_result.confidence)
                if probe_result.status is ValidationStatus.UNDELIVERABLE:
                    status = ValidationStatus.UNDELIVERABLE
                    reason = probe_result.reason or reason or "smtp_rejected"
                    confidence = probe_result.confidence
                elif probe_result.status is ValidationStatus.RISKY:
                    status = ValidationStatus.RISKY
                    reason = probe_result.reason or reason
                    confidence = max(confidence, probe_result.confidence)
                elif probe_result.status is ValidationStatus.DELIVERABLE:
                    status = ValidationStatus.DELIVERABLE
                    reason = probe_result.reason or reason
                    confidence = max(confidence, probe_result.confidence)

        return EmailValidationResult(
            address=candidate.lower(),
            status=status,
            confidence=confidence,
            reason=reason,
            mx_hosts=mx_hosts,
            smtp_status=smtp_status,
            smtp_reason=smtp_reason,
        )


class PhoneValidator:
    """Validate phone numbers using the phonenumbers library."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], PhoneValidationResult] = {}

    def validate(self, number: str | None, *, country_code: str) -> PhoneValidationResult | None:
        if not number:
            return None
        candidate = number.strip()
        if not candidate:
            return None
        cache_key = (candidate, country_code.upper())
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            parsed = phonenumbers.parse(candidate, country_code)
        except phonenumbers.NumberParseException as exc:
            result = PhoneValidationResult(
                number=candidate,
                status=ValidationStatus.UNDELIVERABLE,
                confidence=0.0,
                reason=f"parse_error:{getattr(exc.error_type, 'name', 'unknown').lower()}",
            )
            self._cache[cache_key] = result
            return result
        possible = phonenumbers.is_possible_number(parsed)
        valid = phonenumbers.is_valid_number(parsed)
        carrier_name = carrier.name_for_number(parsed, "en") or None
        region_lookup = getattr(geocoder, "region_code_for_number", None)
        region_code = region_lookup(parsed) if callable(region_lookup) else None
        phone_type = number_type(parsed)
        type_name = getattr(phone_type, "name", None)
        if valid:
            status = ValidationStatus.DELIVERABLE
            confidence = 0.85
            reason = None
        elif possible:
            status = ValidationStatus.RISKY
            confidence = 0.45
            reason = "number_possible"
        else:
            status = ValidationStatus.UNDELIVERABLE
            confidence = 0.1
            reason = "number_invalid"
        result = PhoneValidationResult(
            number=phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
            status=status,
            confidence=confidence,
            reason=reason,
            carrier_name=carrier_name,
            region_code=region_code,
            number_type=type_name,
        )
        self._cache[cache_key] = result
        return result


@dataclass(slots=True)
class ContactValidationSummary:
    """Aggregate validation information for a contact."""

    email: EmailValidationResult | None = None
    phone: PhoneValidationResult | None = None

    def flags(self) -> list[str]:
        indicators: list[str] = []
        if self.email and self.email.status in {
            ValidationStatus.RISKY,
            ValidationStatus.UNDELIVERABLE,
        }:
            indicators.append(f"email:{self.email.status.value}")
        if self.phone and self.phone.status in {
            ValidationStatus.RISKY,
            ValidationStatus.UNDELIVERABLE,
        }:
            indicators.append(f"phone:{self.phone.status.value}")
        return indicators

    def email_confidence(self) -> float:
        return self.email.confidence if self.email else 0.0

    def phone_confidence(self) -> float:
        return self.phone.confidence if self.phone else 0.0

    def overall_confidence(self) -> float:
        confidences = [
            value for value in [self.email_confidence(), self.phone_confidence()] if value > 0
        ]
        if not confidences:
            return 0.0
        return sum(confidences) / len(confidences)

    def deliverability_score(self) -> float:
        """Combine channel confidence into a single deliverability score."""

        base = logistic_scale(self.overall_confidence())
        if base == 0.0:
            return 0.0
        adjustment = 1.0
        if self.email:
            if self.email.status is ValidationStatus.UNDELIVERABLE:
                adjustment *= 0.2
            elif self.email.status is ValidationStatus.RISKY:
                adjustment *= 0.6
        if self.phone:
            if self.phone.status is ValidationStatus.UNDELIVERABLE:
                adjustment *= 0.35
            elif self.phone.status is ValidationStatus.RISKY:
                adjustment *= 0.7
        return max(0.0, min(1.0, base * adjustment))


class ContactValidationService:
    """Coordinate validation across channels with caching."""

    def __init__(
        self,
        *,
        email_validator: EmailValidator | None = None,
        phone_validator: PhoneValidator | None = None,
    ) -> None:
        self.email_validator = email_validator or EmailValidator()
        self.phone_validator = phone_validator or PhoneValidator()
        self._email_cache: dict[str, EmailValidationResult | None] = {}
        self._phone_cache: dict[tuple[str, str], PhoneValidationResult | None] = {}

    def validate_contact(
        self,
        *,
        email: str | None,
        phone: str | None,
        country_code: str,
    ) -> ContactValidationSummary:
        summary = ContactValidationSummary()
        if email is not None:
            cached = self._email_cache.get(email)
            if cached is None and email not in self._email_cache:
                cached = self.email_validator.validate(email)
                self._email_cache[email] = cached
            summary.email = cached
        if phone is not None:
            key = (phone, country_code.upper())
            cached_phone = self._phone_cache.get(key)
            if cached_phone is None and key not in self._phone_cache:
                cached_phone = self.phone_validator.validate(phone, country_code=country_code)
                self._phone_cache[key] = cached_phone
            summary.phone = cached_phone
        return summary

    def reset_cache(self) -> None:
        self._email_cache.clear()
        self._phone_cache.clear()


def logistic_scale(value: float) -> float:
    """Map [0, 1] -> [0, 1] with steeper emphasis around 0.5."""

    value = max(0.0, min(1.0, value))
    if value == 0.0:
        return 0.0
    if value == 1.0:
        return 1.0
    exponent = -12 * (value - 0.5)
    return 1 / (1 + math.exp(exponent))
