---
title: How-to — configure Hotpass for your organisation
summary: Customise industry profiles, column mapping, and runtime options to fit your data landscape.
last_updated: 2025-11-02
---

Hotpass ships with aviation defaults but can be tailored to any industry. Follow these steps to align the platform with your organisation’s data.

## 1. Select or create an industry profile

Profiles define synonyms, validation thresholds, and contact preferences.

```python
from hotpass.config import get_default_profile

profile = get_default_profile("aviation")
print(profile.display_name)
```

To create your own profile, add a YAML file under `apps/data-platform/hotpass/profiles/`:

```yaml
name: healthcare
display_name: Healthcare Facilities
default_country_code: US
organization_term: facility
source_priorities:
  Cms Database: 3
  State Registry: 2
column_synonyms:
  organization_name:
    - facility_name
    - provider_name
authority_sources:
  - name: US HCRIS Registry
    url: https://data.cms.gov/
    cache_key: hcris
    category: registry
research_backfill:
  fields:
    - contact_primary_email
    - website
  confidence_threshold: 0.7
```

Reload the profile in Python:

```python
from hotpass.config import load_industry_profile
healthcare = load_industry_profile("healthcare")
```

`authority_sources` declares authoritative registries the adaptive research orchestrator should consult before falling back to web search, while `research_backfill` lists which optional fields may be repopulated during the backfill pass and the minimum confidence score required to accept network results.

## 2. Tune the pipeline configuration

Start by generating a workspace scaffold so you have baseline configuration files to edit:

```bash
uv run hotpass init --path ./workspace
uv run hotpass doctor --config ./workspace/config/pipeline.quickstart.toml
```

After the scaffold completes, adjust the settings you need in the generated configuration files.

Copy `config/pipeline.example.yaml` and adjust the options you need:

- `input_dir` / `output_path`: point to your source and destination folders.
- `archive`: enable to keep the original spreadsheets for auditing.
- `country_code`: default for phone and address parsing.
- `validation`: override thresholds per field type.
- `intent_digest_path`: emit a ranked prospect list with the latest intent signals.
- `intent_signal_store_path`: persist collector payloads with provenance metadata for reuse.
- `daily_list_path` / `daily_list_size`: generate the daily prospect export used by automation hooks.
- `intent_webhooks`: send the daily digest to third-party systems after each run.
- `crm_endpoint` / `crm_token`: push the generated daily list directly to your CRM.

Run the pipeline with the custom config:

```bash
uv run hotpass refine --config config/pipeline.healthcare.yaml --profile healthcare --archive
```

Install the scoring dependencies before running the automation workflow:

```bash
uv sync --extra dev --extra enrichment --extra orchestration --extra ml_scoring
```

### Train and evaluate the lead scoring model

The scoring workflow expects a binary target column (for example `won`) and feature
columns aligned with the `LeadScoringModel` defaults. Train the model on a curated
dataset and capture evaluation metrics before you enable automation hooks:

```python
from pathlib import Path

import pandas as pd

from hotpass.transform.scoring import train_lead_scoring_model

dataset = pd.read_csv("./data/training/leads.csv")
result = train_lead_scoring_model(
    dataset,
    target_column="won",
    metrics_path=Path("./dist/metrics/lead_scoring.json"),
    metric_thresholds={"roc_auc": 0.7, "recall": 0.6},
)

print(result.metrics)
```

Hotpass automatically writes the metrics and metadata payload to
`dist/metrics/lead_scoring.json` (or the path you provide). The metadata includes the
feature list, dataset sizes, and the timestamp used for the training run. Downstream
automation (for example CI jobs or Prefect flows) can parse the JSON artefact and halt
deployments when a metric drops below the configured threshold. Treat the artefact as a
living record—commit significant runs alongside code changes so you can monitor model
drift over time.

When you attach the trained model to daily list generation, the scoring pipeline applies
the same logistic calibration used by manual lead scoring. The calibration keeps scores
between 0 and 1 and emphasises separation around 0.5 so operators can compare pipeline
outputs with historical exports.

### Canonical schema and migration

Behind the scenes the CLI now converts every profile, config file, and CLI flag into the
canonical `HotpassConfig` model. You can express the full configuration directly in TOML:

```toml
[pipeline]
input_dir = "./data"
output_path = "./dist/refined.xlsx"
archive = true
dist_dir = "./dist"
intent_digest_path = "./dist/daily-intent.parquet"

[pipeline.intent]
enabled = true
deduplicate = true

[[pipeline.intent.collectors]]
name = "news"
weight = 1.4

[[pipeline.intent.collectors.options.events."aero-school"]]
headline = "Aero School secures defence contract"
intent = 0.9
timestamp = "2025-10-23T08:00:00Z"
url = "https://example.test/aero/contract"

[[pipeline.intent.targets]]
identifier = "Aero School"
slug = "aero-school"

[pipeline.intent.storage]
path = "./data/intent-signals.json"
max_age_hours = 6

[pipeline.intent.credentials]
token = "${HOTPASS_INTENT_TOKEN}"

[features]
compliance = true

[governance]
intent = ["Process POPIA regulated dataset"]
data_owner = "Data Governance"
classification = "sensitive_pii"

[pipeline]
daily_list_path = "./dist/daily-list.csv"
daily_list_size = 100
intent_webhooks = ["https://hooks.example/pipeline"]
crm_endpoint = "https://crm.example/api/leads"
crm_token = "${CRM_TOKEN}"
```

Legacy configuration dictionaries can be upgraded automatically:

```python
from hotpass.config_doctor import ConfigDoctor

doctor = ConfigDoctor()
config, notices = doctor.upgrade_payload(legacy_payload)
if doctor.autofix():
    print("Applied governance autofixes")
for diagnostic in doctor.diagnose():
    print(diagnostic)
```

Autofix injects sensible governance defaults (for example `Data Governance` as the data owner)
and flags missing intent declarations when compliance or PII detection is enabled. The resulting
`HotpassConfig` instance exposes `.to_pipeline_config()` and `.to_enhanced_config()` helpers so
CLI, Prefect flows, and agentic orchestrations consume the same configuration objects.

### Persist signals and automate daily digests

Intent collectors now use a persistent cache with timestamps and provenance. Configure the
storage block to control where collectors store their JSON payloads and how long entries
remain eligible for reuse:

```toml
[pipeline.intent.storage]
path = "./data/intent-signals.json"
max_age_hours = 12
```

When the pipeline runs with `intent_webhooks` or a `crm_endpoint`, the CLI automatically
dispatches the resulting digest and daily list after the quality report finishes logging.
Hotpass includes helper functions that:

- POST the daily digest and optional daily list to each webhook URL declared in
  `intent_webhooks`.
- Send the same daily list to your CRM endpoint with an optional bearer token from
  `crm_token`.

Enable daily list exports by setting `daily_list_path` and `daily_list_size`. The
pipeline writes the CSV (or Parquet when using a `.parquet` suffix) and returns the
dataframe so automation hooks can send it downstream.

```bash
uv run hotpass \
  --input-dir ./data \
  --output-path ./dist/refined.xlsx \
  --intent-signal-store ./data/intent-signals.json \
  --daily-list-path ./dist/daily-list.csv \
  --daily-list-size 25 \
  --intent-webhook https://hooks.example/hotpass \
  --crm-endpoint https://crm.example/api/leads \
--crm-token ${CRM_TOKEN}
```

Hotpass only sends automation payloads when there is data to deliver. If the digest or
daily list is empty the CLI skips the request but retains log entries so you can audit
when downstream systems were contacted.

#### Harden webhook and CRM delivery

Automation hooks now run through a shared HTTP client that exposes retry, backoff, and
circuit-breaking policies. Each delivery emits structured events (`automation.webhook.*`,
`automation.crm.*`) and updates the OpenTelemetry counter/histogram pair under
`hotpass.automation.*` so operators can track success/failure rates.

- Use CLI flags to tune the policies per run:
  - `--automation-http-timeout`, `--automation-http-retries`,
    `--automation-http-backoff`, and `--automation-http-backoff-max` govern retry
    behaviour.
  - `--automation-http-circuit-threshold` and
    `--automation-http-circuit-reset` control when the circuit opens and how long it
    waits before retrying.
  - `--automation-http-idempotency-header` overrides the default `Idempotency-Key`
    header when downstream systems expect a different name.
  - `--automation-http-dead-letter` paired with `--automation-http-dead-letter-enabled`
    appends failed deliveries to a newline-delimited JSON file for replay.

- Equivalent environment variables ensure Prefect deployments and automated agents pick
  up the same configuration:

| Variable                                      | Meaning                                            |
| --------------------------------------------- | -------------------------------------------------- |
| `HOTPASS_AUTOMATION_HTTP_TIMEOUT`             | Delivery timeout in seconds.                       |
| `HOTPASS_AUTOMATION_HTTP_RETRIES`             | Maximum retry attempts.                            |
| `HOTPASS_AUTOMATION_HTTP_BACKOFF`             | Exponential backoff factor.                        |
| `HOTPASS_AUTOMATION_HTTP_BACKOFF_MAX`         | Maximum backoff interval in seconds.               |
| `HOTPASS_AUTOMATION_HTTP_CIRCUIT_THRESHOLD`   | Consecutive failures before the circuit opens.     |
| `HOTPASS_AUTOMATION_HTTP_CIRCUIT_RESET`       | Seconds to wait before half-opening the circuit.   |
| `HOTPASS_AUTOMATION_HTTP_IDEMPOTENCY_HEADER`  | Override the generated idempotency header.         |
| `HOTPASS_AUTOMATION_HTTP_DEAD_LETTER`         | Destination path for the NDJSON dead-letter queue. |
| `HOTPASS_AUTOMATION_HTTP_DEAD_LETTER_ENABLED` | `true`/`false` toggle for dead-letter persistence. |

Delivery reports return the status, idempotency key, attempt count, and latency for each
webhook or CRM call. These details are mirrored in the structured logger so on-call staff
can triage failures quickly and correlate with the generated dead-letter artefacts.

### Configure registry enrichment connectors

Registry lookups now ship with native adapters for the CIPC and SACAA registries. Configure
the adapters with environment variables so both the CLI and Prefect flows pick up the
correct credentials and rate limits:

```text
HOTPASS_CIPC_BASE_URL=https://api.cipc.gov.za/v1/companies
HOTPASS_CIPC_API_KEY=...
HOTPASS_CIPC_API_KEY_HEADER=Ocp-Apim-Subscription-Key
HOTPASS_CIPC_THROTTLE_SECONDS=2
HOTPASS_CIPC_TIMEOUT_SECONDS=15
HOTPASS_CIPC_SEARCH_PARAM=search

HOTPASS_SACAA_BASE_URL=https://api.sacaa.co.za/operators
HOTPASS_SACAA_API_KEY=...
HOTPASS_SACAA_API_KEY_HEADER=X-API-Key
HOTPASS_SACAA_THROTTLE_SECONDS=1
HOTPASS_SACAA_TIMEOUT_SECONDS=15
HOTPASS_SACAA_QUERY_PARAM=query
```

Each lookup is cached via `CacheManager`, so repeated calls within the TTL reuse the
normalised payload instead of hammering upstream APIs. You can share a cache across
providers:

```python
from hotpass.enrichment import CacheManager, enrich_from_registry

cache = CacheManager(db_path="./data/.cache/registries.db", ttl_hours=24)
result = enrich_from_registry("Aero Tech", registry_type="cipc", cache=cache)

if result["success"]:
    print(result["payload"]["registration_number"])
else:
    print("Registry lookup skipped:", result["errors"])
```

Soft failures (for example unknown entities) return `success: false` with structured
`errors` so the pipeline can fall back to internal data. Hard failures such as missing
credentials or transport errors raise `RegistryLookupError`; wrap calls in a `try` block
when you need bespoke recovery logic. Refer to `policy/acquisition/providers.json` for
per-provider collection notes and acceptable use constraints.

### Enable asynchronous website enrichment

When you enrich records with external website content, enable the enhanced pipeline with
concurrency to speed up network-bound fetches:

```python
from pathlib import Path

from hotpass.pipeline import (
    PipelineConfig,
    PipelineExecutionConfig,
    PipelineOrchestrator,
    default_feature_bundle,
)
from hotpass.pipeline.features import EnhancedPipelineConfig

base_config = PipelineConfig(
    input_dir=Path("data"),
    output_path=Path("dist/refined.xlsx"),
    enable_formatting=True,
)

enhanced = EnhancedPipelineConfig(
    enable_enrichment=True,
    enrich_websites=True,
    enrichment_concurrency=8,
)

execution = PipelineExecutionConfig(
    base_config=base_config,
    enhanced_config=enhanced,
    features=default_feature_bundle(),
)

result = PipelineOrchestrator().run(execution)
```

Set `enrichment_concurrency` to the number of parallel fetches you are comfortable running
against upstream sites. The default (`8`) uses asynchronous workers to download multiple
pages at once while respecting cache guardrails. Lower the value if an API enforces strict
rate limits. Passing a custom `features` sequence lets you mix built-in strategies (entity
resolution, geospatial, enrichment, compliance) with your own feature hooks while
retaining deterministic orchestration and telemetry.

### Orchestrate multi-source acquisition

Hotpass 2.0 introduces agent-based acquisition that can blend API, registry, and respectful crawl
results before the spreadsheet loaders run. Define the plan under the new `[pipeline.acquisition]`
section and the schema validator will materialise an `AcquisitionPlan` for you:

```toml
[pipeline.acquisition]
enabled = true
deduplicate = true

[[pipeline.acquisition.agents]]
name = "prospector"
search_terms = ["hotpass"]

[[pipeline.acquisition.agents.targets]]
identifier = "hotpass"
domain = "hotpass.example"

[[pipeline.acquisition.agents.providers]]
name = "linkedin"
[pipeline.acquisition.agents.providers.options.profiles.hotpass]
organization = "Hotpass Aero"
profile_url = "https://linkedin.com/company/hotpass"

[[pipeline.acquisition.agents.providers]]
name = "clearbit"
[pipeline.acquisition.agents.providers.options.companies."hotpass.example"]
name = "Hotpass Aero"
```

At runtime the pipeline invokes each agent before reading the Excel workbooks. The resulting
records enter the existing normalization, validation, and deduplication flow with provenance
metadata intact. Supply credentials (for example API keys) under `[pipeline.acquisition.credentials]`
and they will be passed to each provider adapter.

### Monitor contact verification confidence

Every run now annotates contact rosters with MX- and carrier-aware verification signals. The
`Company_Contacts` sheet receives additional expectation coverage to ensure the derived columns
(`EmailValidationStatus`, `EmailValidationConfidence`, `PhoneValidationStatus`,
`PhoneValidationConfidence`) stay within governed ranges. Downstream SSOT exports emit
rollups for these checks:

- `contact_email_confidence_avg` / `contact_phone_confidence_avg` — average deliverability
  confidence for the organisation’s roster.
- `contact_verification_score_avg` — blended SMTP/MX + carrier signal expressed on a 0–1 scale.
- `contact_lead_score_avg` — mean ML lead score feeding preference rankings.

Great Expectations and the Pandera schema both enforce 0–1 bounds for these metrics while
validating that status columns only contain the governed enum (`deliverable`, `risky`,
`undeliverable`, `unknown`). Failures surface in the pipeline quality report and will block SSOT
publication until addressed.

Each acquisition run emits OpenTelemetry spans (`acquisition.plan`, `acquisition.agent`,
`acquisition.provider`) and updates the `hotpass.acquisition.*` metrics. Inspect these spans in
the console exporter or your OTLP backend to confirm provider coverage, record counts, and runtime.
Before enabling a provider, confirm it appears in [`policy/acquisition/providers.json`](../../policy/acquisition/providers.json)
and that the collection basis matches your legal review. Custom providers should be registered via
`ProviderPolicy.ensure_allowed` to enforce compliance.

### Collect intent signals and daily digests

The canonical schema also supports an intent pipeline that blends news, hiring, and traffic signals
before the contact aggregation stage. Configure collectors and targets under `[pipeline.intent]`:

```toml
[pipeline]
intent_digest_path = "dist/intent-digest.parquet"

[pipeline.intent]
enabled = true
deduplicate = true

[[pipeline.intent.collectors]]
name = "news"
weight = 1.0

[[pipeline.intent.collectors.options.events."aero-school"]]
headline = "Aero expands fleet"
intent = 0.9
timestamp = "2025-10-25T08:00:00Z"
url = "https://example.test/aero/expands"

[[pipeline.intent.collectors.options.events."heli-ops"]]
headline = "Heli Ops launches medivac division"
intent = 0.7
timestamp = "2025-10-24T11:00:00Z"

[[pipeline.intent.targets]]
identifier = "Aero School"
slug = "aero-school"

[[pipeline.intent.targets]]
identifier = "Heli Ops"
slug = "heli-ops"

[pipeline.intent.credentials]
token = "${HOTPASS_INTENT_TOKEN}"
```

At runtime the plan is materialised into `IntentPlan` objects which feed the new intent scoring stage.
The resulting columns (`intent_signal_score`, `intent_signal_types`, and `intent_top_insights`) appear
in the SSOT export and can be blended with lead scoring. Use the new CLI flag to override the export
location when running ad-hoc analyses:

```bash
uv run hotpass run --intent-digest-path dist/daily-intent.csv --input-dir data --output-path dist/refined.xlsx
```

The CLI will log where the digest was written and how many prospects were ranked. All digest exports
respect the suffix you provide (`.parquet`, `.csv`, or `.json`) and inherit the same masking rules as
the structured logs. In JSON log mode the CLI emits an `intent.digest` event with the output path and
record count so downstream automation can react without parsing console output.

## 3. Extend column mapping

Add business-specific column names directly in the profile or register them at runtime:

```python
from hotpass.column_mapping import ColumnMapper

mapper = ColumnMapper(profile.column_synonyms)
result = mapper.map_columns(["facility", "mail", "phone_number"])
print(result.mapped)
```

Use the `profile.column_synonyms` dictionary to audit which columns are automatically detected and which need manual mapping.

## 4. Configure contact management

Hotpass can consolidate multiple contacts per organisation. Set source priority and deduplication behaviour in your profile or config:

```yaml
contacts:
  prefer_roles:
    - Primary Contact
    - Account Manager
  fallback_to_first_seen: true
```

```python
from hotpass.contacts import consolidate_contacts_from_rows
consolidated = consolidate_contacts_from_rows(
    organization_name="Acme Corp",
    rows=df[df["organization_name"] == "Acme Corp"],
    source_priority={"CRM": 3, "Spreadsheet": 1},
)
primary = consolidated.get_primary_contact()
```

## 5. Enable contact verification

Hotpass now validates primary email and phone contacts during aggregation. The default
validators perform MX lookups for well-known domains and use `phonenumbers` to parse and
classify phone numbers. Verification results are exposed via new SSOT columns:

| Column                             | Description                                                                           |
| ---------------------------------- | ------------------------------------------------------------------------------------- |
| `contact_primary_email_confidence` | Float confidence score returned by the email validator.                               |
| `contact_primary_email_status`     | Enum (`deliverable`, `risky`, `undeliverable`, `unknown`).                            |
| `contact_primary_phone_confidence` | Confidence score produced by the phone validator.                                     |
| `contact_primary_phone_status`     | Enum mirroring the email status values.                                               |
| `contact_primary_lead_score`       | Logistic-scaled lead score combining completeness, verification, and source priority. |
| `contact_validation_flags`         | Semicolon-delimited list of warnings (for example `email:risky`).                     |

To customise behaviour instantiate `ContactValidationService` with bespoke provider logic:

```python
from hotpass.enrichment.validators import ContactValidationService, EmailValidator

service = ContactValidationService(
    email_validator=EmailValidator(dns_lookup=my_dns_lookup),
)
contacts = consolidate_contacts_from_rows(
    organization_name="Aero Co",
    rows=frame,
    validator=service,
)
```

At pipeline level the validators use `PipelineConfig.country_code` to infer phone regions and
cache results to minimise repeated lookups. If you disable validation (for example in offline
fixtures), set `contact_primary_email_confidence` and related fields manually before schema
validation.

## 6. Validate the configuration

Run tests before promoting changes:

```bash
uv run pytest tests/test_config.py tests/test_contacts.py
```

A green test suite confirms your configuration behaves as expected across the supported use cases.

## 7. Enforce consent validation

The enhanced pipeline now enforces consent for POPIA-regulated fields. When you enable compliance with `EnhancedPipelineConfig(enable_compliance=True)`, the pipeline checks that every record requiring consent has a granted status.

1. **Capture consent sources** — Extend your upstream data to include a `consent_status` column (`granted`, `pending`, `revoked`, etc.).
2. **Map overrides** — Provide overrides per organisation when you orchestrate the pipeline:

   ```python
   from hotpass.pipeline_enhanced import EnhancedPipelineConfig

   config = EnhancedPipelineConfig(
       enable_compliance=True,
       consent_overrides={
           "test-org-1": "granted",
           "Example Flight School": "granted",
       },
   )
   ```

   Overrides can use the organisation slug (`organization_slug`) or the display name; they update the `consent_status` column before validation runs.

3. **Review the compliance report** — `PipelineResult.compliance_report` includes a summary of consent statuses and any violations detected. A `ConsentValidationError` stops the run if any required record lacks a granted status.

Consent statuses are case-insensitive. The defaults treat `granted`/`approved` as valid, `pending`/`unknown` as awaiting action, and `revoked`/`denied` as blockers. Adjust `consent_granted_statuses`, `consent_pending_statuses`, or `consent_denied_statuses` via `POPIAPolicy` if your organisation uses different terminology.
