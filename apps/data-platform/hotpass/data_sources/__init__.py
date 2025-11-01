"""Adapters that ingest and harmonise the legacy Excel inputs."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ..enrichment.validators import ContactValidationService
from ..normalization import (
    clean_string,
    join_non_empty,
    normalize_email,
    normalize_phone,
    normalize_province,
    normalize_website,
)
from ..validation import validate_with_expectations, validate_with_frictionless

_CONTACT_VALIDATOR = ContactValidationService()


@dataclass(frozen=True)
class ExcelReadOptions:
    """Options controlling how Excel sheets are loaded."""

    engine: str | None = None
    chunk_size: int | None = None
    stage_to_parquet: bool = False
    stage_dir: Path | None = None

    def __post_init__(self) -> None:
        if self.chunk_size is not None and self.chunk_size <= 0:
            msg = "chunk_size must be greater than zero when provided"
            raise ValueError(msg)

    def as_reader_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if self.engine:
            kwargs["engine"] = self.engine
        return kwargs

    def should_stage(self) -> bool:
        return self.stage_to_parquet and (self.stage_dir is not None)

    def resolve_stage_dir(self, workbook_path: Path) -> Path:
        return self.stage_dir or workbook_path.parent


def _sanitise_sheet_name(sheet_name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9]+", "_", sheet_name.strip() or "sheet")
    return clean.strip("_") or "sheet"


def _read_excel(
    workbook_path: Path,
    sheet_name: str,
    options: ExcelReadOptions | None,
) -> pd.DataFrame:
    engine = options.engine if options and options.engine else None
    if options and options.chunk_size:
        frame = _read_excel_chunked(
            workbook_path,
            sheet_name,
            chunk_size=options.chunk_size,
            engine=engine,
        )
    else:
        kwargs: dict[str, Any] = {"sheet_name": sheet_name}
        if engine:
            kwargs["engine"] = engine
        frame = pd.read_excel(workbook_path, **kwargs)

    if options and options.should_stage():
        stage_dir = options.resolve_stage_dir(workbook_path)
        stage_dir.mkdir(parents=True, exist_ok=True)
        stage_path = stage_dir / f"{workbook_path.stem}__{_sanitise_sheet_name(sheet_name)}.parquet"
        try:
            frame.to_parquet(stage_path, index=False)
        except ImportError as exc:  # pragma: no cover - optional dependency
            msg = "Staging to parquet requires the optional pyarrow dependency"
            raise RuntimeError(msg) from exc
    return frame


def _read_excel_chunked(
    workbook_path: Path,
    sheet_name: str,
    *,
    chunk_size: int,
    engine: str | None,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    columns: list[str] | None = None
    data_rows_consumed = 0

    with pd.ExcelFile(workbook_path, engine=engine) as excel_file:
        while True:
            skip_value = 0 if columns is None else data_rows_consumed + 1
            chunk = pd.read_excel(
                excel_file,
                sheet_name=sheet_name,
                header=0 if columns is None else None,
                names=columns if columns is not None else None,
                skiprows=skip_value,
                nrows=chunk_size,
            )
            if chunk.empty:
                break
            if columns is None:
                columns = list(chunk.columns)
            frames.append(chunk)
            data_rows_consumed += len(chunk)
            if len(chunk) < chunk_size:
                break

    if not frames:
        return pd.DataFrame(columns=columns or None)
    return pd.concat(frames, ignore_index=True)


@dataclass
class RawRecord:
    organization_name: str
    source_dataset: str
    source_record_id: str
    province: str | None = None
    area: str | None = None
    address: str | None = None
    category: str | None = None
    organization_type: str | None = None
    status: str | None = None
    website: str | None = None
    planes: str | None = None
    description: str | None = None
    notes: str | None = None
    last_interaction_date: str | None = None
    priority: str | None = None
    contact_names: list[str] | None = None
    contact_roles: list[str] | None = None
    contact_emails: list[str] | None = None
    contact_phones: list[str] | None = None
    provenance: list[dict[str, Any]] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "organization_name": self.organization_name,
            "source_dataset": self.source_dataset,
            "source_record_id": self.source_record_id,
            "province": self.province,
            "area": self.area,
            "address": self.address,
            "category": self.category,
            "organization_type": self.organization_type,
            "status": self.status,
            "website": self.website,
            "planes": self.planes,
            "description": self.description,
            "notes": self.notes,
            "last_interaction_date": self.last_interaction_date,
            "priority": self.priority,
            "contact_names": self.contact_names or [],
            "contact_roles": self.contact_roles or [],
            "contact_emails": self.contact_emails or [],
            "contact_phones": self.contact_phones or [],
            "provenance": self.provenance or [],
        }


def _extract_normalized_emails(value: object | None) -> list[str]:
    if isinstance(value, str):
        parts = [p.strip() for p in re.split(r"[;,/|]+", value) if p.strip()]
    else:
        parts = []
    emails: list[str] = []
    for part in parts:
        normalised = normalize_email(part)
        if normalised and normalised not in emails:
            emails.append(normalised)
    return emails


def _normalise_contacts(
    df: pd.DataFrame,
    country_code: str,
    name_fields: Iterable[str],
    email_field: str,
    phone_fields: Iterable[str],
    role_field: str | None = None,
) -> list[dict[str, Any]]:
    contacts: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        name_parts = [clean_string(row.get(field)) for field in name_fields]
        name = join_non_empty(name_parts)
        raw_email = row.get(email_field)
        email_candidates = _extract_normalized_emails(raw_email)
        if not email_candidates:
            email_value: str | list[str] | None = None
        elif len(email_candidates) == 1:
            email_value = email_candidates[0]
        else:
            email_value = email_candidates
        phones: list[str] = []
        for field in phone_fields:
            normalised_phone = normalize_phone(row.get(field), country_code=country_code)
            if normalised_phone:
                phones.append(normalised_phone)
        role = clean_string(row.get(role_field)) if role_field else None
        contacts.append(
            {
                "name": name,
                "email": email_value,
                "phones": [phone for phone in phones if phone],
                "role": role,
            }
        )
    return contacts


def _split_contact_fields(
    contacts: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[str], list[str]]:
    names: list[str] = []
    roles: list[str] = []
    emails: list[str] = []
    phones: list[str] = []
    for contact in contacts:
        name = contact.get("name")
        if isinstance(name, str) and name:
            names.append(name)
        role = contact.get("role")
        if isinstance(role, str) and role:
            roles.append(role)
        email = contact.get("email")
        if isinstance(email, str) and email:
            emails.append(email)
        elif isinstance(email, list):
            for value in email:
                if isinstance(value, str) and value:
                    emails.append(value)
        contact_phones = contact.get("phones", [])
        if isinstance(contact_phones, list):
            for phone in contact_phones:
                if isinstance(phone, str) and phone:
                    phones.append(phone)
    return names, roles, emails, phones


def load_reachout_database(
    input_dir: Path, country_code: str, options: ExcelReadOptions | None = None
) -> pd.DataFrame:
    org_path = input_dir / "Reachout Database.xlsx"
    organisation_df = _read_excel(org_path, "Organisation", options)
    contacts_df = _read_excel(org_path, "Contact Info", options)

    validate_with_frictionless(
        organisation_df,
        schema_descriptor="reachout_organisation.schema.json",
        table_name="Reachout Organisation",
        source_file=f"{org_path.name}#Organisation",
    )
    validate_with_expectations(
        organisation_df,
        suite_descriptor="reachout_organisation.json",
        source_file=f"{org_path.name}#Organisation",
    )

    validate_with_frictionless(
        contacts_df,
        schema_descriptor="reachout_contact_info.schema.json",
        table_name="Reachout Contact Info",
        source_file=f"{org_path.name}#Contact Info",
    )
    validate_with_expectations(
        contacts_df,
        suite_descriptor="reachout_contact_info.json",
        source_file=f"{org_path.name}#Contact Info",
    )

    contact_groups = contacts_df.groupby("ID")
    records: list[RawRecord] = []
    for _, org in organisation_df.iterrows():
        org_id = org.get("ID")
        org_name = clean_string(org.get("Organisation Name"))
        if not org_name:
            continue
        group = (
            contact_groups.get_group(org_id) if org_id in contact_groups.groups else pd.DataFrame()
        )
        contacts = _normalise_contacts(
            group,
            country_code=country_code,
            name_fields=("Firstname", "Surname"),
            email_field="Email",
            phone_fields=("Phone", "WhatsApp"),
            role_field="Position",
        )
        names, roles, emails, phones = _split_contact_fields(contacts)
        primary_description = clean_string(org.get("Description Type"))
        notes = [
            clean_string(org.get("Notes")),
            clean_string(org.get("Open Questions")),
        ]
        record = RawRecord(
            organization_name=org_name,
            source_dataset="Reachout Database",
            source_record_id=f"reachout:{org_id}",
            province=normalize_province(org.get("Area")),
            area=clean_string(org.get("Area")),
            address=clean_string(org.get("Address")),
            category=clean_string(org.get("Type")),
            organization_type=clean_string(org.get("Type")),
            website=normalize_website(org.get("Website")),
            planes=clean_string(org.get("Planes")),
            description=join_non_empty(
                [primary_description, clean_string(org.get("Notes"))],
                separator=" | ",
            ),
            notes=join_non_empty(notes, separator=" | "),
            last_interaction_date=clean_string(org.get("Reachout Date")),
            contact_names=names,
            contact_roles=roles,
            contact_emails=emails,
            contact_phones=phones,
        )
        records.append(record)
    return pd.DataFrame([record.as_dict() for record in records])


def load_contact_database(
    input_dir: Path, country_code: str, options: ExcelReadOptions | None = None
) -> pd.DataFrame:
    path = input_dir / "Contact Database.xlsx"
    company_df = _read_excel(path, "Company_Cat", options)
    contacts_df = _read_excel(path, "Company_Contacts", options)
    addresses_df = _read_excel(path, "Company_Addresses", options)
    capture_df = _read_excel(path, "10-10-25 Capture", options)

    validate_with_frictionless(
        company_df,
        schema_descriptor="contact_company_cat.schema.json",
        table_name="Contact Company Catalogue",
        source_file=f"{path.name}#Company_Cat",
    )
    validate_with_expectations(
        company_df,
        suite_descriptor="contact_company_cat.json",
        source_file=f"{path.name}#Company_Cat",
    )

    validate_with_frictionless(
        contacts_df,
        schema_descriptor="contact_company_contacts.schema.json",
        table_name="Contact Company Contacts",
        source_file=f"{path.name}#Company_Contacts",
    )
    contacts_df = _annotate_contact_verification(contacts_df, country_code=country_code)
    validate_with_expectations(
        contacts_df,
        suite_descriptor="contact_company_contacts.json",
        source_file=f"{path.name}#Company_Contacts",
    )

    validate_with_frictionless(
        addresses_df,
        schema_descriptor="contact_company_addresses.schema.json",
        table_name="Contact Company Addresses",
        source_file=f"{path.name}#Company_Addresses",
    )
    validate_with_expectations(
        addresses_df,
        suite_descriptor="contact_company_addresses.json",
        source_file=f"{path.name}#Company_Addresses",
    )

    validate_with_frictionless(
        capture_df,
        schema_descriptor="contact_capture.schema.json",
        table_name="Contact Capture Log",
        source_file=f"{path.name}#10-10-25 Capture",
    )
    validate_with_expectations(
        capture_df,
        suite_descriptor="contact_capture.json",
        source_file=f"{path.name}#10-10-25 Capture",
    )

    contacts_grouped = contacts_df.groupby("C_ID")
    address_map: dict[str, str] = {}
    for _, addr in addresses_df.iterrows():
        cid = addr.get("C_ID")
        address = join_non_empty([addr.get("Airport"), addr.get("Unnamed: 4")], separator=", ")
        if cid not in address_map and address:
            address_map[cid] = address

    capture_notes: dict[str, str] = {}
    for _, row in capture_df.iterrows():
        school_name = clean_string(row.get("School"))
        description = join_non_empty(
            [clean_string(row.get("Description")), clean_string(row.get("Type"))],
            separator=" | ",
        )
        if school_name and description:
            capture_notes[school_name] = description

    records: list[RawRecord] = []
    for _, company in company_df.iterrows():
        company_name = clean_string(company.get("Company"))
        if not company_name:
            continue
        cid = company.get("C_ID")
        contacts_subset = (
            contacts_grouped.get_group(cid) if cid in contacts_grouped.groups else pd.DataFrame()
        )
        contacts = _normalise_contacts(
            contacts_subset,
            country_code=country_code,
            name_fields=("FirstName", "Surname"),
            email_field="Email",
            phone_fields=("Cellnumber", "Landline"),
            role_field="Position",
        )
        names, roles, emails, phones = _split_contact_fields(contacts)
        records.append(
            RawRecord(
                organization_name=company_name,
                source_dataset="Contact Database",
                source_record_id=f"contact:{cid}",
                province=None,
                area=None,
                address=address_map.get(cid),
                category=clean_string(company.get("Category")),
                organization_type=clean_string(company.get("Category")),
                status=clean_string(company.get("Status")),
                website=normalize_website(company.get("Website")),
                planes=None,
                description=capture_notes.get(company_name),
                notes=None,
                last_interaction_date=clean_string(company.get("LoadDate")),
                priority=clean_string(company.get("Priority")),
                contact_names=names,
                contact_roles=roles,
                contact_emails=emails,
                contact_phones=phones,
            )
        )
    return pd.DataFrame([record.as_dict() for record in records])


def _annotate_contact_verification(df: pd.DataFrame, *, country_code: str) -> pd.DataFrame:
    if df.empty:
        return df

    email_status: list[str | None] = []
    email_confidence: list[float | None] = []
    phone_status: list[str | None] = []
    phone_confidence: list[float | None] = []
    phone_carrier: list[str | None] = []

    for _, row in df.iterrows():
        email_value = clean_string(row.get("Email"))
        phone_value = clean_string(row.get("Cellnumber"))
        summary = _CONTACT_VALIDATOR.validate_contact(
            email=email_value,
            phone=phone_value,
            country_code=country_code,
        )
        email_result = summary.email
        phone_result = summary.phone
        email_status.append(email_result.status.value if email_result else None)
        email_confidence.append(email_result.confidence if email_result else None)
        phone_status.append(phone_result.status.value if phone_result else None)
        phone_confidence.append(phone_result.confidence if phone_result else None)
        phone_carrier.append(phone_result.carrier_name if phone_result else None)

    enriched = df.copy()
    enriched["EmailValidationStatus"] = email_status
    enriched["EmailValidationConfidence"] = email_confidence
    enriched["PhoneValidationStatus"] = phone_status
    enriched["PhoneValidationConfidence"] = phone_confidence
    enriched["PhoneCarrier"] = phone_carrier
    return enriched


def load_sacaa_cleaned(
    input_dir: Path, country_code: str, options: ExcelReadOptions | None = None
) -> pd.DataFrame:
    path = input_dir / "SACAA Flight Schools - Refined copy__CLEANED.xlsx"
    df = _read_excel(path, "Cleaned", options)

    validate_with_frictionless(
        df,
        schema_descriptor="sacaa_cleaned.schema.json",
        table_name="SACAA Cleaned",
        source_file=f"{path.name}#Cleaned",
    )
    validate_with_expectations(
        df,
        suite_descriptor="sacaa_cleaned.json",
        source_file=f"{path.name}#Cleaned",
    )
    records: list[RawRecord] = []
    for _, row in df.iterrows():
        org_name = clean_string(row.get("Name of Organisation"))
        if not org_name:
            continue
        email_candidates = _extract_normalized_emails(row.get("Contact Email Address"))
        if not email_candidates:
            contact_email: str | list[str] | None = None
        elif len(email_candidates) == 1:
            contact_email = email_candidates[0]
        else:
            contact_email = email_candidates
        contact_row = {
            "name": clean_string(row.get("Contact Person")),
            "email": contact_email,
            "phones": [normalize_phone(row.get("Contact Number"), country_code=country_code)],
            "role": None,
        }
        names, roles, emails, phones = _split_contact_fields([contact_row])
        website = normalize_website(row.get("Website URL"))
        records.append(
            RawRecord(
                organization_name=org_name,
                source_dataset="SACAA Cleaned",
                source_record_id=f"sacaa:{org_name}",
                province=normalize_province(row.get("Province")),
                area=normalize_province(row.get("Province")),
                address=None,
                category="Flight School",
                organization_type=clean_string(row.get("Status")),
                status=clean_string(row.get("Status")),
                website=website,
                planes=None,
                description=None,
                notes=None,
                last_interaction_date=None,
                contact_names=names,
                contact_roles=roles,
                contact_emails=emails,
                contact_phones=phones,
            )
        )
    return pd.DataFrame([record.as_dict() for record in records])
