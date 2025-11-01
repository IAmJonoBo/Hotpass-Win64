"""Canonical Party / Role / Alias data structures."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from enum import Enum
from typing import cast

from pydantic import BaseModel, ConfigDict, Field


def generate_uuid7() -> uuid.UUID:
    """Generate a sortable UUID using the UUIDv7 algorithm."""

    if hasattr(uuid, "uuid7"):
        maybe_generator = getattr(uuid, "uuid7", None)  # noqa: B009
        if callable(maybe_generator):
            generator = cast(Callable[[], uuid.UUID], maybe_generator)
            return generator()
    # uuid7 is available in Python 3.13 used by the project, but this guard keeps the
    # helper resilient when executed from earlier interpreters.
    return uuid.UUID(int=uuid.uuid1().int)


class PartyKind(str, Enum):
    """High-level category describing the type of party."""

    PERSON = "person"
    ORGANISATION = "organisation"
    LOCATION = "location"


class AliasType(str, Enum):
    """Different types of aliases supported for parties."""

    LEGAL = "legal"
    TRADING_AS = "trading_as"
    HISTORIC = "historic"
    SOCIAL = "social"
    MACHINE = "machine"


class ContactMethodType(str, Enum):
    """Supported contact modalities for parties."""

    EMAIL = "email"
    PHONE = "phone"
    WHATSAPP = "whatsapp"
    WEBSITE = "website"
    PHYSICAL_ADDRESS = "physical_address"


class ConfidenceBand(str, Enum):
    """Qualitative confidence band for alias/contact provenance."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DomainModel(BaseModel):
    """Base Pydantic model configuration shared across party models."""

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=False,
        use_attribute_docstrings=True,
    )


class Provenance(DomainModel):
    """Capture the origin of a record and supporting metadata."""

    source: str = Field(..., description="Human friendly name of the contributing dataset")
    record_id: str | None = Field(
        default=None,
        description="Source specific identifier for the contributing record",
    )
    captured_at: datetime | None = Field(
        default=None,
        description="Timestamp when the source record was captured or exported",
    )
    selection_priority: int = Field(
        default=0,
        ge=0,
        description="Relative priority of the source when resolving conflicts (higher wins)",
    )
    quality_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Normalised quality score attributed to the source observation",
    )


class ValidityWindow(DomainModel):
    """Validity interval for temporal facts."""

    start: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Timestamp from which the record is considered valid",
    )
    end: datetime | None = Field(
        default=None,
        description="Timestamp at which the record ceased to be valid (open ended when omitted)",
    )


class Party(DomainModel):
    """Canonical representation of a person, organisation, or location."""

    party_id: uuid.UUID = Field(default_factory=generate_uuid7, description="Canonical identifier")
    kind: PartyKind = Field(..., description="Type of party represented")
    display_name: str = Field(..., description="Preferred display name for the party")
    normalized_name: str | None = Field(
        default=None,
        description="Normalised version of the party name for matching",
    )
    country_code: str | None = Field(
        default=None,
        description="ISO country code associated with the party when available",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Timestamp when the canonical record was created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Timestamp when the canonical record was last updated",
    )
    provenance: Provenance | None = Field(
        default=None,
        description="Primary provenance of the canonical record",
    )


class PartyAlias(DomainModel):
    """Alias record mapped back to a canonical party."""

    alias_id: uuid.UUID = Field(default_factory=generate_uuid7, description="Alias identifier")
    party_id: uuid.UUID = Field(..., description="Party the alias belongs to")
    alias: str = Field(..., description="Alias text as captured from the source")
    alias_type: AliasType = Field(
        default=AliasType.LEGAL,
        description="Classification of the alias (legal, trading, historic, ...)",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score for the alias after resolution",
    )
    confidence_band: ConfidenceBand = Field(
        default=ConfidenceBand.MEDIUM,
        description="Qualitative confidence bucket derived from the numeric score",
    )
    validity: ValidityWindow = Field(
        default_factory=ValidityWindow,
        description="Validity window for the alias",
    )
    provenance: Provenance | None = Field(
        default=None,
        description="Where the alias originated from",
    )


class PartyRole(DomainModel):
    """Role linking two parties with temporal validity."""

    role_id: uuid.UUID = Field(default_factory=generate_uuid7, description="Role identifier")
    subject_party_id: uuid.UUID = Field(
        ..., description="Party fulfilling the role (e.g. the person)"
    )
    object_party_id: uuid.UUID = Field(
        ..., description="Party the role is performed for (e.g. the organisation)"
    )
    role_name: str = Field(..., description="Role label as captured")
    role_category: str | None = Field(
        default=None,
        description="Normalised category (e.g. primary_contact, owner)",
    )
    is_primary: bool = Field(
        default=False,
        description="Indicator if the role is the primary association between the parties",
    )
    validity: ValidityWindow = Field(
        default_factory=ValidityWindow,
        description="Validity window for the relationship",
    )
    provenance: Provenance | None = Field(
        default=None,
        description="Source metadata describing where the role was derived from",
    )


class ContactMethod(DomainModel):
    """Contact methods captured for a given party."""

    contact_method_id: uuid.UUID = Field(
        default_factory=generate_uuid7, description="Contact method identifier"
    )
    party_id: uuid.UUID = Field(..., description="Party the contact method belongs to")
    method_type: ContactMethodType = Field(..., description="Type of communication channel")
    value: str = Field(..., description="Contact value (email address, phone number, URL)")
    is_primary: bool = Field(
        default=False,
        description="Whether the contact method is preferred/primary",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score for the contact method",
    )
    validity: ValidityWindow = Field(
        default_factory=ValidityWindow,
        description="Validity window for the contact method",
    )
    provenance: Provenance | None = Field(
        default=None,
        description="Source metadata for the contact method",
    )


class PartyStore(DomainModel):
    """Aggregate of canonical party data."""

    parties: tuple[Party, ...] = Field(default_factory=tuple)
    aliases: tuple[PartyAlias, ...] = Field(default_factory=tuple)
    roles: tuple[PartyRole, ...] = Field(default_factory=tuple)
    contact_methods: tuple[ContactMethod, ...] = Field(default_factory=tuple)

    def extend(
        self,
        *,
        parties: Iterable[Party] | None = None,
        aliases: Iterable[PartyAlias] | None = None,
        roles: Iterable[PartyRole] | None = None,
        contact_methods: Iterable[ContactMethod] | None = None,
    ) -> PartyStore:
        """Return a new store extended with the provided objects."""

        return PartyStore(
            parties=tuple(self.parties) + tuple(parties or ()),
            aliases=tuple(self.aliases) + tuple(aliases or ()),
            roles=tuple(self.roles) + tuple(roles or ()),
            contact_methods=tuple(self.contact_methods) + tuple(contact_methods or ()),
        )

    def party_index(self) -> dict[uuid.UUID, Party]:
        """Expose a mapping between party identifier and record for quick lookups."""

        return {party.party_id: party for party in self.parties}

    def as_dict(self) -> dict[str, list[dict[str, object]]]:
        """Return the store as JSON serialisable dictionaries."""

        return {
            "party": [party.model_dump(mode="json") for party in self.parties],
            "party_alias": [alias.model_dump(mode="json") for alias in self.aliases],
            "party_role": [role.model_dump(mode="json") for role in self.roles],
            "contact_method": [contact.model_dump(mode="json") for contact in self.contact_methods],
        }
