# Hotpass

Hotpass ingests messy spreadsheet collections (primarily XLSX) alongside orchestrated research crawlers managed through the CLI and MCP server. It cleans, normalises, backfills, maps relationships, and publishes analysis-ready outputs so teams can run deeper investigations with trusted data.

## Why Hotpass

- **Industry-ready**: Configurable profiles tailor validation rules, mappings, and terminology to your sector.
- **Quality first**: Great Expectations, POPIA compliance checks, and actionable quality reports keep stakeholders informed.
- **Operational**: Prefect orchestration, OpenTelemetry metrics, and a Streamlit dashboard make the pipeline production-friendly.

## Product vision

Hotpass is stewarded by n00tropic to prove that an open, automation-friendly data refinery can match enterprise suites feature-for-feature. Every shipping artifact—Prefect deployments, Marquez lineage facets, ARC manifests, agent tools—lives in Git so staging runs mirror what lands in production. The goal: messy spreadsheets in, governed outputs out, with clear provenance and repeatable automation backed by a commercial support path when teams outgrow the Business Source License defaults.

## Five-minute quickstart

1. Create an isolated environment with uv (n00tropic publishes the canonical extras list so agents and operators stay aligned):

   ```bash
   uv venv
   export HOTPASS_UV_EXTRAS="dev docs"
   bash ops/uv_sync_extras.sh
   ```

   Need orchestration or enrichment extras? Append them to
   `HOTPASS_UV_EXTRAS` before rerunning the helper script.

2. Confirm the CLI surface and available profiles:

   ```bash
   uv run hotpass overview
   ```

   The overview command lists the core verbs (`refine`, `enrich`, `qa`, `contracts`) and reports the
   installed extras/profile set so agents and operators can plan the next steps.

3. Inspect the governed asset inventory and feature readiness:

   ```bash
   uv run hotpass inventory status
   ```

   Add `--json` to integrate with automation or generate quick reports.

4. Run the refinement pipeline against the bundled fixtures:

   ```bash
   uv run hotpass refine \
     --input-dir ./data \
     --output-path ./dist/refined.xlsx \
     --profile generic \
     --archive
   ```

   The command writes refined outputs to `dist/refined.xlsx` and publishes the
   latest Great Expectations Data Docs under `dist/data-docs/`.

5. Optional: enrich the refined workbook deterministically (network off by default):

   ```bash
   uv run hotpass enrich \
     --input ./dist/refined.xlsx \
     --output ./dist/enriched.xlsx \
     --profile generic \
     --allow-network=false
   ```

6. Optional: regenerate validation reports explicitly while exploring the
   dataset contracts:

   ```bash
   uv run python ops/validation/refresh_data_docs.py
   ```

7. Optional: build an adaptive research plan for a specific entity (offline-first):

   ```bash
   uv run hotpass plan research \\
     --dataset ./dist/refined.xlsx \\
     --row-id 0 \\
     --allow-network
   ```

   The planner surfaces cached authority snapshots, deterministic enrichment updates, and
   crawl/backfill recommendations before you enable network access. To execute the
   crawl step with rate-limit enforcement, pass `--allow-network=true` only after
   setting the appropriate profile guardrails.

7. Launch the interactive bootstrap when you are ready to provision Prefect,
   observability, and supply-chain integrations:

   ```bash
   python ops/idp/bootstrap.py --execute
   ```

### Docker compose (local stack)

For an end-to-end sandbox run:

```bash
cd deploy/docker
docker compose up --build
# Optional LLM sidecar:
docker compose --profile llm up
```

The startup banner will remind you to open the VPN/bastion if the Prefect or Marquez health checks remain red.

### Automate tunnels and contexts

The CLI now provides one-command automation for tunnels, AWS identity checks, context bootstrap, and staging-ready environment files:

- Run the guided setup wizard (sync extras, open tunnels, configure contexts, emit `.env` files) in one go:

  ```bash
  hotpass setup --preset staging --host bastion.example.com --dry-run   # review plan
  hotpass setup --preset staging --host bastion.example.com --execute   # run plan
  ```

- Establish local forwards for Prefect and Marquez:

  ```bash
  hotpass net up --host bastion.example.com --detach
  ```

- Inspect or tear down active tunnels:

  ```bash
  hotpass net status
  hotpass net down --label staging
  ```

- Validate AWS credentials and store the summary:

  ```bash
  hotpass aws --profile staging --output text
  ```

- Create a Prefect profile and kubeconfig context (derives ports from active tunnels):

  ```bash
  hotpass ctx init --prefect-profile hotpass-staging --eks-cluster hotpass-staging
  ```

- Review stored context metadata before writing `.env` files:

  ```bash
  hotpass ctx list
  ```

- Generate an `.env` file aligned with the current session:

  ```bash
  hotpass env --target staging
  ```

## Inventory configuration

- `HOTPASS_INVENTORY_PATH` — override the path to `data/inventory/asset-register.yaml` when packaging or sourcing manifests externally.
- `HOTPASS_INVENTORY_FEATURE_STATUS_PATH` — override the feature status metadata file consumed by `hotpass inventory status` and `/api/inventory`.
- `HOTPASS_INVENTORY_CACHE_TTL` / `HOTPASS_INVENTORY_CACHE_TTL_MS` — adjust cache TTL (seconds or milliseconds, non-negative integers) shared by the CLI and web API.

### Keep uv caches on an external SSD

When running Hotpass from `/Volumes/APFS Space/GitHub/Hotpass` (or another external
volume), redirect `uv`'s data and cache directories so they live on the same drive:

```bash
chmod +x ops/use-ssd-env.sh
./ops/use-ssd-env.sh uv sync
```

The helper sets `UV_DATA_DIR` and `UV_CACHE_DIR` to the SSD and then executes the
given command, so virtual environments, wheels, and build artefacts no longer grow
under `~/.cache` on the internal disk.

Working on a hosted runner? Use `make sync EXTRAS="dev orchestration enrichment geospatial compliance dashboards"`
to replicate the environment bootstrap above with a single command.

## Preflight checks

Run these gates before opening a pull request so local results align with CI:

- `make qa` — runs Ruff format/lint, pytest with coverage, mypy, Bandit,
  detect-secrets, and pre-commit hooks.
- `uv run hotpass qa all` — executes the CLI-driven quality gates (QG‑1 → QG‑5)
  and mirrors the GitHub Actions workflow.
- `uv run python ops/validation/refresh_data_docs.py` — refreshes Data Docs
  to confirm expectation suites remain in sync with contracts.
- `uv run python ops/quality/fitness_functions.py` — exercises the
  architectural fitness checks documented in `docs/architecture/fitness-functions.md`.
- `uv run pytest -n auto` — executes the full test suite in parallel (mirrors CI’s xdist configuration).
- Optional: set `HOTPASS_ENABLE_PRESIDIO=1` before running if you need Presidio-backed
  PII redaction. By default Hotpass skips the heavy Presidio models to keep offline
  runs self-contained.

On orchestrated environments, register multiple Prefect workers against a shared pool so
`uv run hotpass qa all` and pipeline runs can execute in parallel. Monitor worker heartbeats
in Prefect and align worker images with the same `uv` environment you use locally.

## Post-deploy observability validation

After each deploy, confirm the runtime surfaces are healthy before handing over to operations:

- **Lineage UI** – follow the [lineage smoke test runbook](docs/operations/lineage-smoke-tests.md) to verify Marquez ingests new runs, capture the datasets/jobs graph, and archive API payloads under `dist/staging/marquez/`.
- **Prefect guardrails** – run the [Prefect backfill guardrail rehearsal](docs/operations/prefect-backfill-guardrails.md) to ensure concurrency limits remain intact and Prefect logs are stored in `dist/staging/backfill/`.
- **OpenTelemetry exporters** – review the [observability registry overview](docs/observability/index.md) and confirm OTLP endpoints receive spans/metrics (or console exporters flush) using the compose stack shipped in `deploy/docker/docker-compose.yml`. Document any overrides in `Next_Steps.md` before declaring the release healthy.

## Documentation

The full documentation lives under [`docs/`](docs/index.md) and follows the Diátaxis framework:

- [Tutorials](docs/tutorials/quickstart.md) — end-to-end walkthroughs.
- [How-to guides](docs/how-to-guides/configure-pipeline.md) — targeted tasks such as configuring profiles or enabling observability. See the [dependency profile guide](docs/how-to-guides/dependency-profiles.md) to pick the right extras.
- [Reference](docs/reference/cli.md) — command syntax, data model, and expectation catalogue.
- Governance artefacts — [Data Docs](docs/reference/data-docs.md),
  [schema exports](docs/reference/schema-exports.md), and the
  [Marquez lineage quickstart](docs/observability/marquez.md).
- [Explanations](docs/explanations/architecture.md) — architectural decisions and platform scope.
- [Roadmap](docs/roadmap.md) — delivery status, quality gates, and tracked follow-ups. See also the
  repository-level [ROADMAP.md](ROADMAP.md) for a per-phase PR checklist.
- [Research-first orchestration](docs/reference/profiles.md#provider-guardrails) — profile-driven rate limits, audit artefacts, and MCP/CLI workflows for plan/crawl operations.

## Contributing

Read the [documentation contributing guide](docs/CONTRIBUTING.md) and [style guide](docs/style.md), then submit pull requests using Conventional Commits. The contributing guide now includes a five-minute documentation quickstart plus preflight reminders. Run the consolidated QA suite before opening a PR:

```bash
make qa
```

The `qa` target runs Ruff formatting and linting, pytest with coverage, mypy (strict for the pipeline configuration module and QA tooling), Bandit, detect-secrets, and repository pre-commit hooks so local results match CI.

Join the conversation in the `#hotpass` Slack channel or open an issue using the templates under `.github/ISSUE_TEMPLATE/`.
