from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd
import pytest

pytest.importorskip("stdnum")

from hotpass.domain.party import (
    AliasType,
    ContactMethodType,
    PartyKind,
    build_party_store_from_refined,
    render_dictionary,
)


def _selection_payload() -> str:
    return json.dumps(
        {
            "organization_name": {
                "source_dataset": "SACAA Cleaned",
                "source_record_id": "ORG-1",
                "source_priority": 3,
                "quality_score": 0.92,
                "last_interaction_date": "2025-01-12",
            },
            "contact_primary_name": {
                "source_dataset": "Reachout Database",
                "source_record_id": "CONTACT-7",
                "source_priority": 2,
                "quality_score": 0.75,
                "last_interaction_date": "2025-01-10",
            },
            "contact_primary_email": {
                "source_dataset": "Reachout Database",
                "source_record_id": "CONTACT-7",
                "source_priority": 2,
                "quality_score": 0.8,
            },
            "contact_primary_phone": {
                "source_dataset": "Reachout Database",
                "source_record_id": "CONTACT-7",
                "source_priority": 1,
            },
            "website": {
                "source_dataset": "SACAA Cleaned",
                "source_record_id": "ORG-1",
                "source_priority": 3,
            },
            "address_primary": {
                "source_dataset": "Contact Database",
                "source_record_id": "ADDR-22",
                "source_priority": 1,
            },
        }
    )


def test_build_party_store_from_refined_creates_entities() -> None:
    refined = pd.DataFrame(
        [
            {
                "organization_name": "Aero School",
                "organization_slug": "aero-school",
                "province": "Gauteng",
                "country": "South Africa",
                "area": "Johannesburg",
                "address_primary": "Hangar 1",
                "organization_category": "Flight School",
                "organization_type": "Training",
                "status": "Active",
                "website": "https://aero.example",
                "planes": "Sling 2",
                "description": "Light aircraft training",
                "notes": "Primary outreach target",
                "source_datasets": "SACAA Cleaned; Reachout Database",
                "source_record_ids": "ORG-1; CONTACT-7",
                "contact_primary_name": "Jane Doe",
                "contact_primary_role": "Chief Pilot",
                "contact_primary_email": "jane.doe@aero.example",
                "contact_primary_phone": "+27 82 123 0000",
                "contact_secondary_emails": "ops@aero.example; info@aero.example",
                "contact_secondary_phones": "0829991111",
                "data_quality_score": 0.9,
                "data_quality_flags": "none",
                "selection_provenance": _selection_payload(),
                "last_interaction_date": "2025-01-12",
                "priority": "High",
                "privacy_basis": "Legitimate Interest",
            }
        ]
    )

    store = build_party_store_from_refined(
        refined,
        default_country="ZA",
        execution_time=datetime(2025, 1, 20, tzinfo=UTC),
    )

    from tests.helpers.assertions import expect

    expect(len(store.parties) == 2, "Should create exactly 2 parties (1 org, 1 person)")
    org = next(party for party in store.parties if party.kind == PartyKind.ORGANISATION)
    contact = next(party for party in store.parties if party.kind == PartyKind.PERSON)

    expect(org.display_name == "Aero School", "Organization name should match")
    expect(contact.display_name == "Jane Doe", "Contact name should match")

    org_aliases = [alias for alias in store.aliases if alias.party_id == org.party_id]
    expect(
        any(
            alias.alias == "Aero School" and alias.alias_type == AliasType.LEGAL
            for alias in org_aliases
        ),
        "Should have legal alias for organization",
    )
    expect(
        any(
            alias.alias == "SACAA Cleaned" and alias.alias_type == AliasType.HISTORIC
            for alias in org_aliases
        ),
        "Should have historic alias from source dataset",
    )

    expect(
        any(
            method.method_type == ContactMethodType.EMAIL
            and method.value == "jane.doe@aero.example"
            and method.is_primary
            for method in store.contact_methods
            if method.party_id == contact.party_id
        ),
        "Should have primary email contact method",
    )
    expect(
        any(
            role.object_party_id == org.party_id and role.subject_party_id == contact.party_id
            for role in store.roles
        ),
        "Should have relationship between contact and organization",
    )


def test_render_dictionary_includes_party_fields() -> None:
    markdown = render_dictionary()
    from tests.helpers.assertions import expect

    expect("Party" in markdown, "Dictionary should include Party entity")
    expect("Alias" in markdown, "Dictionary should include Alias entity")
    expect("ContactMethod" in markdown, "Dictionary should include ContactMethod entity")
