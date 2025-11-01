---
title: Reference — command-line interface
summary: Detailed options for the unified `hotpass` CLI entry point and its subcommands.
last_updated: 2025-10-31
---

Hotpass now ships a single console script: `hotpass`. Subcommands map to the core
pipeline as well as orchestrator, entity resolution, dashboard, and deployment workflows.
Legacy `hotpass-enhanced` invocations continue to work but simply delegate to the unified
CLI after printing a deprecation warning.

> ℹ️ Need the MCP equivalents? See [Reference — MCP tools](mcp-tools.md) for the tool names that mirror each CLI verb.

## Quick start

```bash
uv run hotpass run --input-dir ./data --output-path ./dist/refined.xlsx --archive
```

Scaffold a dedicated workspace and validate prerequisites before your first run:

```bash
uv run hotpass init --path ./workspace
uv run hotpass doctor --config ./config/pipeline.quickstart.toml
```

Shared flags such as `--profile`, `--config`, `--log-format`, and `--sensitive-field`
may be supplied before the subcommand or repeated per subcommand thanks to the parser's
parent structure. Profiles defined in TOML or YAML load via `--profile` and can merge
additional configuration files and feature toggles.

## Core commands

The unified CLI exposes five primary verbs that map to the workflows described in
`UPGRADE.md`:

- `uv run hotpass overview` — list available commands, profiles, and shortcuts for agents.
- `uv run hotpass refine` — execute the deterministic data refinement pipeline.
- `uv run hotpass enrich` — enrich refined data with deterministic and optional research sources.
- `uv run hotpass qa` — run quality gates (`fitness`, `data-quality`, `docs`, `contracts`, `cli`, `ta`).
- `uv run hotpass contracts` — emit contract bundles (YAML/JSON) for downstream systems.
- `uv run hotpass setup` — run the guided staging wizard (dependencies, tunnels, contexts, env files).
- `uv run hotpass net` — manage SSH/SSM tunnels to Prefect and Marquez.
- `uv run hotpass aws` — resolve the current AWS identity and verify EKS connectivity.
- `uv run hotpass ctx` — bootstrap Prefect profiles and Kubernetes contexts.
- `uv run hotpass env` — generate `.env.<target>` files using recorded tunnel/context metadata.
- `uv run hotpass explain-provenance --dataset ./dist/enriched.xlsx --row-id 0 --json` — surface provenance metadata for a specific row (prints a table by default or JSON with `--json`).
- `uv run hotpass plan research --dataset ./dist/refined.xlsx --row-id 0 --allow-network` — generate an adaptive research plan that combines local snapshots, deterministic enrichment, optional network fetchers, and crawl/backfill recommendations.
- `uv run hotpass crawl "https://example.test" --allow-network` — trigger the crawler-only pathway (uses the same orchestrator engine but skips deterministic enrichment).

> 🔐 **QG-1 — CLI Integrity:** Automated checks expect `hotpass overview` and
> `hotpass --help` to advertise the automation verbs (`setup`, `net`, `aws`,
> `ctx`, `env`) alongside the core pipeline commands above. If a new verb is
> added, update the quality gate lists and this reference page together.

The sections below retain backward-compatible documentation for legacy verbs until the
Sprint 5 docs refresh is published.

## Infrastructure automation

The CLI also includes commands to streamline operator workflows such as tunnel setup,
AWS/EKS verification, Prefect/kubecontext bootstrap, and environment file generation.

### `setup`

Run a guided wizard that stitches together dependency synchronisation, tunnel creation, AWS
verification, context bootstrap, and environment file generation. Designed for staging operators
who want a single “don’t make me think” entry point.

```bash
uv run hotpass setup --preset staging --host bastion.example.com --dry-run
uv run hotpass setup --preset staging --host bastion.example.com --execute --skip-arc
```

| Option                                         | Description                                                             |
| ---------------------------------------------- | ----------------------------------------------------------------------- |
| `--preset {staging\|local}`                    | Controls default extras, namespaces, and environment targets.           |
| `--extras EXTRA`                               | Override preset extras for `ops/uv_sync_extras.sh` (repeatable).        |
| `--skip-*`                                     | Skip individual stages (`deps`, `tunnels`, `aws`, `ctx`, `env`, `arc`). |
| `--host HOST`                                  | Bastion host or SSM target for the tunnel stage.                        |
| `--aws-profile NAME`                           | AWS profile used when invoking `hotpass aws`.                           |
| `--eks-cluster NAME`                           | Cluster name forwarded to `hotpass aws`/`hotpass ctx init`.             |
| `--prefect-profile NAME`                       | Prefect profile configured during context bootstrap.                    |
| `--env-target NAME`                            | Target passed to `hotpass env --target`.                                |
| `--allow-network`                              | Enable network enrichment flags in generated environment files.         |
| `--arc-owner/--arc-repository/--arc-scale-set` | Include ARC lifecycle verification when details are provided.           |
| `--dry-run`                                    | Render the plan without executing commands.                             |
| `--execute`                                    | Run the generated plan immediately (skip confirmation prompts).         |

Successful executions record the plan under `.hotpass/setup.json`.

### `net`

Manage SSH or AWS SSM tunnels to staging infrastructure.

```bash
uv run hotpass net up --host bastion.example.com --detach
uv run hotpass net status
uv run hotpass net down --label bastion-session
```

| Option                     | Description                                                                       |
| -------------------------- | --------------------------------------------------------------------------------- |
| `--via {ssh-bastion\|ssm}` | Select port-forwarding mechanism (default: `ssh-bastion`).                        |
| `--host HOST`              | Bastion hostname or SSM target instance ID.                                       |
| `--prefect-port INTEGER`   | Local port for Prefect (auto-resolves conflicts with `--auto-port`).              |
| `--marquez-port INTEGER`   | Local port for Marquez (skip with `--no-marquez`).                                |
| `--detach`                 | Launch the tunnel in the background and record the PID under `.hotpass/net.json`. |
| `--dry-run`                | Print the tunnel command without executing it.                                    |

State is persisted to `.hotpass/net.json`; `net status` prints active sessions and their
local ports.

### `aws`

Resolve the active AWS identity and optionally describe/verify EKS access.

```bash
uv run hotpass aws --profile staging --region eu-west-1
uv run hotpass aws --eks-cluster hotpass-staging --verify-kubeconfig
```

| Option                  | Description                                                   |
| ----------------------- | ------------------------------------------------------------- |
| `--profile NAME`        | AWS CLI profile override.                                     |
| `--region NAME`         | AWS region override.                                          |
| `--eks-cluster NAME`    | Describe the cluster and (optionally) update kubeconfig.      |
| `--verify-kubeconfig`   | Run `aws eks update-kubeconfig` after describing the cluster. |
| `--output {text\|json}` | Render output as Rich table or JSON (default: text).          |
| `--dry-run`             | Display AWS commands without executing them.                  |

On success, the summary is saved to `.hotpass/aws.json`.

### `ctx`

Bootstrap Prefect profiles and Kubernetes contexts.

```bash
uv run hotpass ctx init --prefect-profile hotpass-staging --eks-cluster hotpass-staging
uv run hotpass ctx list
```

| Option                   | Description                                                                      |
| ------------------------ | -------------------------------------------------------------------------------- |
| `--prefect-profile NAME` | Prefect profile to create or update.                                             |
| `--prefect-url URL`      | Prefect API URL (defaults to tunnel-derived URL or `http://127.0.0.1:4200/api`). |
| `--eks-cluster NAME`     | EKS cluster to configure via `aws eks update-kubeconfig`.                        |
| `--kube-context NAME`    | Context alias for kubeconfig (defaults to cluster name).                         |
| `--dry-run`              | Print commands without executing them.                                           |

Context history is recorded under `.hotpass/contexts.json`.

### `env`

Generate `.env.<environment>` files aligned with the current tunnels and contexts.

```bash
uv run hotpass env --target staging
uv run hotpass env --target staging --allow-network --force
```

| Option                  | Description                                                              |
| ----------------------- | ------------------------------------------------------------------------ |
| `--target NAME`         | Environment name (determines output filename).                           |
| `--prefect-url URL`     | Override Prefect API URL.                                                |
| `--openlineage-url URL` | Override OpenLineage API URL.                                            |
| `--allow-network`       | Set `FEATURE_ENABLE_REMOTE_RESEARCH`/`ALLOW_NETWORK_RESEARCH` to `true`. |
| `--dry-run`             | Print the generated file without writing it.                             |

When tunnels exist, ports recorded in `.hotpass/net.json` are reused automatically.

### `arc`

Wrapper around ARC lifecycle verification with optional artifact storage.

```bash
uv run hotpass arc --owner ExampleOrg --repository Hotpass --scale-set hotpass-arc
uv run hotpass arc --owner ExampleOrg --repository Hotpass --scale-set hotpass-arc --store-summary
```

| Option                                   | Description                                                    |
| ---------------------------------------- | -------------------------------------------------------------- |
| `--owner`, `--repository`, `--scale-set` | Identify the ARC deployment to verify.                         |
| `--verify-oidc`                          | Additionally verify AWS identity using OIDC.                   |
| `--snapshot PATH`                        | Replay a recorded lifecycle snapshot for offline verification. |
| `--store-summary`                        | Persist results under `.hotpass/arc/<timestamp>/`.             |
| `--status-path PATH`                     | Write the JSON result to disk for the web UI health probes.    |
| `--dry-run`                              | Print the underlying command without executing it.             |

### `distro`

Collect documentation into a single directory for distribution bundles.

```bash
uv run hotpass distro docs --output dist/docs
```

Copies `README.md`, `AGENTS.md`, and `docs/reference/cli.md` into the specified directory
(defaults to `dist/docs`). Use `--dry-run` to preview or `--force` to overwrite.

## Canonical configuration schema

The CLI now materialises every run from the canonical `HotpassConfig` schema defined in
[`apps/data-platform/hotpass/config_schema.py`](../../apps/data-platform/hotpass/config_schema.py). Profiles, config files,
and CLI flags are normalised into that schema before any pipeline code executes, ensuring
consistent behaviour across CLI, Prefect flows, and agent-triggered runs.

```toml
# config/pipeline.canonical.toml
[profile]
name = "aviation"
display_name = "Aviation & Flight Training"

[pipeline]
input_dir = "./data"
output_path = "./dist/refined.xlsx"
archive = true
dist_dir = "./dist"
log_format = "json"

[features]
compliance = true
geospatial = true

[governance]
intent = ["Process POPIA regulated dataset"]
data_owner = "Data Governance"
classification = "sensitive_pii"

[compliance]
detect_pii = true

[data_contract]
dataset = "aviation_ssot"
expectation_suite = "aviation"
schema_descriptor = "ssot.schema.json"
```

Merge the file with `--config config/pipeline.canonical.toml` or place it under a CLI profile.
Legacy configuration payloads can be upgraded via the `ConfigDoctor` helper:

```python
from hotpass.config_doctor import ConfigDoctor

doctor = ConfigDoctor()
config, notices = doctor.upgrade_payload(legacy_payload)
doctor.diagnose()
doctor.autofix()
```

The doctor flags missing governance intent or data owners and injects safe defaults such as
`Data Governance` when autofixable.

## Shared options

| Option                                                  | Description                                                                                                |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `--profile NAME`                                        | Named profile (TOML/YAML) to apply before CLI flags.                                                       |
| `--profile-search-path PATH`                            | Additional directory to search when resolving named profiles. Repeat the flag to merge multiple locations. |
| `--config FILE`                                         | TOML or JSON configuration file merged before CLI flags. Repeat to layer multiple files.                   |
| `--log-format [rich \| json]`                           | Structured logging format. Rich enables interactive output and progress bars.                              |
| `--sensitive-field FIELD`                               | Field name to mask in structured logs. Repeat for multiple masks.                                          |
| `--interactive` / `--no-interactive`                    | Control inline prompts when rich logging is enabled.                                                       |
| `--qa-mode [default \| strict \| relaxed]`              | Apply guardrail presets (strict enables additional validation; relaxed disables audit prompts).            |
| `--observability` / `--no-observability`                | Toggle OpenTelemetry exporters regardless of profile defaults.                                             |
| `--telemetry-service-name TEXT`                         | Override the default service name reported to OpenTelemetry (default: `hotpass`).                          |
| `--telemetry-environment TEXT`                          | Set the `deployment.environment` resource attribute (default: `HOTPASS_ENVIRONMENT`).                      |
| `--telemetry-exporter NAME`                             | Append telemetry exporters (`console`, `noop`, `otlp`). Repeat to enable multiple exporters.               |
| `--telemetry-resource-attr KEY=VALUE`                   | Attach additional resource attributes. Repeat per key/value pair.                                          |
| `--telemetry-otlp-endpoint URL`                         | Configure the OTLP gRPC endpoint for trace export (for example `grpc://collector:4317`).                   |
| `--telemetry-otlp-metrics-endpoint URL`                 | Override the OTLP metrics endpoint when different from the trace endpoint.                                 |
| `--telemetry-otlp-header KEY=VALUE`                     | Supply OTLP headers such as authentication tokens. Repeat per header.                                      |
| `--telemetry-otlp-insecure` / `--telemetry-otlp-secure` | Toggle TLS validation for OTLP exporters (default: secure).                                                |
| `--telemetry-otlp-timeout FLOAT`                        | Set the OTLP exporter timeout in seconds.                                                                  |

## Subcommands

### `run`

Validate, normalise, and publish the refined workbook.

```bash
uv run hotpass run [OPTIONS]
```

| Option                                                                       | Description                                                                           |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `--input-dir PATH`                                                           | Directory containing raw spreadsheets (default: `./data`).                            |
| `--output-path PATH`                                                         | Destination path for the refined workbook (default: `<input-dir>/refined_data.xlsx`). |
| `--expectation-suite NAME`                                                   | Great Expectations suite to execute (default: `default`).                             |
| `--country-code CODE`                                                        | ISO country code applied when normalising phone numbers (default: `ZA`).              |
| `--archive` / `--no-archive`                                                 | Enable or disable creation of a timestamped `.zip` archive.                           |
| `--dist-dir PATH`                                                            | Directory used for archive output when `--archive` is enabled (default: `./dist`).    |
| `--report-path PATH`                                                         | Optional path for the quality report (Markdown or HTML).                              |
| `--report-format [markdown \| html]`                                         | Explicit report format override. When omitted the format is inferred from the path.   |
| `--party-store-path PATH`                                                    | Path to serialise the canonical Party/Role/Alias/Contact store.                       |
| `--excel-chunk-size INTEGER`                                                 | Chunk size for streaming Excel reads; must be greater than zero when supplied.        |
| `--excel-engine TEXT`                                                        | Explicit pandas Excel engine (for example `openpyxl`).                                |
| `--excel-stage-dir PATH`                                                     | Directory for staging chunked Excel reads to parquet for reuse.                       |
| `--automation-http-timeout FLOAT`                                            | Timeout in seconds for webhook and CRM deliveries.                                    |
| `--automation-http-retries INTEGER`                                          | Maximum retry attempts for automation deliveries.                                     |
| `--automation-http-backoff FLOAT`                                            | Exponential backoff factor applied between automation retries.                        |
| `--automation-http-backoff-max FLOAT`                                        | Upper bound for the backoff interval (seconds).                                       |
| `--automation-http-circuit-threshold INTEGER`                                | Consecutive failures that open the automation circuit breaker.                        |
| `--automation-http-circuit-reset FLOAT`                                      | Seconds to wait before half-opening the automation circuit.                           |
| `--automation-http-idempotency-header TEXT`                                  | Override the `Idempotency-Key` header when generating idempotency keys.               |
| `--automation-http-dead-letter PATH`                                         | Append failed automation payloads to the given NDJSON file.                           |
| `--automation-http-dead-letter-enabled` / `--no-automation-http-dead-letter` | Toggle dead-letter persistence for automation failures.                               |

### `orchestrate`

Execute the pipeline under Prefect with optional enhanced features.

```bash
uv run hotpass orchestrate [OPTIONS]
```

| Option                                                       | Description                                                                   |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| `--industry-profile NAME`                                    | Prefect profile used when loading orchestrator presets (default: `aviation`). |
| `--enable-all`                                               | Enable all enhanced features in one flag.                                     |
| `--enable-entity-resolution` / `--disable-entity-resolution` | Control probabilistic entity resolution.                                      |
| `--enable-geospatial` / `--disable-geospatial`               | Control geospatial enrichment (geocoding).                                    |
| `--enable-enrichment` / `--disable-enrichment`               | Control web enrichment workflows.                                             |
| `--enable-compliance` / `--disable-compliance`               | Control compliance tracking and PII detection.                                |
| `--enable-observability` / `--disable-observability`         | Control observability exporters during orchestrated runs.                     |
| `--linkage-match-threshold FLOAT`                            | Probability considered an automatic match (default: `0.9`).                   |
| `--linkage-review-threshold FLOAT`                           | Probability routed to human review (default: `0.7`).                          |
| `--linkage-output-dir PATH`                                  | Directory to persist linkage artefacts.                                       |
| `--linkage-use-splink`                                       | Force Splink for probabilistic linkage even when profiles disable it.         |
| `--label-studio-url URL`                                     | Label Studio base URL for review queues.                                      |
| `--label-studio-token TOKEN`                                 | Label Studio API token.                                                       |
| `--label-studio-project INTEGER`                             | Label Studio project identifier.                                              |

Profiles enabling enrichment or compliance must declare intent statements (`intent = [...]`) to
enforce guardrails such as consent capture and audit logging.

### `explain-provenance`

Inspect provenance metadata for a specific row in an enriched workbook.

```bash
uv run hotpass explain-provenance \
  --dataset ./dist/enriched.xlsx \
  --row-id 0 \
  --json
```

| Option           | Description                                                                                              |
| ---------------- | -------------------------------------------------------------------------------------------------------- |
| `--dataset PATH` | Required path to the enriched dataset (Excel `.xlsx/.xlsm/.xls` or `.csv`).                              |
| `--row-id TEXT`  | Row index (0-based) or identifier from the dataset’s `id` column.                                        |
| `--json`         | Emit provenance details as JSON rather than a Rich table.                                                |
| `--output PATH`  | Persist the JSON payload to the provided path (directories are created automatically; implies `--json`). |

The command surfaces the standard provenance fields (`provenance_source`, `provenance_timestamp`,
`provenance_confidence`, `provenance_strategy`, `provenance_network_status`) alongside the
associated `organization_name`. When no provenance columns are present the command prints a warning
and exits with status `2` so pipeline owners can treat it as a soft failure.

### `resolve`

Deduplicate existing datasets using rule-based or probabilistic linkage.

```bash
uv run hotpass resolve --input-file data/raw.xlsx --output-file data/deduplicated.xlsx
```

| Option                             | Description                                                                                      |
| ---------------------------------- | ------------------------------------------------------------------------------------------------ |
| `--input-file PATH`                | Source CSV or Excel file with potential duplicates.                                              |
| `--output-file PATH`               | Destination path for deduplicated results.                                                       |
| `--threshold FLOAT`                | Baseline match probability threshold (default: `0.75`).                                          |
| `--use-splink` / `--no-use-splink` | Toggle Splink for probabilistic matching. Profiles enabling entity resolution default to `True`. |
| `--match-threshold FLOAT`          | Threshold treated as an automatic match (default: `0.9`).                                        |
| `--review-threshold FLOAT`         | Threshold that routes pairs to human review (default: `0.7`).                                    |
| `--label-studio-url URL`           | Label Studio base URL for review queues.                                                         |
| `--label-studio-token TOKEN`       | Label Studio API token.                                                                          |
| `--label-studio-project INTEGER`   | Label Studio project identifier.                                                                 |
| `--log-format [rich \| json]`      | Override profile defaults for structured logging (falls back to profile or `rich`).              |

`resolve` inherits the shared `--sensitive-field` flag. Profiles may supply default masks; repeat the flag to extend masks in runtime-only investigations.

### `plan research`

Generate an adaptive research plan that combines deterministic enrichment, network enrichment (when permitted), and crawl/backfill guidance.

```bash
uv run hotpass plan research \
  --dataset ./dist/refined.xlsx \
  --row-id 0 \
  --url https://example.test \
  --allow-network \
  --json \
  --output dist/research/plan.json
```

| Option            | Description                                                                                                                          |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `--dataset PATH`  | Refined workbook or directory to load before planning.                                                                               |
| `--row-id TEXT`   | Row identifier or zero-based index to focus the plan (optional when using entity slug/entity name filters).                          |
| `--entity TEXT`   | Friendly name to locate the target row when `--row-id` is not supplied.                                                              |
| `--url URL`       | Append target URLs for immediate crawl consideration (repeatable).                                                                   |
| `--allow-network` | Opt into research providers that require network access (enforce via `FEATURE_ENABLE_REMOTE_RESEARCH` and `ALLOW_NETWORK_RESEARCH`). |
| `--json`          | Emit the plan payload as JSON.                                                                                                       |
| `--output PATH`   | Persist the JSON plan to disk (directories are created automatically).                                                               |

Plans honour environment toggles and profile settings. When network access is disabled the orchestrator records skipped steps so reviewers can track pending research work.

### `crawl`

Execute only the crawling component of the research pipeline.

```bash
uv run hotpass crawl "https://example.test" --allow-network
```

| Option            | Description                                                                                                 |
| ----------------- | ----------------------------------------------------------------------------------------------------------- |
| `QUERY_OR_URL`    | Either a URL to crawl or a free-text query for provider search adapters.                                    |
| `--allow-network` | Enable network calls; otherwise the command validates configuration and exits without contacting providers. |

Crawler runs write JSON artefacts to `.hotpass/research_runs/<slug>/` and respect profile-defined throttling (`research_rate_limit`).

### `deploy`

Create or update Prefect deployments defined in the repository manifests.

```bash
uv run hotpass deploy --flow refinement
```

| Option               | Description                                                                                    |
| -------------------- | ---------------------------------------------------------------------------------------------- |
| `--flow TEXT`        | Deployment manifest identifier (repeat to register multiple manifests; default registers all). |
| `--manifest-dir DIR` | Directory containing manifest files (default: `prefect/`).                                     |
| `--build-image`      | Build the deployment image before registration.                                                |
| `--push-image`       | Push the built image to the configured registry.                                               |
| `--name TEXT`        | Override the Prefect deployment name for the selected manifests.                               |
| `--schedule TEXT`    | Apply a cron schedule in UTC. Use `none`/`off` to disable scheduling.                          |
| `--work-pool TEXT`   | Target Prefect work pool name when registering deployments.                                    |

### `dashboard`

Launch the Streamlit monitoring dashboard. Install the `dashboards` extra before using this
subcommand.

```bash
uv run hotpass dashboard --host localhost --port 8501
```

| Option           | Description                                                   |
| ---------------- | ------------------------------------------------------------- |
| `--host HOST`    | Bind address for the dashboard server (default: `localhost`). |
| `--port INTEGER` | Port for the Streamlit dashboard (default: `8501`).           |

### `doctor`

Run configuration and environment diagnostics. The command honours shared options such as
`--config` and `--profile` before running the checks.

```bash
uv run hotpass doctor --config ./config/pipeline.quickstart.toml --autofix
```

| Option      | Description                                                        |
| ----------- | ------------------------------------------------------------------ |
| `--autofix` | Apply safe governance autofixes (for example default data owners). |

The doctor reports Python version compatibility, input/output directory readiness, and the
results of the underlying `ConfigDoctor` diagnostics. Exit code `1` indicates an error that
requires remediation, while warnings leave the exit code unchanged.

### `init`

Scaffold a workspace with sample configuration, profile, and Prefect deployment files.

```bash
uv run hotpass init --path ./workspace
```

| Option    | Description                                                       |
| --------- | ----------------------------------------------------------------- |
| `--path`  | Destination directory for the generated workspace (default: `.`). |
| `--force` | Overwrite files when the destination already contains artefacts.  |

The generated workspace includes `config/pipeline.quickstart.toml`, a matching profile,
and a Prefect deployment sample that executes the quickstart pipeline.

### Automation delivery environment variables

The CLI and Prefect flows read the following environment variables when CLI flags are not
provided. All values are optional.

| Variable                                      | Purpose                                                     |
| --------------------------------------------- | ----------------------------------------------------------- |
| `HOTPASS_AUTOMATION_HTTP_TIMEOUT`             | Override the automation timeout (seconds).                  |
| `HOTPASS_AUTOMATION_HTTP_RETRIES`             | Override the retry count.                                   |
| `HOTPASS_AUTOMATION_HTTP_BACKOFF`             | Override the backoff factor.                                |
| `HOTPASS_AUTOMATION_HTTP_BACKOFF_MAX`         | Override the maximum backoff interval (seconds).            |
| `HOTPASS_AUTOMATION_HTTP_CIRCUIT_THRESHOLD`   | Override the failure threshold before the circuit opens.    |
| `HOTPASS_AUTOMATION_HTTP_CIRCUIT_RESET`       | Override the circuit recovery window (seconds).             |
| `HOTPASS_AUTOMATION_HTTP_IDEMPOTENCY_HEADER`  | Override the idempotency header name.                       |
| `HOTPASS_AUTOMATION_HTTP_DEAD_LETTER`         | Write failed deliveries to the specified NDJSON file.       |
| `HOTPASS_AUTOMATION_HTTP_DEAD_LETTER_ENABLED` | Enable or disable dead-letter persistence (`true`/`false`). |

## Exit codes

| Code | Meaning                                                                         |
| ---- | ------------------------------------------------------------------------------- |
| `0`  | Success.                                                                        |
| `1`  | Unrecoverable failure (for example missing input files, orchestration failure). |
| `2`  | Validation failure when loading profiles or configuration.                      |

## See also

- [How-to guide — orchestrate and observe](../how-to-guides/orchestrate-and-observe.md)
- [How-to guide — configure pipeline](../how-to-guides/configure-pipeline.md)
- [Tutorial — enhanced pipeline](../tutorials/enhanced-pipeline.md)
