---
title: Reference — SSOT data model
summary: Canonical fields, types, and descriptions for the Hotpass single source of truth (SSOT).
last_updated: 2025-11-02
---

Hotpass standardises heterogeneous spreadsheets into a single source of truth (SSOT). The table below lists the core entities and fields produced by the pipeline.

## Organisation fields

| Field                 | Type    | Description                                                            |
| --------------------- | ------- | ---------------------------------------------------------------------- |
| `organization_id`     | UUID    | Stable identifier generated during ingestion.                          |
| `organization_name`   | string  | Canonical display name for the organisation.                           |
| `organization_type`   | string  | Industry-specific classification (for example, `flight_school`).       |
| `organization_status` | string  | Operational status derived from source systems.                        |
| `country_code`        | string  | ISO 3166-1 alpha-2 country code.                                       |
| `region`              | string  | State or province when available.                                      |
| `source_priority`     | integer | Priority score that determines which source wins when merging records. |

## Contact fields

| Field                   | Type   | Description                                         |
| ----------------------- | ------ | --------------------------------------------------- |
| `primary_contact_name`  | string | Selected using source priority and role preference. |
| `primary_contact_email` | string | Email address validated by `email_validity`.        |
| `primary_contact_phone` | string | E.164-formatted phone number when detected.         |
| `all_contact_emails`    | string | Semicolon-delimited list of emails for auditing.    |
| `all_contact_phones`    | string | Semicolon-delimited list of phone numbers.          |

## Quality and enrichment fields

| Field                 | Type    | Description                                                         |
| --------------------- | ------- | ------------------------------------------------------------------- |
| `completeness_score`  | float   | Weighted completeness metric from 0–1.                              |
| `priority_score`      | float   | Combined completeness and quality score used by entity resolution.  |
| `validation_failures` | integer | Number of failing Great Expectations checks.                        |
| `pii_detected`        | boolean | True when POPIA-sensitive data is found.                            |
| `geocode_latitude`    | float   | Latitude from the geospatial enrichment stage.                      |
| `geocode_longitude`   | float   | Longitude from the geospatial enrichment stage.                     |
| `enrichment_sources`  | string  | Comma-separated list of enrichment providers that contributed data. |

## Audit fields

| Field               | Type     | Description                                                     |
| ------------------- | -------- | --------------------------------------------------------------- |
| `source_records`    | integer  | Count of source rows merged into the final record.              |
| `source_systems`    | string   | Comma-separated systems that contributed to the record.         |
| `last_refreshed_at` | datetime | Timestamp of the latest successful pipeline run.                |
| `run_id`            | UUID     | Identifier for the pipeline execution that produced the record. |

Refer to the [source mapping reference](./source-mapping.md) for details on how raw columns flow into these canonical fields.
