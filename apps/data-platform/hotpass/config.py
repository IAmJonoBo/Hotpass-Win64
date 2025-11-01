"""Configuration management for industry profiles and pipeline settings."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from .config_schema import ProfileConfig

try:
    import yaml
except ImportError:  # pragma: no cover - fallback when PyYAML missing at runtime
    yaml = cast("Any", None)


class IndustryProfile(ProfileConfig):
    """Backward compatible alias for profile definitions."""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> IndustryProfile:
        try:
            return cls.model_validate(payload)
        except ValidationError as exc:  # pragma: no cover - exercised via tests
            raise ValueError(str(exc)) from exc

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def load_industry_profile(profile_name: str, config_dir: Path | None = None) -> IndustryProfile:
    """Load an industry profile from configuration directory."""
    if config_dir is None:
        config_dir = Path(__file__).parent / "profiles"

    profile_path = config_dir / f"{profile_name}.yaml"

    # Try YAML first
    if profile_path.exists():
        with open(profile_path) as f:
            data = yaml.safe_load(f)
            return IndustryProfile.from_dict(data)

    # Try JSON
    json_path = config_dir / f"{profile_name}.json"
    if json_path.exists():
        with open(json_path) as f:
            data = json.load(f)
            return IndustryProfile.from_dict(data)

    # Return default profile
    return get_default_profile(profile_name)


def get_default_profile(profile_name: str = "generic") -> IndustryProfile:
    """Get a built-in default profile."""
    if profile_name == "aviation":
        return IndustryProfile(
            name="aviation",
            display_name="Aviation & Flight Training",
            default_country_code="ZA",
            organization_term="flight_school",
            organization_type_term="school_type",
            organization_category_term="training_category",
            source_priorities={
                "SACAA Cleaned": 3,
                "Reachout Database": 2,
                "Contact Database": 1,
            },
            column_synonyms={
                "organization_name": [
                    "school_name",
                    "institution_name",
                    "provider_name",
                    "company_name",
                    "account_name",
                    "organisation_name",
                ],
                "contact_email": [
                    "email",
                    "email_address",
                    "primary_email",
                    "contact_email_address",
                    "e-mail",
                    "e_mail",
                    "mail",
                ],
                "contact_phone": [
                    "phone",
                    "telephone",
                    "phone_number",
                    "contact_number",
                    "tel",
                    "mobile",
                    "cell",
                    "cellphone",
                ],
                "website": [
                    "url",
                    "website_url",
                    "web_address",
                    "homepage",
                    "site",
                    "web",
                ],
                "province": ["state", "region", "area", "territory"],
            },
            required_fields=["organization_name"],
            optional_fields=[
                "contact_primary_email",
                "contact_primary_phone",
                "website",
                "province",
                "address_primary",
            ],
        )

    # Generic profile for any industry
    return IndustryProfile.from_dict(
        {
            "name": "generic",
            "display_name": "Generic Business",
            "default_country_code": "ZA",
            "column_synonyms": {
                "organization_name": [
                    "name",
                    "company",
                    "business",
                    "entity",
                    "organization",
                    "company_name",
                    "business_name",
                    "organisation",
                ],
                "contact_email": [
                    "email",
                    "email_address",
                    "e-mail",
                    "e_mail",
                    "mail",
                    "contact_email",
                    "primary_email",
                ],
                "contact_phone": [
                    "phone",
                    "telephone",
                    "phone_number",
                    "contact_number",
                    "tel",
                    "mobile",
                    "cell",
                    "cellphone",
                ],
                "website": ["url", "website", "web", "homepage", "site", "web_address"],
                "address": [
                    "address",
                    "location",
                    "street_address",
                    "mailing_address",
                    "physical_address",
                ],
            },
            "required_fields": ["organization_name"],
            "optional_fields": [
                "contact_primary_email",
                "contact_primary_phone",
                "website",
                "province",
                "address_primary",
            ],
        }
    )


def save_industry_profile(profile: IndustryProfile, config_dir: Path) -> None:
    """Save an industry profile to YAML."""
    config_dir.mkdir(parents=True, exist_ok=True)
    profile_path = config_dir / f"{profile.name}.yaml"

    with open(profile_path, "w") as f:
        yaml.dump(profile.to_dict(), f, default_flow_style=False, sort_keys=False)
