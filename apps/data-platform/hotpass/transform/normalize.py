"""Rich text and identifier normalisation helpers."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from types import ModuleType
from typing import cast
from urllib.parse import urlparse, urlunparse

import phonenumbers

from .._compat_nameparser import HumanName

StdnumCleanFunc = Callable[[str, str], str]


def _fallback_clean(number: str, deletechars: str = " ") -> str:
    """Basic character stripping fallback when python-stdnum is unavailable."""

    result = number
    for character in deletechars:
        result = result.replace(character, "")
    return result


_numdb_module: ModuleType | None
try:  # pragma: no cover - optional dependency
    _numdb_module = import_module("stdnum.numdb")
except ImportError:  # pragma: no cover - fallback when stdnum is absent
    _numdb_module = None


_stdnum_clean: StdnumCleanFunc
try:  # pragma: no cover - optional dependency
    _stdnum_util = import_module("stdnum.util")
except ImportError:  # pragma: no cover - fallback when stdnum is absent
    _stdnum_clean = _fallback_clean
else:
    _stdnum_clean = cast(StdnumCleanFunc, _stdnum_util.clean)


_invalid_format: type[Exception]
try:  # pragma: no cover - optional dependency
    _stdnum_exceptions = import_module("stdnum.exceptions")
except ImportError:  # pragma: no cover - fallback when stdnum is absent

    class _StdnumInvalidFormat(Exception):
        """Fallback exception mirroring python-stdnum's InvalidFormat."""

    _invalid_format = _StdnumInvalidFormat
else:
    _invalid_format = cast(type[Exception], _stdnum_exceptions.InvalidFormat)


numdb: ModuleType | None = _numdb_module
InvalidFormat = _invalid_format
stdnum_clean: StdnumCleanFunc = _stdnum_clean

try:  # pragma: no cover - optional modules for locale-specific numbers
    from stdnum.za import postcode as za_postcode
    from stdnum.za import vat as za_vat
except ImportError:  # pragma: no cover - fallback if optional modules missing
    za_postcode = None
    za_vat = None


@dataclass(frozen=True)
class NormalizedName:
    """Structured view of a human name parsed via :mod:`nameparser`."""

    full: str
    given: str | None = None
    middle: str | None = None
    family: str | None = None
    title: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        """Serialise the name into a mapping for downstream consumers."""
        return {
            "full": self.full,
            "given": self.given,
            "middle": self.middle,
            "family": self.family,
            "title": self.title,
        }


def clean_text(value: object | None, *, max_length: int = 10000) -> str | None:
    """Normalise arbitrary values into trimmed unicode strings."""
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN guard
        return None
    if isinstance(value, str):
        text = value.strip()
    else:
        text = str(value).strip()
    if not text:
        return None
    if len(text) > max_length:
        text = text[:max_length]
    text = unicodedata.normalize("NFKC", text)
    return text or None


def parse_person_name(value: object | None) -> NormalizedName | None:
    """Return a parsed representation of a person's name."""
    text = clean_text(value)
    if not text:
        return None
    name = HumanName(text)
    return NormalizedName(
        full=name.full_name,
        given=name.first or None,
        middle=name.middle or None,
        family=name.last or None,
        title=name.title or None,
    )


def normalize_email(value: object | None) -> str | None:
    """Lower-case and validate email addresses."""
    text = clean_text(value)
    if not text:
        return None
    if "@" not in text:
        return None
    local, _, domain = text.partition("@")
    if not local or not domain:
        return None
    return f"{local.lower()}@{domain.lower()}"


def normalize_phone(value: object | None, *, country_code: str = "ZA") -> str | None:
    """Return an E.164 formatted phone number when valid."""
    text = clean_text(value)
    if not text:
        return None
    digits = re.sub(r"[^0-9+]+", "", text)
    if not digits:
        return None
    try:
        parsed = phonenumbers.parse(digits, country_code)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def normalize_website(value: object | None) -> str | None:
    """Ensure website URLs are https-prefixed and normalised."""
    text = clean_text(value)
    if not text:
        return None
    if not re.match(r"https?://", text, flags=re.I):
        text = f"https://{text}"
    parsed = urlparse(text)
    netloc = parsed.netloc or parsed.path
    path = parsed.path if parsed.netloc else ""
    netloc = netloc.lower().lstrip()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    clean_path = path.rstrip("/")
    rebuilt = urlunparse(("https", netloc, clean_path, "", "", ""))
    return rebuilt.rstrip("/")


def normalize_vat_number(value: object | None) -> str | None:
    """Validate and canonicalise a South African VAT number when available."""
    text = clean_text(value)
    if not text:
        return None
    cleaned = stdnum_clean(text, " -")
    if za_vat is None:
        return cleaned
    try:
        validated = za_vat.compact(za_vat.validate(cleaned))
    except InvalidFormat:
        return None
    return validated  # type: ignore[no-any-return]


def normalize_postal_code(value: object | None) -> str | None:
    """Return a canonical postal code for supported regions."""
    text = clean_text(value)
    if not text:
        return None
    cleaned = stdnum_clean(text, " -")
    if za_postcode is not None:
        try:
            return za_postcode.validate(cleaned)  # type: ignore[no-any-return]
        except InvalidFormat:
            return None
    if cleaned.isdigit() and 3 <= len(cleaned) <= 6:
        return cleaned
    return None


def normalise_identifier(value: object | None) -> str | None:
    """Canonicalise generic identifiers by stripping punctuation and upper-casing."""
    text = clean_text(value)
    if not text:
        return None
    cleaned = stdnum_clean(text, " -/").upper()
    # fall back to python-stdnum database for known patterns when available
    if numdb is not None and numdb.get(cleaned):  # pragma: no cover - optional datasets
        return cleaned
    return cleaned or None
