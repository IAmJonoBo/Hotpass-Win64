---
title: Dataset schemas
summary: Canonical dataset contracts for Hotpass source and refined tables.
last_updated: 2025-11-02
---

# Dataset schemas

```{note}
This page is generated from the dataset contract registry. Run
`python -m hotpass.contracts.generator` to refresh the artefacts.
```

## Contact Database capture log

Schema for 10-10-25 Capture sheet in Contact Database.xlsx

**Primary key:** `School`

| Column                  | Type   | Required | Description                                           |
| ----------------------- | ------ | -------- | ----------------------------------------------------- |
| `Unnamed: 0`            | String | No       | Source worksheet row identifier                       |
| `School`                | String | Yes      | School or organisation name captured during outreach  |
| `Contact person (role)` | String | No       | Primary contact name with role context                |
| `Phone`                 | String | No       | Primary phone number captured for the contact         |
| `Email`                 | String | No       | Email address captured for the contact                |
| `Addresses`             | String | No       | Free-form address information captured from the sheet |
| `Planes`                | String | No       | Aircraft or fleet notes gathered during outreach      |
| `Website`               | String | No       | Organisation website or landing page                  |
| `Description`           | String | No       | Narrative notes captured by the outreach team         |
| `Type`                  | String | No       | Captured organisation classification from the sheet   |

### Example

```json
{
  "Unnamed: 0": "1",
  "School": "Blue Sky Flight Academy",
  "Contact person (role)": "Lerato Mokoena (Training Director)",
  "Phone": "+27 82 000 0000",
  "Email": "lerato@bluesky.ac.za",
  "Addresses": "12 Aviation Road, Midrand",
  "Planes": "Cessna 172; Piper PA-28",
  "Website": "https://www.bluesky.ac.za",
  "Description": "Focus on instrument training for commercial pilots",
  "Type": "Flight School"
}
```

## Contact Database addresses

Schema for Company_Addresses sheet in Contact Database.xlsx

**Primary key:** `C_ID, Type`

| Column       | Type   | Required | Description                                             |
| ------------ | ------ | -------- | ------------------------------------------------------- |
| `C_ID`       | Number | Yes      | Numeric company identifier from the Contact Database    |
| `Company`    | String | Yes      | Registered company name                                 |
| `Type`       | String | No       | Address type classification (for example Head Office)   |
| `Airport`    | String | No       | Associated airport or facility if present               |
| `Unnamed: 4` | String | No       | Spare column for auxiliary notes in the source workbook |

### Example

```json
{
  "C_ID": 101,
  "Company": "Northwind Aviation",
  "Type": "Head Office",
  "Airport": "FALA",
  "Unnamed: 4": "Hangar B3"
}
```

## Contact Database company catalogue

Schema for Company_Cat sheet in Contact Database.xlsx

**Primary key:** `C_ID`

| Column            | Type   | Required | Description                                     |
| ----------------- | ------ | -------- | ----------------------------------------------- |
| `C_ID`            | Number | Yes      | Numeric company identifier                      |
| `Company`         | String | Yes      | Registered company name                         |
| `QuickNooks_Name` | String | No       | Imported QuickBooks account name when available |
| `Last_Order_Date` | String | No       | Most recent recorded order date                 |
| `Category`        | String | No       | Operational category tag assigned by outreach   |
| `Strat`           | String | No       | Strategic segment classification                |
| `Priority`        | String | No       | Prioritisation tier                             |
| `Status`          | String | No       | Engagement status in the Contact Database       |
| `LoadDate`        | String | No       | Initial load date for the record                |
| `Checked`         | String | No       | Quality assurance marker from source workbook   |
| `Website`         | String | No       | Company website                                 |

### Example

```json
{
  "C_ID": 101,
  "Company": "Northwind Aviation",
  "QuickNooks_Name": "Northwind Aviation (Pty) Ltd",
  "Last_Order_Date": "2025-09-30",
  "Category": "Aviation Training",
  "Strat": "Core",
  "Priority": "High",
  "Status": "Active",
  "LoadDate": "2025-09-01",
  "Checked": "Yes",
  "Website": "https://northwind.example"
}
```

## Contact Database contacts

Schema for Company_Contacts sheet in Contact Database.xlsx

**Primary key:** `C_ID, Email, Cellnumber, Landline`

| Column       | Type   | Required | Description                       |
| ------------ | ------ | -------- | --------------------------------- |
| `C_ID`       | Number | Yes      | Numeric company identifier        |
| `Company`    | String | Yes      | Company name for the contact      |
| `Status`     | String | No       | Engagement status for the contact |
| `FirstName`  | String | No       | Contact given name                |
| `Surname`    | String | No       | Contact surname                   |
| `Position`   | String | No       | Role or job title                 |
| `Cellnumber` | String | No       | Mobile number                     |
| `Email`      | String | No       | Email address                     |
| `Landline`   | String | No       | Landline number if supplied       |

### Example

```json
{
  "C_ID": 101,
  "Company": "Northwind Aviation",
  "Status": "Primary",
  "FirstName": "Naledi",
  "Surname": "Nkosi",
  "Position": "Operations Manager",
  "Cellnumber": "+27 82 100 2000",
  "Email": "naledi.nkosi@northwind.example",
  "Landline": "011 555 0100"
}
```

## Reachout contact info sheet

Contract defining the Contact Info sheet in Reachout Database.xlsx

**Primary key:** `ID, Email, Phone`

| Column              | Type   | Required | Description                                      |
| ------------------- | ------ | -------- | ------------------------------------------------ |
| `ID`                | Number | Yes      | Reachout record identifier                       |
| `Organisation Name` | String | Yes      | Organisation associated with the outreach record |
| `Reachout Date`     | String | No       | Date the outreach took place                     |
| `Firstname`         | String | No       | Contact given name                               |
| `Surname`           | String | No       | Contact surname                                  |
| `Position`          | String | No       | Role captured during outreach                    |
| `Phone`             | String | No       | Primary phone number recorded                    |
| `WhatsApp`          | String | No       | WhatsApp number if supplied                      |
| `Email`             | String | No       | Email address recorded for the contact           |
| `Invalid`           | String | No       | Flags invalid contact information                |
| `Unnamed: 10`       | String | No       | Auxiliary notes column                           |

### Example

```json
{
  "ID": 501,
  "Organisation Name": "Aerotech College",
  "Reachout Date": "2025-08-15",
  "Firstname": "Imani",
  "Surname": "Dlamini",
  "Position": "Head of Training",
  "Phone": "+27 83 400 5000",
  "WhatsApp": "+27 83 400 5000",
  "Email": "imani.dlamini@aerotech.ac.za",
  "Invalid": "",
  "Unnamed: 10": "Prefers email follow-up"
}
```

## Reachout organisation sheet

Contract defining the Organisation sheet in Reachout Database.xlsx

**Primary key:** `ID`

| Column              | Type   | Required | Description                               |
| ------------------- | ------ | -------- | ----------------------------------------- |
| `Organisation Name` | String | Yes      | Organisation name tracked in Reachout     |
| `ID`                | Number | Yes      | Reachout record identifier                |
| `Reachout Date`     | String | No       | Date of most recent outreach              |
| `Recent_Touch_Ind`  | String | No       | Indicator flag for recent engagement      |
| `Area`              | String | No       | Geographic area                           |
| `Distance`          | String | No       | Distance notes from the Reachout workbook |
| `Type`              | String | No       | Organisation type                         |
| `Website`           | String | No       | Organisation website                      |
| `Address`           | String | No       | Physical address                          |
| `Planes`            | String | No       | Aircraft or fleet summary                 |
| `Description Type`  | String | No       | Description category                      |
| `Notes`             | String | No       | General notes                             |
| `Open Questions`    | String | No       | Outstanding questions logged by outreach  |

### Example

```json
{
  "Organisation Name": "Aerotech College",
  "ID": 501,
  "Reachout Date": "2025-08-15",
  "Recent_Touch_Ind": "Y",
  "Area": "Gauteng",
  "Distance": "35 km from Johannesburg",
  "Type": "Flight School",
  "Website": "https://aerotech.ac.za",
  "Address": "45 Sky Lane, Germiston",
  "Planes": "Diamond DA40; Tecnam P2006",
  "Description Type": "Aviation Training",
  "Notes": "Interested in data-sharing pilot",
  "Open Questions": "Need confirmation on simulator availability"
}
```

## SACAA cleaned sheet

Schema for Cleaned sheet in SACAA Flight Schools workbook

**Primary key:** `Name of Organisation`

| Column                  | Type   | Required | Description                             |
| ----------------------- | ------ | -------- | --------------------------------------- |
| `Name of Organisation`  | String | Yes      | Organisation name listed by SACAA       |
| `Province`              | String | No       | Province recorded by SACAA              |
| `Status`                | String | No       | Approval status                         |
| `Website URL`           | String | No       | Website URL captured in the SACAA sheet |
| `Contact Person`        | String | No       | Named contact person                    |
| `Contact Number`        | String | No       | Primary phone number                    |
| `Contact Email Address` | String | No       | Primary email address                   |

### Example

```json
{
  "Name of Organisation": "SkyReach Training Centre",
  "Province": "KwaZulu-Natal",
  "Status": "Approved",
  "Website URL": "https://skyreach.example",
  "Contact Person": "Sipho Zulu",
  "Contact Number": "+27 31 200 3000",
  "Contact Email Address": "info@skyreach.example"
}
```

## Hotpass single source of truth

Schema for the refined Hotpass dataset exported via the pipeline

**Primary key:** `organization_slug`

| Column                     | Type   | Required | Description                                           |
| -------------------------- | ------ | -------- | ----------------------------------------------------- |
| `organization_name`        | String | Yes      | Canonical organisation name after refinement          |
| `organization_slug`        | String | Yes      | Slugified identifier for downstream systems           |
| `province`                 | String | No       | Province derived from input datasets                  |
| `country`                  | String | No       | Country derived from input datasets                   |
| `area`                     | String | No       | Local area or region                                  |
| `address_primary`          | String | No       | Primary address for the organisation                  |
| `organization_category`    | String | No       | High-level category assigned during refinement        |
| `organization_type`        | String | No       | Detailed organisation type                            |
| `status`                   | String | No       | Lifecycle status within the refined dataset           |
| `website`                  | String | No       | Primary website                                       |
| `planes`                   | String | No       | Fleet summary                                         |
| `description`              | String | No       | Narrative description aggregated across sources       |
| `notes`                    | String | No       | Internal notes retained after refinement              |
| `source_datasets`          | String | Yes      | Comma-delimited list of contributing datasets         |
| `source_record_ids`        | String | Yes      | Identifiers for contributing source records           |
| `contact_primary_name`     | String | No       | Primary contact name after consolidation              |
| `contact_primary_role`     | String | No       | Primary contact role                                  |
| `contact_primary_email`    | String | No       | Primary contact email                                 |
| `contact_primary_phone`    | String | No       | Primary contact phone number                          |
| `contact_secondary_emails` | String | No       | Secondary email addresses aggregated across inputs    |
| `contact_secondary_phones` | String | No       | Secondary phone numbers aggregated across inputs      |
| `data_quality_score`       | Number | No       | Composite quality score generated by the pipeline     |
| `data_quality_flags`       | String | No       | Delimited quality flags from validation               |
| `selection_provenance`     | String | No       | Details on how the record was selected or prioritised |
| `last_interaction_date`    | String | No       | Last known interaction date                           |
| `priority`                 | String | No       | Priority ranking used by downstream teams             |
| `privacy_basis`            | String | No       | Documented privacy basis for retaining the data       |

### Example

```json
{
  "organization_name": "Northwind Aviation",
  "organization_slug": "northwind-aviation",
  "province": "Gauteng",
  "country": "South Africa",
  "area": "Johannesburg",
  "address_primary": "45 Sky Lane, Germiston",
  "organization_category": "Aviation Training",
  "organization_type": "Flight School",
  "status": "Active",
  "website": "https://northwind.example",
  "planes": "Cessna 172; Piper PA-28",
  "description": "Instrument-focused commercial pilot academy",
  "notes": "High engagement potential for Q1 intake",
  "source_datasets": "contact_capture, reachout_organisation",
  "source_record_ids": "capture:1|reachout:501",
  "contact_primary_name": "Naledi Nkosi",
  "contact_primary_role": "Operations Manager",
  "contact_primary_email": "naledi.nkosi@northwind.example",
  "contact_primary_phone": "+27 82 100 2000",
  "contact_secondary_emails": "info@northwind.example; support@northwind.example",
  "contact_secondary_phones": "011 555 0100",
  "data_quality_score": 0.92,
  "data_quality_flags": "email_verified;has_recent_touch",
  "selection_provenance": "reachout_follow_up",
  "last_interaction_date": "2025-09-20",
  "priority": "High",
  "privacy_basis": "Legitimate interest"
}
```
