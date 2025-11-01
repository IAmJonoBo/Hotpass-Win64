"""Helpers to load canonical party data from refined Hotpass outputs."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime

import pandas as pd

from hotpass.normalization import clean_string, slugify

from .models import (
    AliasType,
    ConfidenceBand,
    ContactMethod,
    ContactMethodType,
    Party,
    PartyAlias,
    PartyKind,
    PartyRole,
    PartyStore,
    Provenance,
    ValidityWindow,
    generate_uuid7,
)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=UTC)
    except ValueError:
        return None


def _confidence_band(score: float) -> ConfidenceBand:
    if score >= 0.75:
        return ConfidenceBand.HIGH
    if score >= 0.5:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


def _coerce_confidence(provenance: Provenance | None, default: float = 0.5) -> float:
    if provenance is None:
        return default
    base = default
    if provenance.selection_priority:
        base = max(base, min(1.0, 0.25 + 0.2 * provenance.selection_priority))
    if provenance.quality_score is not None:
        base = max(base, min(1.0, provenance.quality_score))
    return float(max(0.05, min(1.0, base)))


def _parse_selection_provenance(raw: str | None) -> dict[str, dict[str, object]]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {key: value for key, value in data.items() if isinstance(value, dict)}


def _provenance_from(selection: dict[str, object]) -> Provenance | None:
    if not selection:
        return None
    source = clean_string(selection.get("source_dataset")) or "Unknown"
    record_id = clean_string(selection.get("source_record_id"))
    captured = selection.get("last_interaction_date")
    timestamp = None
    if isinstance(captured, str):
        timestamp = _parse_iso_datetime(captured)
    priority = selection.get("source_priority")
    if isinstance(priority, str) and priority.isdigit():
        priority_value = int(priority)
    elif isinstance(priority, int | float):
        priority_value = int(priority)
    else:
        priority_value = 0
    quality_score = selection.get("quality_score")
    if isinstance(quality_score, str):
        try:
            quality_score_value = float(quality_score)
        except ValueError:
            quality_score_value = None
    elif isinstance(quality_score, int | float):
        quality_score_value = float(quality_score)
    else:
        quality_score_value = None
    if quality_score_value is not None and quality_score_value > 1.0:
        quality_score_value = min(1.0, quality_score_value / 5.0)
    return Provenance(
        source=source,
        record_id=record_id,
        captured_at=timestamp,
        selection_priority=priority_value,
        quality_score=quality_score_value,
    )


def _split_multi(value: object | None) -> Iterator[str]:
    if not value:
        return
    if isinstance(value, str):
        tokens: Iterable[object] = re.split(r"[;,]", value)
    elif isinstance(value, Iterable):
        tokens = list(value)
    else:
        return
    for token in tokens:
        cleaned = clean_string(token)
        if cleaned:
            yield cleaned


def _normalise_person_name(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = clean_string(name)
    if not cleaned:
        return None
    return " ".join(part for part in cleaned.split() if part)


def build_party_store_from_refined(
    refined: pd.DataFrame,
    *,
    default_country: str | None = None,
    execution_time: datetime | None = None,
) -> PartyStore:
    """Translate the refined SSOT dataframe into canonical party records."""

    if refined.empty:
        return PartyStore()

    timestamp = execution_time or datetime.now(tz=UTC)
    selection_cache = [
        _parse_selection_provenance(value) for value in refined.get("selection_provenance", [])
    ]

    organisation_parties: dict[str, Party] = {}
    person_parties: dict[str, Party] = {}
    aliases: list[PartyAlias] = []
    roles: list[PartyRole] = []
    contact_methods: list[ContactMethod] = []

    for index, row in refined.reset_index(drop=True).iterrows():
        slug = clean_string(row.get("organization_slug")) or str(index)
        display_name = clean_string(row.get("organization_name")) or slug
        provenance_map = selection_cache[index] if index < len(selection_cache) else {}
        org_prov = _provenance_from(provenance_map.get("organization_name", {}))
        organisation_party = organisation_parties.get(slug)
        if organisation_party is None:
            organisation_party = Party(
                party_id=generate_uuid7(),
                kind=PartyKind.ORGANISATION,
                display_name=display_name,
                normalized_name=slugify(display_name) if display_name else slug,
                country_code=row.get("country") or default_country,
                created_at=timestamp,
                updated_at=timestamp,
                provenance=org_prov,
            )
            organisation_parties[slug] = organisation_party
            alias_confidence = _coerce_confidence(org_prov, default=0.6)
            aliases.append(
                PartyAlias(
                    party_id=organisation_party.party_id,
                    alias=display_name,
                    alias_type=AliasType.LEGAL,
                    confidence=alias_confidence,
                    confidence_band=_confidence_band(alias_confidence),
                    validity=ValidityWindow(start=timestamp),
                    provenance=org_prov,
                )
            )
            for dataset in _split_multi(row.get("source_datasets")):
                dataset_confidence = _coerce_confidence(org_prov, default=0.4)
                dataset_alias = PartyAlias(
                    party_id=organisation_party.party_id,
                    alias=dataset,
                    alias_type=AliasType.HISTORIC,
                    confidence=dataset_confidence,
                    confidence_band=_confidence_band(dataset_confidence),
                    validity=ValidityWindow(start=timestamp),
                    provenance=org_prov,
                )
                aliases.append(dataset_alias)

        primary_contact_name = clean_string(row.get("contact_primary_name"))
        primary_contact_role = clean_string(row.get("contact_primary_role")) or "Primary contact"
        primary_email = clean_string(row.get("contact_primary_email"))
        primary_phone = clean_string(row.get("contact_primary_phone"))

        person_key = None
        if primary_email:
            person_key = f"email:{primary_email.lower()}"
        elif primary_phone:
            person_key = f"phone:{primary_phone}"
        elif primary_contact_name:
            person_key = f"name:{primary_contact_name.lower()}"

        contact_party = None
        if person_key:
            contact_party = person_parties.get(person_key)
            name_provenance = _provenance_from(provenance_map.get("contact_primary_name", {}))
            if contact_party is None:
                display_contact = (
                    primary_contact_name or primary_email or primary_phone or "Unknown"
                )
                contact_party = Party(
                    party_id=generate_uuid7(),
                    kind=PartyKind.PERSON,
                    display_name=display_contact,
                    normalized_name=_normalise_person_name(primary_contact_name),
                    country_code=default_country or row.get("country"),
                    created_at=timestamp,
                    updated_at=timestamp,
                    provenance=name_provenance,
                )
                person_parties[person_key] = contact_party
                if primary_contact_name:
                    contact_confidence = _coerce_confidence(name_provenance, default=0.55)
                    aliases.append(
                        PartyAlias(
                            party_id=contact_party.party_id,
                            alias=primary_contact_name,
                            alias_type=AliasType.LEGAL,
                            confidence=contact_confidence,
                            confidence_band=_confidence_band(contact_confidence),
                            validity=ValidityWindow(start=timestamp),
                            provenance=name_provenance,
                        )
                    )

            role_provenance = _provenance_from(provenance_map.get("contact_primary_role", {}))
            last_seen = row.get("last_interaction_date")
            start_ts = _parse_iso_datetime(last_seen) or timestamp
            roles.append(
                PartyRole(
                    subject_party_id=contact_party.party_id,
                    object_party_id=organisation_party.party_id,
                    role_name=primary_contact_role,
                    role_category="primary_contact",
                    is_primary=True,
                    validity=ValidityWindow(start=start_ts),
                    provenance=role_provenance or name_provenance or org_prov,
                )
            )

            if primary_email:
                email_prov = _provenance_from(provenance_map.get("contact_primary_email", {}))
                email_confidence = _coerce_confidence(email_prov, default=0.75)
                contact_methods.append(
                    ContactMethod(
                        party_id=contact_party.party_id,
                        method_type=ContactMethodType.EMAIL,
                        value=primary_email,
                        is_primary=True,
                        confidence=email_confidence,
                        validity=ValidityWindow(start=timestamp),
                        provenance=email_prov or name_provenance,
                    )
                )
            if primary_phone:
                phone_prov = _provenance_from(provenance_map.get("contact_primary_phone", {}))
                phone_confidence = _coerce_confidence(phone_prov, default=0.65)
                contact_methods.append(
                    ContactMethod(
                        party_id=contact_party.party_id,
                        method_type=ContactMethodType.PHONE,
                        value=primary_phone,
                        is_primary=not primary_email,
                        confidence=phone_confidence,
                        validity=ValidityWindow(start=timestamp),
                        provenance=phone_prov or name_provenance,
                    )
                )
            for email in _split_multi(row.get("contact_secondary_emails")):
                contact_methods.append(
                    ContactMethod(
                        party_id=contact_party.party_id,
                        method_type=ContactMethodType.EMAIL,
                        value=email,
                        is_primary=False,
                        confidence=0.5,
                        validity=ValidityWindow(start=timestamp),
                        provenance=name_provenance,
                    )
                )
            for phone in _split_multi(row.get("contact_secondary_phones")):
                contact_methods.append(
                    ContactMethod(
                        party_id=contact_party.party_id,
                        method_type=ContactMethodType.PHONE,
                        value=phone,
                        is_primary=False,
                        confidence=0.4,
                        validity=ValidityWindow(start=timestamp),
                        provenance=name_provenance,
                    )
                )

        website = clean_string(row.get("website"))
        if website:
            web_prov = _provenance_from(provenance_map.get("website", {}))
            contact_methods.append(
                ContactMethod(
                    party_id=organisation_party.party_id,
                    method_type=ContactMethodType.WEBSITE,
                    value=website,
                    is_primary=True,
                    confidence=_coerce_confidence(web_prov, default=0.6),
                    validity=ValidityWindow(start=timestamp),
                    provenance=web_prov or org_prov,
                )
            )

        address = clean_string(row.get("address_primary"))
        if address:
            address_prov = _provenance_from(provenance_map.get("address_primary", {}))
            contact_methods.append(
                ContactMethod(
                    party_id=organisation_party.party_id,
                    method_type=ContactMethodType.PHYSICAL_ADDRESS,
                    value=address,
                    is_primary=True,
                    confidence=_coerce_confidence(address_prov, default=0.55),
                    validity=ValidityWindow(start=timestamp),
                    provenance=address_prov or org_prov,
                )
            )

    parties = tuple(organisation_parties.values()) + tuple(person_parties.values())
    return PartyStore(
        parties=parties,
        aliases=tuple(aliases),
        roles=tuple(roles),
        contact_methods=tuple(contact_methods),
    )
