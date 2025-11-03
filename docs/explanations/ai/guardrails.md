---
title: Explanation — AI guardrails
summary: Guardrails that keep Codex and Copilot automations safe when they run Hotpass workflows.
last_updated: 2025-11-03
---

# AI guardrails

Hotpass automations share infrastructure with human operators, so guardrails protect data boundaries, network usage, and quality outcomes. Use this page when you build or review AI workflows.

## Deterministic-first policy

- Profiles enabling enrichment or compliance must declare intent strings. The CLI loader (`apps/data-platform/hotpass/cli/configuration.py`) raises `ProfileIntentError` if a profile switches on `features.enrichment` or `features.compliance` without intent statements.
- Network enrichment remains opt-in. You must export `FEATURE_ENABLE_REMOTE_RESEARCH=1` **and** pass `--allow-network=true` to `hotpass enrich` (or the MCP equivalent) before remote collectors run.
- Default runs stay offline. Deterministic fixtures live under `dist/quality-gates/qg3-enrichment/` and power automated tests.

## Secrets and credentials

- Set provider keys as environment variables (for example, `HOTPASS_GEOCODE_API_KEY`, `HOTPASS_ENRICH_API_KEY`). The agent instructions in `AGENTS.md` reiterate this requirement.
- Do not hard-code secrets in prompts or tool arguments. MCP tools reject payloads that attempt to pass credentials inline.
- GitHub Actions (`.github/workflows/*`) wrap secrets behind repository-level protection; copy the pattern when you add new automations.

## Network allow-lists

- Codex Cloud uses an allow-list model. Keep the list minimal (`Common dependencies` plus the provider domains you actually call). Start with `GET, HEAD, OPTIONS` and add `POST` only when the provider demands it.
- For local `uv sync` runs, the helper script `ops/uv_sync_extras.sh` ensures you declare extras up front so the firewall can lock down after installation.

## Quality gates for assistants

- QG-5 (`tests/cli/test_quality_gates.py`) checks that `.github/copilot-instructions.md` and `AGENTS.md` stay present and include the required terminology (`profiles`, `deterministic`, `provenance`). If you update these docs, rerun `uv run pytest tests/cli/test_quality_gates.py -k QG5`.
- `AGENTS.md` includes a verification snippet that hits `https://pypi.org` with `requests.get`. Run it whenever you change the allow-list; blocked traffic means the agent will fail later.
- Codex and Copilot commands should always run `uv run hotpass refine --profile ... --archive` followed by `upload dist/refined.xlsx` as an artefact. Do not rely on screenshots or manual confirmation alone.

## Prompt hygiene

- Keep agent prompts declarative and include success criteria. The MCP server records each request in the optional audit log; review it for unsafe natural-language instructions (for example, “ignore provenance”).
- Use scoped roles. For read-only investigations, set `HOTPASS_MCP_DEFAULT_ROLE=observer` so the assistant cannot mutate data.
- Deny dangerous commands by default: the CLI command builder never exposes shell execution, and the MCP server refuses to register tools not explicitly allowed in the policy. Do not embed `subprocess` or `os.system` helpers in new tools without a compelling case.

## Human-in-the-loop steps

- Annotate incident or research workflows with explicit review points. For example, `hotpass.plan.research` returns a plan that still requires human approval before `hotpass.crawl` runs with `--allow-network=true`.
- Record approvals in `Next_Steps_Log.md` or the relevant governance ticket so auditors can trace who enabled network access.

These guardrails keep AI-run workflows compliant with the same standards as human operators. Update this page whenever you add an MCP tool, change the role policy, or adjust default network access.
