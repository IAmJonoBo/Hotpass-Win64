---
title: Reference — MCP tools
summary: Model Context Protocol tools exposed by Hotpass and their CLI equivalents.
last_updated: 2025-11-02
---

Hotpass ships a stdio MCP server (`python -m hotpass.mcp.server`) that mirrors the CLI surface so agents can orchestrate the platform without bespoke adapters. The table below documents each tool, the underlying CLI command, and common arguments.

| Tool name | Purpose | CLI equivalent | Key arguments |
| --------- | ------- | -------------- | ------------- |
| `hotpass.refine` | Run the deterministic refinement pipeline. | `uv run hotpass refine --input-dir … --output-path …` | `input_path`, `output_path`, `profile`, `archive` |
| `hotpass.enrich` | Enrich refined workbooks deterministically or with network sources. | `uv run hotpass enrich --input … --output …` | `input_path`, `output_path`, `profile`, `allow_network` |
| `hotpass.qa` | Execute quality gates (QG‑1 → QG‑5). | `uv run hotpass qa <target>` | `target` (`all`, `fitness`, `docs`, etc.) |
| `hotpass.setup` | End-to-end wizard: sync extras, open tunnels, verify AWS, bootstrap contexts, emit `.env`. | `uv run hotpass setup …` | `preset`, `host`, `skip_steps`, `execute`, `extras`, `aws_profile`, `arc_owner`, … |
| `hotpass.net` | Manage SSH/SSM tunnels. | `uv run hotpass net <up|down|status>` | `action`, `host`, `via`, `label`, `all`, `detach`, `prefect_port`, `marquez_port` |
| `hotpass.ctx` | Configure or list Prefect/Kubernetes contexts. | `uv run hotpass ctx <init|list>` | `prefect_profile`, `prefect_url`, `eks_cluster`, `kube_context`, `namespace`, `no_prefect`, `no_kube`, `dry_run` |
| `hotpass.env` | Generate `.env.<target>` files aligned with tunnels/contexts. | `uv run hotpass env --target …` | `target`, `prefect_url`, `openlineage_url`, `allow_network`, `force`, `dry_run` |
| `hotpass.aws` | Verify AWS identity and optional EKS connectivity. | `uv run hotpass aws …` | `profile`, `region`, `eks_cluster`, `verify_kubeconfig`, `output`, `dry_run` |
| `hotpass.arc` | Wrap ARC lifecycle verification and evidence capture. | `uv run hotpass arc …` | `owner`, `repository`, `scale_set`, `namespace`, `aws_region`, `snapshot`, `verify_oidc`, `store_summary`, `dry_run` |
| `hotpass.explain_provenance` | Surface provenance columns for a given row. | Reads workbook directly (no CLI call). | `dataset_path`, `row_id` |
| `hotpass.plan.research` | Build deterministic/network research plans. | Uses `ResearchOrchestrator`. | `profile`, `dataset_path`, `row_id`, `entity`, `allow_network` |
| `hotpass.crawl` | Execute crawl-only orchestration flow. | Uses `ResearchOrchestrator`. | `query_or_url`, `profile`, `allow_network`, `backend` |
| `hotpass.ta.check` | Run the technical acceptance script (`ops/quality/run_all_gates.py`). | `python ops/quality/run_all_gates.py --json` | `gate` (1‑5) |

### Example dolphin-mcp session

```bash
uv run python -m hotpass.mcp.server &
dolphin-mcp chat --server hotpass --model ollama/llama3.1
```

```
/mcp list
/call hotpass.setup preset=staging host=bastion.example.com dry_run=true skip_steps=["aws","ctx","env","arc"]
/call hotpass.net action=status
/call hotpass.aws profile=staging region=eu-west-1 dry_run=true output=json
```

### Tool availability

- `hotpass.setup`, `hotpass.net`, `hotpass.ctx`, `hotpass.env`, `hotpass.aws`, and `hotpass.arc` were introduced in October 2025 to streamline staging bootstrap for agents.
- Tools inherit the same safeguards as the CLI: network enrichment still requires `FEATURE_ENABLE_REMOTE_RESEARCH=1` and `ALLOW_NETWORK_RESEARCH=1`, while ARC verification honours the `.hotpass/` evidence directory.
- When invoking from IDEs (VS Code, Cursor, Zed, etc.), ensure `chat.mcp.access` is set to `"all"` so the editor can reach the local server. For quick experiments, use `dolphin-mcp` as described in [AGENTS.md](../AGENTS.md).
- Model routing and provider metadata live in `apps/web-ui/public/config/llm-providers.yaml`. Update the YAML to surface additional providers in both the Admin UI and MCP clients.
