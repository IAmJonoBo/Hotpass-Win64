# Hotpass Guidance for AI Agents

These notes equip GitHub Copilot CLI, Copilot Agent HQ, and Codex-based agents to work safely and efficiently inside the Hotpass repository.

---

## 1. Mission Snapshot

- **What Hotpass does**: Refine messy spreadsheets, enrich them with deterministic and optional research fetchers, run relationship/linkage analysis, and publish governed outputs with provenance.
- **Primary interfaces**: The CLI (`uv run hotpass <verb>`) and the MCP stdio server (`python -m hotpass.mcp.server`) expose the same operations. MCP tools mirror the CLI verbs (`refine`, `enrich`, `qa`, `contracts`) plus provenance explainers and TA checks.
- **Default stance**: Deterministic-first, offline-safe. Network enrichment requires `FEATURE_ENABLE_REMOTE_RESEARCH=1`, `ALLOW_NETWORK_RESEARCH=1`, and the `--allow-network=true` flag.

---

## 2. Getting Started (Agent Playbook)

1. **Sync dependencies**
   ```bash
   uv venv
   export HOTPASS_UV_EXTRAS="dev orchestration enrichment"
   bash ops/uv_sync_extras.sh
   ```
2. **Discover the surface**
   ```bash
   uv run hotpass overview
   ```
   Confirm that `refine`, `enrich`, `qa`, and `contracts` appear.
3. **Run the core pipeline**
   ```bash
   uv run hotpass refine \
     --input-dir ./data \
     --output-path ./dist/refined.xlsx \
     --profile generic \
     --archive
   ```
4. **Optionally enrich deterministically**
   ```bash
   uv run hotpass enrich \
     --input ./dist/refined.xlsx \
     --output ./dist/enriched.xlsx \
     --profile generic \
     --allow-network=false
   ```
   Inspect provenance for any enriched row when needed:
   ```bash
   uv run hotpass explain-provenance \
     --dataset ./dist/enriched.xlsx \
     --row-id 0 \
     --json
   ```
5. **Execute quality gates**
   ```bash
   uv run hotpass qa all
   ```
6. **Plan adaptive research (optional)**
   ```bash
   uv run hotpass plan research \\
     --dataset ./dist/refined.xlsx \\
     --row-id 0 \\
     --allow-network=false
   ```
   Review step outcomes before enabling network enrichment or crawling.
7. **Run the guided operator wizard (optional, great for staging)**
   ```bash
   hotpass setup --preset staging --host bastion.example.com --dry-run   # review
   hotpass setup --preset staging --host bastion.example.com --execute   # run
   ```
   The wizard orchestrates dependency sync, tunnels, AWS verification, context bootstrap, and `.env` generation.
8. **Expose MCP tools (when needed)**
   ```bash
   uv run python -m hotpass.mcp.server
   ```
   Use `/mcp list` (Copilot CLI) to verify `hotpass.refine`, `hotpass.enrich`, `hotpass.qa`, `hotpass.setup`, `hotpass.net`, `hotpass.ctx`, `hotpass.env`, `hotpass.aws`, `hotpass.arc`, `hotpass.explain_provenance`, `hotpass.plan.research`, `hotpass.crawl`, and `hotpass.ta.check`.
9. **Leverage infrastructure helpers via MCP**
   Preview the wizard or launch tunnels without leaving chat:
   ```
   /call hotpass.setup preset=staging host=bastion.example.com dry_run=true skip_steps=["aws","ctx","env","arc"]
   /call hotpass.setup preset=staging host=bastion.example.com execute=true arc_owner=ExampleOrg arc_repository=Hotpass arc_scale_set=hotpass-arc
   /call hotpass.net action=status
   /call hotpass.env target=staging allow_network=false dry_run=true
   ```

---

## Using dolphin-mcp with Hotpass

Follow these steps to connect GitHub Copilot and the `dolphin-mcp` client to the Hotpass MCP stdio server.

1. **Prepare the environment**
   ```bash
   uv venv
   export HOTPASS_UV_EXTRAS="dev orchestration enrichment"
   bash ops/uv_sync_extras.sh
   ```
   The helper script installs the extras that keep CLI and MCP commands in sync.
2. **Install the MCP client**
   ```bash
   uv pip install dolphin-mcp lmstudio
   ```
   `dolphin-mcp` requires the optional `lmstudio` dependency to load cleanly.
3. **Register the server** — add `.vscode/mcp.json` (or `.mcp.json` at the repo root) with:
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
   Keep the command aligned with `AGENTS.md` so Copilot launches the server exactly as documented.
4. **Allow Copilot access** — set `"chat.mcp.access": "all"` in `.vscode/settings.json` so Copilot can call local servers.
5. **Start the server**
   ```bash
   uv run python -m hotpass.mcp.server
   ```
   Run it from the repository root so relative paths such as `./data` resolve correctly.
6. **Discover tools** — once the server is up, Copilot (or `/mcp list` in the CLI) should list:
   - `hotpass.refine`
   - `hotpass.enrich`
   - `hotpass.qa`
   - `hotpass.explain_provenance`
   - `hotpass.crawl`
   - `hotpass.ta.check`
7. **Test a call from Copilot** — ask: “Run hotpass.refine on ./data and write to ./dist/refined.xlsx with profile generic and archive=true.” Copilot will invoke `hotpass.refine` with the parameters above.
8. **Test via dolphin-mcp**
   ```bash
   dolphin-mcp chat --server hotpass --model ollama/llama3.1
   ```
   Then issue:
   ```
   /call hotpass.refine input_dir=./data output_path=./dist/refined.xlsx profile=generic archive=true
   ```
   The CLI prints the tool response for quick debugging.
9. **Enable network research when needed**
   ```bash
   export FEATURE_ENABLE_REMOTE_RESEARCH=1
   export ALLOW_NETWORK_RESEARCH=1
   ```
   Set both variables before starting the server when network-backed enrichment or crawl support is required.

---

## 3. Repository Map

- `apps/data-platform/hotpass/cli/commands/` — CLI entry points (`overview`, `refine`, `enrich`, `qa`, `contracts`, `resolve`, etc.). Extend parsers here and keep help text concise.
- `apps/data-platform/hotpass/enrichment/` — Deterministic and research fetchers, pipeline orchestration, and provenance tracking.
- `apps/data-platform/hotpass/linkage/` — Splink/RapidFuzz entity resolution with optional Label Studio review queues.
- `apps/data-platform/hotpass/mcp/server.py` — MCP stdio server implementation; mirrors CLI behaviour. Update tool registration when adding new verbs.
- `ops/quality/` — Quality gate runners (`run_qg*.py`, `run_all_gates.py`) referenced by CI and `hotpass qa`.
- `docs/` — MyST/Sphinx documentation organised by Diátaxis; `docs/reference/cli.md` is the authoritative CLI spec.
- `tests/` — Pytest suites using the shared `expect(condition, message)` helper (no bare `assert`).

---

## 4. QA & Safety Checklist

- **Before PRs**: run `make qa`, `uv run hotpass qa all`, and `uv run python ops/validation/refresh_data_docs.py`.
- **Quality gates**: QG‑1 → QG‑5 must stay green. Use `ops/quality/run_all_gates.py --json` for structured summaries or call `hotpass.ta.check` via MCP.
- **Testing conventions**: Replace bare `assert` with `expect(...)` (see `docs/how-to-guides/assert-free-pytest.md`). Keep fixtures under `tests/data` and `tests/fixtures`.
- **Optional dependencies**: Handle missing Great Expectations, Prefect, Splink, requests, trafilatura, etc. gracefully. Never import them at module top level without guards.
- **Security**: Respect POPIA compliance helpers, provenance schema, and audit logging. When touching network code, honour environment toggles and rate-limit guidance.

---

## 5. Agent Guardrails

- Never request or print secrets; rely on environment variables.
- Honour network policy: run deterministic enrichment first; escalate to network fetchers only when explicitly enabled.
- Keep CLI output succinct. Help text should highlight required flags and the `--profile` expectation.
- Log MCP tool invocations when extending the server (planned location: `./.hotpass/mcp-audit.log`).
- Validate documentation updates alongside behavioural changes (`docs/reference/cli.md`, `AGENTS.md`, `UPGRADE.md`).

---

## 6. Key References

- `UPGRADE.md` — Canonical roadmap and sprint plan.
- `Next_Steps.md` — Date-bound tasks and ownership.
- `docs/reference/cli.md` — Full CLI option matrix.
- `docs/reference/data-docs.md` & `dist/quality-gates/` — Validation artefacts.
- `.github/workflows/quality-gates.yml` — CI implementation of QG‑1 → QG‑5.

Keep this file aligned with the runbook. When CLI or MCP surfaces change, update this guidance, `AGENTS.md`, and `UPGRADE.md` in the same PR.
