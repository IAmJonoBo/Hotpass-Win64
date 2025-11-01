"""Tests for enhanced contact management."""

import pandas as pd
import pytest

pytest.importorskip("frictionless")

from hotpass.contacts import Contact, OrganizationContacts, consolidate_contacts_from_rows
from hotpass.enrichment.validators import (
    ContactValidationService,
    EmailValidationResult,
    PhoneValidationResult,
    ValidationStatus,
)


def test_contact_calculate_completeness():
    """Test contact completeness calculation."""
    complete = Contact(
        name="John Doe",
        email="john@example.com",
        phone="+1234567890",
        role="CEO",
        department="Executive",
    )

    partial = Contact(
        name="Jane Doe",
        email="jane@example.com",
    )

    assert complete.calculate_completeness() == 1.0
    assert partial.calculate_completeness() == 0.4  # 2 out of 5 fields


def test_contact_to_dict_roundtrip():
    """Test contact serialization."""
    contact = Contact(
        name="John Doe",
        email="john@example.com",
        phone="+1234567890",
        role="Manager",
    )
    contact.lead_score = 0.42
    contact.verification_score = 0.55
    contact.validation_flags = ["email:risky"]
    contact.email_validation = EmailValidationResult(
        address="john@example.com",
        status=ValidationStatus.RISKY,
        confidence=0.4,
        reason="missing_mx_records",
    )
    contact.phone_validation = PhoneValidationResult(
        number="+1234567890",
        status=ValidationStatus.DELIVERABLE,
        confidence=0.9,
    )

    data = contact.to_dict()
    restored = Contact.from_dict(data)

    assert restored.name == contact.name
    assert restored.email == contact.email
    assert restored.phone == contact.phone
    assert restored.role == contact.role
    assert restored.lead_score == contact.lead_score
    assert restored.verification_score == contact.verification_score
    assert restored.validation_flags == contact.validation_flags
    assert restored.email_validation is not None
    assert restored.phone_validation is not None


def test_contact_validation_adjusts_completeness():
    """Deliverability signals should boost or penalise completeness."""
    base = Contact(name="Valid", email="valid@hotpass.example")
    base.email_validation = EmailValidationResult(
        address="valid@hotpass.example",
        status=ValidationStatus.DELIVERABLE,
        confidence=0.9,
    )
    risky = Contact(name="Risky", email="risky@hotpass.example")
    risky.email_validation = EmailValidationResult(
        address="risky@hotpass.example",
        status=ValidationStatus.RISKY,
        confidence=0.6,
    )
    blocked = Contact(name="Blocked", email="blocked@hotpass.example")
    blocked.email_validation = EmailValidationResult(
        address="blocked@hotpass.example",
        status=ValidationStatus.UNDELIVERABLE,
        confidence=0.85,
        reason="smtp_failure",
    )

    assert base.calculate_completeness() > risky.calculate_completeness()
    assert risky.calculate_completeness() > blocked.calculate_completeness()


def test_organization_contacts_add_contact():
    """Test adding contacts to organization."""
    org = OrganizationContacts("Acme Inc")

    contact = Contact(name="John Doe", email="john@example.com")
    org.add_contact(contact)

    assert len(org.contacts) == 1
    assert org.contacts[0].name == "John Doe"


def test_organization_contacts_get_primary():
    """Test getting primary contact."""
    org = OrganizationContacts("Acme Inc")

    contact1 = Contact(name="John Doe", email="john@example.com", preference_score=0.5)
    contact2 = Contact(name="Jane Doe", email="jane@example.com", preference_score=0.8)

    org.add_contact(contact1)
    org.add_contact(contact2)

    primary = org.get_primary_contact()

    assert primary is not None
    assert primary.name == "Jane Doe"  # Higher preference score


def test_organization_contacts_get_by_role():
    """Test filtering contacts by role."""
    org = OrganizationContacts("Acme Inc")

    org.add_contact(Contact(name="John Doe", role="CEO"))
    org.add_contact(Contact(name="Jane Doe", role="Manager"))
    org.add_contact(Contact(name="Bob Smith", role="Manager"))

    managers = org.get_contacts_by_role("Manager")

    assert len(managers) == 2
    assert all(c.role == "Manager" for c in managers)


def test_organization_contacts_get_all_emails():
    """Test getting all unique emails."""
    org = OrganizationContacts("Acme Inc")

    org.add_contact(Contact(name="John", email="john@example.com"))
    org.add_contact(Contact(name="Jane", email="jane@example.com"))
    org.add_contact(Contact(name="John2", email="john@example.com"))  # Duplicate

    emails = org.get_all_emails()

    assert len(emails) == 2  # Duplicates removed
    assert "john@example.com" in emails
    assert "jane@example.com" in emails


def test_organization_contacts_calculate_preference_scores():
    """Test preference score calculation."""
    org = OrganizationContacts("Acme Inc")

    contact1 = Contact(
        name="John Doe",
        email="john@example.com",
        role="CEO",
        source_dataset="High Priority Source",
    )
    contact2 = Contact(
        name="Jane Doe",
        email="jane@example.com",
        role="Assistant",
        source_dataset="Low Priority Source",
    )

    org.add_contact(contact1)
    org.add_contact(contact2)

    org.calculate_preference_scores(source_priority={"High Priority Source": 2})

    # CEO should have higher preference score than assistant
    assert contact1.preference_score > contact2.preference_score
    assert contact1.verification_score >= 0.0
    assert org.contacts[0].lead_score is not None


def test_organization_contacts_to_flat_dict():
    """Test flattening to SSOT format."""
    org = OrganizationContacts("Acme Inc")

    primary = Contact(
        name="John Doe",
        email="john@example.com",
        phone="+1234567890",
        role="CEO",
        preference_score=1.0,
    )
    primary.email_validation = EmailValidationResult(
        address="john@example.com",
        status=ValidationStatus.DELIVERABLE,
        confidence=0.9,
    )
    primary.phone_validation = PhoneValidationResult(
        number="+1234567890",
        status=ValidationStatus.DELIVERABLE,
        confidence=0.8,
    )
    secondary = Contact(
        name="Jane Doe",
        email="jane@example.com",
        phone="+9876543210",
        role="Manager",
        preference_score=0.5,
    )

    org.add_contact(primary)
    org.add_contact(secondary)

    flat = org.to_flat_dict()

    assert flat["organization_name"] == "Acme Inc"
    assert flat["contact_primary_name"] == "John Doe"
    assert flat["contact_primary_email"] == "john@example.com"
    assert flat["contact_primary_email_confidence"] == primary.email_validation.confidence
    assert "jane@example.com" in flat["contact_secondary_emails"]
    assert flat["total_contacts"] == 2
    assert flat["contact_email_confidence_avg"] == pytest.approx(0.9)
    assert flat["contact_phone_confidence_avg"] == pytest.approx(0.8)
    assert flat["contact_lead_score_avg"] is None  # no lead scores set yet
    assert flat["contact_verification_score_avg"] is None


def test_consolidate_contacts_from_rows():
    """Test consolidating contacts from DataFrame rows."""
    df = pd.DataFrame(
        {
            "source_dataset": ["Source A", "Source B"],
            "source_record_id": ["1", "2"],
            "contact_names": [["John Doe"], ["Jane Doe"]],
            "contact_emails": [["john@example.com"], ["jane@example.com"]],
            "contact_phones": [["+1234567890"], ["+9876543210"]],
            "contact_roles": [["CEO"], ["Manager"]],
        }
    )

    org = consolidate_contacts_from_rows(
        "Acme Inc",
        df,
        source_priority={"Source A": 2, "Source B": 1},
    )

    assert org.organization_name == "Acme Inc"
    assert len(org.contacts) == 2
    assert org.contacts[0].preference_score > 0  # Scores were calculated
    assert all(contact.email_validation for contact in org.contacts)
    assert all(contact.email and "@" in contact.email for contact in org.contacts)
    assert all(contact.verification_score >= 0 for contact in org.contacts)


def test_contact_validation_service_caches_results():
    """Ensure repeated validations reuse cached results."""
    service = ContactValidationService()
    result_one = service.validate_contact(
        email="cache@example.com",
        phone="+27123456789",
        country_code="ZA",
    )
    result_two = service.validate_contact(
        email="cache@example.com",
        phone="+27123456789",
        country_code="ZA",
    )

    assert result_one.email is result_two.email
    assert result_one.phone is result_two.phone
