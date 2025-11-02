---
title: Reference — industry profiles
summary: Schema, required blocks, and optional research metadata for Hotpass industry profiles.
last_updated: 2025-11-02
---

Hotpass industry profiles describe how spreadsheets are ingested, normalised, enriched,
and governed. Profiles are expressed as YAML (one per file under `apps/data-platform/hotpass/profiles/`) and
drive both the CLI defaults and the adaptive research orchestrator.

## Required structure

Profiles must provide four blocks — ingest, refine, enrich, compliance — plus core metadata.
The profile linter (`python tools/profile_lint.py`) enforces the shape shown below.

```yaml
name: aviation
display_name: Aviation & Flight Training
# Optional global defaults
default_country_code: ZA
organization_term: flight_school

# Block 1 — ingest
ingest:
  sources:
    - name: SACAA Cleaned
      format: xlsx
      path_pattern: "data/*sacaa*.xlsx"
      priority: 3
  chunk_size: 5000
  staging_enabled: true

# Block 2 — refine
refine:
  mappings:
    organization_name:
      - school_name
      - institution_name
  deduplication:
    strategy: entity_resolution
    threshold: 0.85
  expectations:
    - expect_column_values_to_not_be_null:
        column: organization_name

# Block 3 — enrich
enrich:
  allow_network: false
  fetcher_chain:
    - deterministic
    - lookup_tables
    - research

# Block 4 — compliance
compliance:
  policy: POPIA
  pii_fields:
    - contact_primary_email
```

### Metadata fields

| Field                  | Description                                                     |
| ---------------------- | --------------------------------------------------------------- |
| `name`                 | Machine-readable identifier (also used as filename).            |
| `display_name`         | Human-readable label surfaced in CLI output.                    |
| `default_country_code` | ISO country code used for normalisation defaults.               |
| `organization_term`    | Domain-specific term used in user messaging.                    |
| `source_priorities`    | Legacy priority map; superseded by `ingest.sources[].priority`. |
| `column_synonyms`      | Legacy synonym map; migrated to `refine.mappings`.              |

## Optional research metadata

Sprint 6 introduced additional fields that extend enrichment planning without breaking
existing profiles:

- `authority_sources`: list of trusted registries/directories queried before general web search. Each entry supports `name`, optional `url`, `cache_key`, and a `category` (`registry`, `directory`, or `dataset`).
- `research_backfill`: controls which fields the orchestrator may backfill. Define `fields` (list of column names) and `confidence_threshold` (0–1).
- `research_rate_limit`: throttling hints for network enrichment/crawl steps. Set `min_interval_seconds` (>= 0) to enforce a minimum delay between remote calls; optional `burst` allows that many back-to-back calls before the delay is enforced again (the burst resets once the interval elapses).
- `tools/profile_lint.py --json` emits machine-readable lint summaries for quality gates, while `--schema-json` documents the expected structure for contributors.

```yaml
authority_sources:
  - name: South African Civil Aviation Authority
    url: https://www.caa.co.za/
    cache_key: sacaa
    category: registry
research_backfill:
  fields:
    - contact_primary_email
    - website
  confidence_threshold: 0.7
```

Every native crawl stores a JSON snapshot under `.hotpass/research_runs/<entity-slug>/crawl/<timestamp>.json`
containing the query (if supplied), resolved URLs, and metadata returned by the fetchers. Profiles declaring
rate limits ensure these artefacts reflect the throttled schedule, making audits and retries deterministic.

### Provider guardrails

- Define `research_rate_limit.min_interval_seconds` and `burst` per profile to control cadence; the orchestrator enforces these limits for both deterministic and network passes.
- Use environment flags `FEATURE_ENABLE_REMOTE_RESEARCH` / `ALLOW_NETWORK_RESEARCH` to gate remote fetchers (documented in `AGENTS.md`).
- `ops/quality/ta_history_report.py` and `.hotpass/research_runs/` outputs provide audit trails for rate-limit tuning and provider SLA reviews.

Profiles omitting these sections remain valid; the orchestrator simply skips the authority/backfill
passes.

## Validation workflow

- The profile linter (`python tools/profile_lint.py`) guards structural compliance and is invoked in QG‑1.
- Contract tests (`tests/profiles/test_quality_gates.py`) ensure governed profiles align with Great Expectations suites.
- When authoring new profiles, run `python tools/profile_lint.py --profile <name>` locally and update
  `docs/reference/profiles.md` if introducing new optional fields.

## Authoring checklist

1. Copy an existing profile (for example `apps/data-platform/hotpass/profiles/generic.yaml`).
2. Update the metadata block and ingest/refine/enrich/compliance sections.
3. Declare any authority sources or backfillable fields required for adaptive research.
4. Run the linter and quality gates (`uv run hotpass qa profiles`) before committing.
