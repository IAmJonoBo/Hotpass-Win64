---
title: Reference — command-line interface
summary: Detailed options for the unified `hotpass` CLI entry point and its subcommands.
last_updated: 2025-11-03
---

# Command-line interface reference

You run every Hotpass workflow through the unified `hotpass` console script. The command
ships with the Python project and mirrors the verbs exposed through the MCP server. Legacy
`hotpass-enhanced` calls still work, but they delegate to the unified entry point after
printing a deprecation warning.

```text
$ uv run hotpass --help
usage: hotpass [-h]
               {overview,refine,enrich,explain-provenance,qa,contracts,imports,inventory,plan,crawl,setup,net,aws,ctx,env,arc,distro,run,backfill,doctor,orchestrate,resolve,dashboard,deploy,init,version}
               ...

Hotpass CLI

positional arguments:
  {overview,refine,enrich,explain-provenance,qa,contracts,imports,inventory,plan,crawl,setup,net,aws,ctx,env,arc,distro,run,backfill,doctor,orchestrate,resolve,dashboard,deploy,init,version}
    overview            Display available Hotpass commands and system status
    refine              Run the Hotpass refinement pipeline
    enrich              Enrich refined data with additional information
    explain-provenance  Inspect provenance metadata for a specific row
    qa                  Run quality assurance checks and validation
    contracts           Emit data contracts and schemas for a profile
    imports             Smart import utilities
    inventory           Inspect the asset inventory and implementation status
    plan                Plan adaptive research tasks and supporting workflows
    crawl               Execute a targeted crawl via the research orchestrator
    setup               Run guided wizards for dependency sync and staging bootstrap
    net                 Manage SSH/SSM tunnels to Hotpass environments
    aws                 Check AWS identity and EKS connectivity
    ctx                 Manage Prefect and Kubernetes contexts
    env                 Write Hotpass .env files
    arc                 Verify GitHub ARC runner scale sets
    distro              Create distribution-ready artefacts
    run                 Run the Hotpass refinement pipeline
    backfill            Replay archived inputs through the refinement pipeline
    doctor              Run configuration and environment diagnostics
    orchestrate         Run the pipeline with Prefect orchestration and optional enhanced features
    resolve             Run entity resolution on existing datasets
    dashboard           Launch the Hotpass Streamlit monitoring dashboard
    deploy              Deploy the Hotpass pipeline to Prefect
    init                Bootstrap a project workspace with sample configuration
    version             Manage dataset versions with DVC

options:
  -h, --help            show this help message and exit

Profiles may be defined as TOML or YAML files. Use --profile-search-path to locate custom profiles.
```

Example `overview` output (captured 2025-11-03):

```text
$ uv run hotpass overview

╭─────────────────────────────── About Hotpass ────────────────────────────────╮
│ Hotpass Data Refinement Platform                                             │
│ Version: 0.2.0                                                               │
│                                                                              │
│ Hotpass transforms messy spreadsheets into a governed single source of       │
│ truth.                                                                       │
╰──────────────────────────────────────────────────────────────────────────────╯

                           Available Hotpass Commands                           
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Command         ┃ Description                                                ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ overview        │ Display this overview of Hotpass commands and status       │
│ refine          │ Run the Hotpass refinement pipeline on input data          │
│ enrich          │ Enrich refined data with additional information            │
│ qa              │ Run quality assurance checks and validation                │
│ contracts       │ Emit data contracts and schemas for a profile              │
│ setup           │ Run the guided staging wizard (deps, tunnels, contexts,    │
│                 │ env)                                                       │
│ net             │ Manage SSH/SSM tunnels to staging services                 │
│ aws             │ Verify AWS credentials and optional EKS access             │
│ ctx             │ Bootstrap Prefect profiles and kube contexts               │
│ env             │ Generate .env files aligned with active tunnels            │
│ arc             │ Verify GitHub ARC runner scale sets                        │
│ distro          │ Bundle documentation assets under dist/docs                │
│ run             │ Run the Hotpass refinement pipeline (alias for refine)     │
│ backfill        │ Replay archived inputs through the pipeline                │
│ doctor          │ Run configuration and environment diagnostics              │
│ orchestrate     │ Run pipeline with Prefect orchestration                    │
│ resolve         │ Run entity resolution on existing datasets                 │
│ dashboard       │ Launch the Hotpass monitoring dashboard                    │
│ deploy          │ Deploy the Hotpass pipeline to Prefect                     │
│ init            │ Bootstrap a project workspace                              │
│ version         │ Manage dataset versions with DVC                           │
└─────────────────┴────────────────────────────────────────────────────────────┘
```

> ℹ️ Need the MCP equivalents? See [Reference — MCP tools](mcp-tools.md) for the tool names that mirror each CLI verb.

Bundled profiles live under `apps/data-platform/hotpass/profiles`. When you work from a generated workspace, add `--profile-search-path ../apps/data-platform/hotpass/profiles` (or copy the profile into `config/profiles`) so the CLI can resolve the name.

## Command structure

```{mermaid}
graph TD
    Root[hotpass]

    Root --> Core[Core Commands]
    Root --> Infra[Infrastructure]
    Root --> Utils[Utilities]

    Core --> Overview[overview]
    Core --> Refine[refine]
    Core --> Enrich[enrich]
    Core --> QA[qa]
    Core --> Contracts[contracts]

    Infra --> Setup[setup]
    Infra --> Net[net]
    Infra --> AWS[aws]
    Infra --> Ctx[ctx]
    Infra --> Env[env]
    Infra --> Arc[arc]

    Utils --> Distro[distro]
    Utils --> Doctor[doctor]
    Utils --> Init[init]
    Utils --> Orchestrate[orchestrate]
    Utils --> Resolve[resolve]
    Utils --> Dashboard[dashboard]
    Utils --> Deploy[deploy]
    Utils --> Version[version]

    classDef core fill:#d4edda,stroke:#333,stroke-width:2px
    classDef infra fill:#fff3cd,stroke:#333,stroke-width:2px
    classDef util fill:#e1f5ff,stroke:#333,stroke-width:2px

    class Overview,Refine,Enrich,QA,Contracts core
    class Setup,Net,AWS,Ctx,Env,Arc infra
    class Distro,Doctor,Init,Orchestrate,Resolve,Dashboard,Deploy,Version util
```

## Quick start

1. Bootstrap a workspace and inspect the generated profile:

   ```bash
   uv run hotpass init --path ./workspace
   cd workspace
   ls config/profiles
   ```

2. Validate prerequisites:

   ```bash
   uv run hotpass doctor --config ./config/pipeline.quickstart.toml
   ```

3. Run the core pipeline with the bundled profile and timestamped archive:

   ```bash
   uv run hotpass refine \
     --profile quickstart \
     --profile-search-path ./config/profiles \
     --config ./config/pipeline.quickstart.toml \
     --log-format json
   ```

   ```
   {"event": "pipeline.summary", "data": {"total_records": 1033,
    "invalid_records": 0, "recommendations":
    ["CRITICAL: Average data quality score is below 50%. Review data sources and validation rules."]}}
   ```

   Outputs appear under `dist/` (`refined.xlsx`, `refined.parquet`, and a timestamped archive).
   If you switch to the aviation profile and point at the SACAA workbook you will see a Frictionless
   contract failure; resolve duplicates or update the governed schema before re-running.

Shared flags such as `--profile`, `--profile-search-path`, `--config`, and `--log-format`
can be supplied before the subcommand or repeated. Profiles defined in TOML or YAML load via
`--profile` and merge additional configuration files or feature toggles as needed.

## Core commands

Use these verbs for day-to-day work:

- `uv run hotpass overview` — list the active command set, installed extras, and profile search paths.
- `uv run hotpass refine` — execute the deterministic data refinement pipeline.
- `uv run hotpass enrich` — enrich refined data with deterministic sources by default (pass `--allow-network=true` after approvals).
- `uv run hotpass qa` — run quality gates (`fitness`, `data-quality`, `docs`, `contracts`, `cli`, `ta`).
- `uv run hotpass contracts` — emit contract bundles (YAML/JSON) for downstream systems.
- `uv run hotpass setup` — run the guided staging wizard (dependencies, tunnels, contexts, env files).
- `uv run hotpass net` — manage SSH/SSM tunnels to Prefect and Marquez.
- `uv run hotpass aws` — resolve the current AWS identity and verify EKS connectivity.
- `uv run hotpass ctx` — bootstrap Prefect profiles and Kubernetes contexts.
- `uv run hotpass env` — generate `.env` files aligned with active tunnels and contexts.
- `uv run hotpass explain-provenance --dataset ./dist/enriched.xlsx --row-id 0 --json` — surface provenance metadata for a specific row.
- `uv run hotpass plan research --dataset ./dist/refined.xlsx --row-id 0 --allow-network=false` — generate an adaptive research plan that combines local snapshots, deterministic enrichment, optional network fetchers, and crawl/backfill recommendations.
- `uv run hotpass crawl "https://example.test" --allow-network=true` — trigger the crawler-only pathway with rate-limit enforcement.

> 🔐 **QG-1 — CLI integrity:** `tests/cli/test_quality_gates.py` expects `hotpass overview` and `hotpass --help` to advertise the automation verbs (`setup`, `net`, `aws`, `ctx`, `env`) alongside the core pipeline commands. Update the test list and this reference together when you add or rename verbs.

## Infrastructure automation

The CLI also includes commands to streamline operator workflows such as tunnel setup,
AWS/EKS verification, Prefect/kubecontext bootstrap, and environment file generation.

### hotpass setup

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

### hotpass net

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

### hotpass aws

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

### hotpass ctx

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

### hotpass env

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

### hotpass arc

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

### hotpass distro

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

### hotpass run

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

### hotpass orchestrate

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

### hotpass explain-provenance

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

### hotpass resolve

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

### hotpass plan research

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

#### SearXNG integration

The planner integrates with [SearXNG](https://docs.searxng.org/) to coordinate
meta-search queries, deduplicate results, and seed the crawler. Enable the
service in the canonical configuration:

```toml
[pipeline.research.searx]
enabled = true
base_url = "https://search.internal.example"
api_key = "${SEARX_API_KEY}"        # optional; also accepts HOTPASS_SEARX_API_KEY
cache.ttl_seconds = 3600             # reuse results for an hour
throttle.min_interval_seconds = 2.0  # space out upstream requests
crawl_retry_attempts = 3             # retry flaky metadata fetches
```

Alternatively set `HOTPASS_SEARX_ENABLED=1` with overrides such as
`HOTPASS_SEARX_URL`, `HOTPASS_SEARX_MIN_INTERVAL`, or
`HOTPASS_SEARX_CACHE_DIR`. Search artefacts are written to
`.hotpass/searx/` and surface as a `searx_search` step in CLI output. The
crawler honours `crawl_retry_attempts`/`crawl_retry_backoff_seconds` and emits
OpenTelemetry metrics under the `hotpass.research.*` namespace for both cache
hits and retry events.

### hotpass crawl

Execute only the crawling component of the research pipeline.

```bash
uv run hotpass crawl "https://example.test" --allow-network
```

| Option            | Description                                                                                                 |
| ----------------- | ----------------------------------------------------------------------------------------------------------- |
| `QUERY_OR_URL`    | Either a URL to crawl or a free-text query for provider search adapters.                                    |
| `--allow-network` | Enable network calls; otherwise the command validates configuration and exits without contacting providers. |

Crawler runs write JSON artefacts to `.hotpass/research_runs/<slug>/` and respect profile-defined throttling (`research_rate_limit`).

### hotpass deploy

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

### hotpass dashboard

Launch the Streamlit monitoring dashboard. Install the `dashboards` extra before using this
subcommand.

```bash
uv run hotpass dashboard --host localhost --port 8501
```

| Option           | Description                                                   |
| ---------------- | ------------------------------------------------------------- |
| `--host HOST`    | Bind address for the dashboard server (default: `localhost`). |
| `--port INTEGER` | Port for the Streamlit dashboard (default: `8501`).           |

### hotpass doctor

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

### hotpass init

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
