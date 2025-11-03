# AGENTS.md — Running Hotpass with Codex

This note tells Codex how to run Hotpass end‑to‑end and what internet access it may need. Keep it short, explicit, and safe-by-default.

---

## 1) Codex Cloud: environment recipe

### Purpose

Build/install Hotpass so agents can ingest spreadsheet workbooks and orchestrated research crawlers, clean and backfill data, map relationships, and run deeper analysis through the CLI and MCP automations.

### 1.1 Internet access policy

- **Mode:** On, with an allowlist.
- **Preset:** _Common dependencies_ (for builds), **plus** the runtime API domains you actually use (see §3).
- **HTTP methods:** start with `GET, HEAD, OPTIONS` only; enable `POST` only if a provider requires it.

### 1.2 Environment variables vs secrets

- Put **runtime API keys** in **environment variables** (available to the agent while it runs).
- Use **secrets only for setup** (they are removed before the agent phase).

### 1.3 Setup script (runs before the agent, has full internet)

Use either _pip_ or _uv_. Pick one block.

#### Option A — pip only

```bash
python -m pip install -U pip
python -m pip install -e ".[orchestration,enrichment,geospatial,compliance]"
```

#### Option B — uv

```bash
python -m pip install -U uv
uv venv
uv sync --extra orchestration --extra enrichment --extra geospatial --extra compliance
```

> Notes
>
> - The _Common dependencies_ preset already allowlists PyPI domains; you shouldn’t need to add them manually.
> - Keep the setup fast: avoid heavyweight toolchains you don’t need.

#### 1.3.1 Select dependency profiles

Codex runners start with a lean `dev orchestration` profile. To add or remove extras on demand:

1. Choose the extras your task needs (space-separated):

| Profile          | Extras string                                                   | Notes                                         |
| ---------------- | --------------------------------------------------------------- | --------------------------------------------- |
| `core` (default) | `dev orchestration`                                             | Installs CLI + Prefect orchestration support. |
| `docs`           | `dev docs`                                                      | Adds Sphinx + Diátaxis toolchain.             |
| `geospatial`     | `dev orchestration geospatial`                                  | Adds GeoPandas/Geopy extras.                  |
| `compliance`     | `dev orchestration compliance`                                  | Adds Presidio-based compliance stack.         |
| `full`           | `dev orchestration enrichment geospatial compliance dashboards` | Everything, slower to install.                |

2. Export the selection before running `uv sync` (Codex setup script):

```bash
export HOTPASS_UV_EXTRAS="dev orchestration geospatial"
bash ops/uv_sync_extras.sh
```

3. After the extras install step, the firewall should be locked down. Declare every required extra up front—additional installs will fail once the firewall is active.

The helper script lives in `ops/uv_sync_extras.sh` and converts the space-separated list into the correct `uv sync --extra …` flags. Agents using the pip setup can mimic the behaviour with:

```bash
python -m pip install -U pip
python -m pip install -e ".[dev,orchestration,geospatial]"
```

For local development you can also run `make sync EXTRAS="dev orchestration"` (or another extras string). The make target wraps the same helper script so CLI, Codex agents, and CI stay aligned.

### 1.4 Agent run command (what Codex should execute)

Baseline run into `dist/refined.xlsx`:

```bash
uv run hotpass refine \
  --input-dir ./data \
  --output-path ./dist/refined.xlsx \
  --profile generic \
  --archive
```

If you used Option A (pip), replace `uv run` with `python -m hotpass refine`:

```bash
python -m hotpass refine \
  --input-dir ./data \
  --output-path ./dist/refined.xlsx \
  --profile generic \
  --archive
```

**Artifacts**: `dist/` will contain the refined output and any reports Hotpass produces.

---

## 2) Expected network calls (and domains to allowlist)

### 2.1 During setup (always on)

PyPI + friends for dependency installs (already covered by _Common dependencies_):

- `pypi.org`, `pypa.io`, `pythonhosted.org` (package index / wheels)
- `github.com`, `githubusercontent.com` (occasional source downloads)

### 2.2 During the agent run (depends on enabled extras)

- **Core pipeline:** local only; no network needed.
- **Enrichment / Geospatial / Compliance extras:** may call your chosen providers. Add only what you use, e.g.:
  - Geocoding/examples: `nominatim.openstreetmap.org`, `api.opencagedata.com`, `api.geoapify.com`
  - Company/people enrichment (examples): provider-specific API domains

> Keep the list tight. Prefer read‑only `GET` where possible; enable `POST` only if strictly required.

---

## 3) Runtime configuration

Set provider credentials as environment variables in the Codex **Environment** (not in Secrets if they’re needed at runtime), for example:

```text
HOTPASS_GEOCODE_API_KEY=...
HOTPASS_ENRICH_API_KEY=...
```

Document any additional variables your chosen providers expect.

---

## 4) Quick verification (sanity check task)

Have Codex run the following first to confirm network policy and imports:

```bash
python - <<'PY'
import sys, requests
print('py ok', sys.version.split()[0])
print('net ok', requests.get('https://pypi.org', timeout=10).status_code)
PY
```

If this is blocked, expand the allowlist or allowed methods and retry.

---

## 5) Troubleshooting

- **ImportError / missing wheel** → rerun the task; ensure _Common dependencies_ is selected.
- **HTTP 403/429 from a provider** → your key or method is wrong, or the domain/method is not allowlisted.
- **Agent cannot see your key** → keys must be Environment Variables for runtime.

---

## 6) Test authoring guardrail

- When generating or modifying pytest suites, avoid bare `assert` statements. Use the shared `expect(..., message)` helper pattern documented in `docs/how-to-guides/assert-free-pytest.md` so Bandit rule **B101** stays green without waivers.

---

## 7) Local use with Codex CLI (optional)

If running locally, enable network in the `workspace-write` sandbox and reuse the commands above.
Example `~/.codex/config.toml` snippet:

```toml
[sandbox_workspace_write]
network_access = true
```

---

### Checklist (copy/paste into a Codex task)

1. Use Cloud environment **Hotpass**; Internet Access: _Common dependencies_ + required provider domains; Methods: `GET,HEAD,OPTIONS`.
2. Run **Setup script** (Option A or B).
3. Execute the **Agent run command**.
4. Upload `dist/refined.xlsx` as artifact.

### Tool Contract

- Machine-readable tool definitions live in [`tools.json`](./tools.json). The same file is consumed by the web UI chat console so Codex, Copilot, and custom agents share an identical contract (`list_prefect_flows`, `get_marquez_lineage`, `run_hotpass_refine`).

---

## 8) CLI Commands (UPGRADE.md Aligned)

As of the UPGRADE.md implementation, Hotpass provides these CLI verbs:

### Discovery & Overview

```bash
uv run hotpass overview
```

Shows all available commands, quick start examples, and system status.

### Core Pipeline Commands

**Refine** (clean and normalize data):

```bash
uv run hotpass refine \
  --input-dir ./data \
  --output-path ./dist/refined.xlsx \
  --profile aviation \
  --archive
```

**Enrich** (add data from deterministic and optional network sources):

```bash
# Deterministic only (safe, offline)
uv run hotpass enrich \
  --input ./dist/refined.xlsx \
  --output ./dist/enriched.xlsx \
  --profile aviation \
  --allow-network=false

# With network (requires FEATURE_ENABLE_REMOTE_RESEARCH=1 and ALLOW_NETWORK_RESEARCH=1)
uv run hotpass enrich \
  --input ./dist/refined.xlsx \
  --output ./dist/enriched-network.xlsx \
  --profile aviation \
  --allow-network=true
```

**Explain provenance** (surface enrichment metadata for a specific row):

```bash
uv run hotpass explain-provenance \
  --dataset ./dist/enriched.xlsx \
  --row-id 0 \
  --json
```

> Use `--json` for machine-readable output or omit it for a Rich table. The command exits with status
> `2` when provenance columns are missing so agents can trace absent metadata quickly.

**QA** (quality assurance checks):

```bash
uv run hotpass qa all          # All checks
uv run hotpass qa fitness      # Fitness functions only
uv run hotpass qa profiles     # Profile validation
uv run hotpass qa docs         # Documentation checks
uv run hotpass qa ta           # Technical acceptance
```

**Contracts** (generate data contracts):

```bash
uv run hotpass contracts emit \
  --profile aviation \
  --format yaml \
  --output ./contracts/aviation.yaml
```

### Research Planning & Crawling

**Plan research** (surface local snapshots, deterministic updates, network requirements):

```bash
uv run hotpass plan research \
  --dataset ./dist/refined.xlsx \
  --row-id 0 \
  --allow-network=false
```

**Crawl** (execute orchestrator crawl-only flow):

```bash
uv run hotpass crawl "https://example.test" --allow-network=true
```

- Artefacts: each run writes a JSON summary under `.hotpass/research_runs/` capturing the plan, step outcomes, and provenance metadata for future audits.
- Throttling: profiles may set `research_rate_limit.min_interval_seconds` (plus optional `burst`) to enforce per-entity crawl spacing; the orchestrator enforces the burst window before applying the delay and records crawl metadata under `.hotpass/research_runs/<slug>/crawl/`.
- Guardrails: enable `FEATURE_ENABLE_REMOTE_RESEARCH=1` and `ALLOW_NETWORK_RESEARCH=1` only when network fetchers are approved; combine with profile rate limits to respect provider SLAs and audit via the crawl artefacts above.
- Prefect workers: attach multiple workers to a shared work pool (for example `hotpass-shared-workers`) so agent-triggered pipeline, enrichment, and QA flows can run in parallel. Monitor worker heartbeats and keep worker environments aligned with the production `uv` extras set.

### Infrastructure & Context Automation

Use these helpers to prepare operator environments quickly:

```bash
# Guided wizard (sync extras, tunnels, AWS, contexts, env files)
hotpass setup --preset staging --host bastion.example.com --dry-run   # review the plan
hotpass setup --preset staging --host bastion.example.com --execute   # run the plan

# Establish SSH tunnel forwards (background)
hotpass net up --host bastion.example.com --detach

# Confirm AWS identity and optional EKS connectivity
hotpass aws --profile staging --eks-cluster hotpass-staging --dry-run

# Bootstrap Prefect and kube contexts (reuses tunnel ports)
hotpass ctx init --prefect-profile hotpass-staging --eks-cluster hotpass-staging

# Emit .env file aligned with the active session
hotpass env --target staging

# Verify ARC lifecycle health and store the summary
hotpass arc --owner ExampleOrg --repository Hotpass --scale-set hotpass-arc --store-summary
```

Documentation bundles can be collected with:

```bash
hotpass distro docs --output dist/docs
```

### Key Principles

1. **Profile-First**: Always specify `--profile <name>`. Profiles contain critical business logic (column mappings, validation rules, compliance settings).

2. **Deterministic-First**: Enrichment defaults to offline/deterministic sources. Network enrichment requires explicit enablement via environment variables + `--allow-network=true` flag.

3. **Provenance Tracking**: All enriched data includes provenance columns showing source, timestamp, confidence, and strategy.

---

## 9) MCP (Model Context Protocol) Tools

Hotpass exposes an MCP stdio server that allows AI assistants (GitHub Copilot, Codex, Agent HQ) to call Hotpass operations as tools.

### Starting the MCP Server

```bash
python -m hotpass.mcp.server
# OR with uv
uv run python -m hotpass.mcp.server
```

The server runs in stdio mode and responds to JSON-RPC 2.0 requests.

### Available MCP Tools

1. **`hotpass.refine`**
   - Description: Run the Hotpass refinement pipeline
   - Inputs:
     - `input_path` (required): Directory or file with data to refine
     - `output_path` (required): Where to write refined output
     - `profile` (default: "generic"): Industry profile
     - `archive` (default: false): Create archive of refined output

2. **`hotpass.enrich`**
   - Description: Enrich refined data with additional information
   - Inputs:
     - `input_path` (required): Refined input file
     - `output_path` (required): Where to write enriched output
     - `profile` (default: "generic"): Industry profile
     - `allow_network` (default: false): Enable network-based enrichment

3. **`hotpass.qa`**
   - Description: Run quality assurance checks
   - Inputs:
     - `target` (default: "all"): Which checks to run (all | fitness | profiles | contracts | docs | ta)

4. **`hotpass.explain_provenance`**
   - Description: Explain data provenance for a specific row
   - Inputs:
     - `row_id` (required): ID of the row to explain
     - `dataset_path` (required): Path to the dataset file

5. **`hotpass.crawl`** (guarded, optional)
   - Description: Execute research crawler (requires network permission)
   - Inputs:
     - `query_or_url` (required): Query string or URL to crawl
     - `profile` (default: "generic"): Industry profile
     - `backend` (default: "deterministic"): Backend to use (deterministic | research)

### MCP Tool Discovery

Tools are discoverable via the `tools/list` JSON-RPC method:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "id": 1
}
```

Response includes all 5 tools with their schemas.

### MCP Security

- **Network operations**: Require explicit user approval (per Copilot CLI defaults)
- **File access**: Follows workspace permissions
- **API keys**: Read from environment variables only (never in tool arguments)
- **Audit logging**: MCP calls logged for compliance (when configured)

### Using MCP with Copilot CLI

```bash
# Discover Hotpass tools
/mcp list

# Call a tool
/mcp call hotpass.refine input_path=./data output_path=./dist/refined.xlsx profile=aviation
```

### Using MCP with Agent HQ / Codex

Agents can call tools directly via the MCP protocol:

```javascript
const result = await callTool("hotpass.refine", {
  input_path: "./data",
  output_path: "./dist/refined.xlsx",
  profile: "aviation",
  archive: true,
});
```

### Using dolphin-mcp locally

`dolphin-mcp` is a lightweight MCP client CLI that mirrors Copilot’s behaviour. Use it to debug tool responses or to exercise the Hotpass server without a Copilot session.

1. **Prepare the environment**
  ```bash
  uv venv
  export HOTPASS_UV_EXTRAS="dev orchestration enrichment"
  bash ops/uv_sync_extras.sh
  ```
  The helper script installs the extras that keep CLI and MCP commands aligned.
2. **Install the client**
  ```bash
  uv pip install dolphin-mcp lmstudio
  ```
  The optional `lmstudio` dependency is required because the client eagerly imports all providers.
3. **Register the server** — create `.vscode/mcp.json` (or `.mcp.json` at the repo root) with:
  ```json
  {
    "version": "0.1",
    "servers": [
     {
      "name": "hotpass",
      "command": ["uv", "run", "python", "-m", "hotpass.mcp.server"],
      "transport": "stdio",
      "env": {
        "HOTPASS_UV_EXTRAS": "dev orchestration enrichment"
      }
     }
    ]
  }
  ```
  Keep the command in sync with this document so relative paths resolve.
4. **Allow Copilot access** — ensure `.vscode/settings.json` contains `"chat.mcp.access": "all"` so the editor can talk to local servers.
5. **Start the server**
  ```bash
  uv run python -m hotpass.mcp.server
  ```
  Start it from the repo root so `./data` and `./dist` resolve correctly.
6. **Discover tools** — run `dolphin-mcp list --server hotpass` or `/mcp list` from Copilot; you should see `hotpass.refine`, `hotpass.enrich`, `hotpass.qa`, `hotpass.setup`, `hotpass.net`, `hotpass.ctx`, `hotpass.env`, `hotpass.aws`, `hotpass.arc`, `hotpass.explain_provenance`, `hotpass.plan.research`, `hotpass.crawl`, and `hotpass.ta.check`.
7. **Test a call** — from Copilot chat ask, “Run hotpass.refine on ./data and write to ./dist/refined.xlsx with profile generic and archive=true.” From the CLI:
  ```bash
  dolphin-mcp chat --server hotpass --model ollama/llama3.1
  ```
  then enter:
  ```
  /call hotpass.refine input_dir=./data output_path=./dist/refined.xlsx profile=generic archive=true
  ```
8. **Enable network research when required**
  ```bash
  export FEATURE_ENABLE_REMOTE_RESEARCH=1
  export ALLOW_NETWORK_RESEARCH=1
  ```
  Set these before launching the server if you plan to call `hotpass.crawl` or network-backed enrichment.

### Automate setup with MCP

- Preview the staging wizard plan:
  ```
  /call hotpass.setup preset=staging host=bastion.example.com skip_steps=["prereqs","aws","ctx","env","arc"] dry_run=true
  ```
- Execute the full bootstrap (opens tunnels, verifies AWS, writes `.env`):
  ```
  /call hotpass.setup preset=staging host=bastion.example.com execute=true assume_yes=true arc_owner=ExampleOrg arc_repository=Hotpass arc_scale_set=hotpass-arc
  ```
- Manage tunnels directly:
  ```
  /call hotpass.net action=up host=bastion.example.com label=staging detach=true
  /call hotpass.net action=status
  /call hotpass.net action=down label=staging
  ```

Combine these with `hotpass.ctx`, `hotpass.env`, `hotpass.aws`, and `hotpass.arc` calls to keep staging environments aligned without leaving chat.

Model routing is configured in `apps/web-ui/public/config/llm-providers.yaml`. Keep GitHub Copilot as the default (`copilot`) and update the YAML when you add new providers so the Admin UI and MCP tooling stay in sync.

---

## 10) Quality Gates (Automated Testing)

The UPGRADE.md implementation includes 5 quality gates (QG) that verify system integrity:

- **QG-1**: CLI Integrity - `hotpass overview`/`hotpass --help` advertise the automation
  verbs (`setup`, `net`, `aws`, `ctx`, `env`) alongside core pipeline commands; command
  help for each verb must succeed.
- **QG-2**: Data Quality - Great Expectations validation passes
- **QG-3**: Enrichment Chain - Offline enrichment works with provenance
- **QG-4**: MCP Discoverability - All MCP tools discoverable and callable
- **QG-5**: Docs/Instructions - Agent documentation complete and accurate

Run all quality gate tests:

```bash
uv run pytest tests/cli/test_quality_gates.py -v
```

Expected: 30/30 tests passing.

For longitudinal tracking run:

```bash
python ops/quality/ta_history_report.py --json
```

This summarises the TA history stored under `dist/quality-gates/history.ndjson` (latest thresholds feed the MCP/CLI TA tooling).

---

## 11) Complete Agent Workflow Example

```bash
# 1. Discover available commands
uv run hotpass overview

# 2. Refine raw data
uv run hotpass refine \
  --input-dir ./data \
  --output-path ./dist/refined.xlsx \
  --profile aviation \
  --archive

# 3. Enrich with deterministic sources only (safe)
uv run hotpass enrich \
  --input ./dist/refined.xlsx \
  --output ./dist/enriched.xlsx \
  --profile aviation \
  --allow-network=false

# 4. Run quality checks
uv run hotpass qa all

# 5. Generate data contract
uv run hotpass contracts emit \
  --profile aviation \
  --format yaml \
  --output ./contracts/aviation.yaml

# 6. Inspect inventory readiness across surfaces
uv run hotpass inventory status --json

# 7. Review provenance in enriched file
# (Check columns: provenance_source, provenance_timestamp, provenance_confidence)
```

---

## 12) References for Agents

- **UPGRADE.md**: Full specification of CLI/MCP requirements and quality gates
- **IMPLEMENTATION_PLAN.md**: Detailed implementation plan with sprint breakdown
- **docs/agent-instructions.md**: Comprehensive agent workflows and troubleshooting
- **.github/copilot-instructions.md**: Project-wide guidance for all AI agents
- **tests/cli/test_quality_gates.py**: Quality gate test implementations
