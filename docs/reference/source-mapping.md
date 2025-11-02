---
title: Reference — source-to-target mapping
summary: Trace how raw spreadsheet columns map to the canonical SSOT schema.
last_updated: 2025-11-02
---

The source-to-target mapping defines how the ingestion layer normalises incoming spreadsheets. Use this reference when onboarding a new datasource or debugging missing values.

## Mapping conventions

- **Synonyms**: Profiles declare accepted aliases for each canonical field. The column mapper picks the best match at runtime.
- **Priority**: When multiple sources provide the same field, Hotpass keeps the value from the highest-priority source.
- **Transformation**: Some fields (for example, phone numbers) are normalised before merging.

## Example mapping

| Canonical field         | Source columns                      | Transformation                                                       |
| ----------------------- | ----------------------------------- | -------------------------------------------------------------------- |
| `organization_name`     | `Company`, `School`, `Organisation` | Title-case normalisation.                                            |
| `organization_type`     | `Type`, `Category`                  | Mapped via profile-specific lookup tables.                           |
| `primary_contact_email` | `Email`, `Primary Email`            | Lower-cased and validated against regex.                             |
| `primary_contact_phone` | `Phone`, `Cell`                     | Converted to E.164 format with the profile’s `default_country_code`. |
| `status`                | `Status`, `Lifecycle`               | Restricted to the canonical status enum.                             |
| `geocode_latitude`      | `Latitude`, `Lat`                   | Cast to float and rounded to 4 decimals.                             |
| `enrichment_sources`    | `Source`, `Verified By`             | Aggregated into a comma-separated list.                              |

## Adding a new mapping

1. Update the relevant profile under `apps/data-platform/hotpass/profiles/` with the new synonyms.
2. Add transformation logic in `apps/data-platform/hotpass/column_mapping.py` if the field requires custom handling.
3. Extend the appropriate tests (`tests/test_column_mapping.py`, `tests/test_contacts.py`) to cover the new scenario.

Consistently updating mappings keeps the SSOT coherent and prevents regressions in the downstream dashboards.
