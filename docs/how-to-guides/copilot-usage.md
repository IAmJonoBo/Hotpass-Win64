---
title: How-to — use GitHub Copilot or Codex with Hotpass
summary: Configure Copilot Chat or Codex Cloud to run Hotpass pipelines through the MCP toolchain.
last_updated: 2025-11-03
---

# Use GitHub Copilot or Codex with Hotpass

Follow this guide when you hook Hotpass into an AI assistant. You reuse the same tooling described in `AGENTS.md`, but this page calls out the concrete editor settings and verification steps.

## 1. Prepare dependencies

1. Sync the extras required by agents:

   ```bash
   HOTPASS_UV_EXTRAS="dev orchestration enrichment" bash ops/uv_sync_extras.sh
   ```

2. Export runtime credentials so the agent can call providers without embedding secrets in prompts:

   ```bash
   export HOTPASS_GEOCODE_API_KEY=...
   export HOTPASS_ENRICH_API_KEY=...
   ```

3. Run the sanity check from `AGENTS.md` to confirm network access:

   ```bash
   python - <<'PY'
   import requests
   response = requests.get("https://pypi.org", timeout=10)
   print("net ok", response.status_code)
   PY
   ```

## 2. Configure the MCP server

Create `.mcp.json` (root or `.vscode/`) with the stdio server declaration:

```json
{
  "version": "0.1",
  "servers": [
    {
      "name": "hotpass",
      "command": ["uv", "run", "python", "-m", "hotpass.mcp.server"],
      "transport": "stdio",
      "env": {
        "HOTPASS_UV_EXTRAS": "dev orchestration enrichment",
        "HOTPASS_MCP_DEFAULT_ROLE": "operator"
      }
    }
  ]
}
```

Restart Copilot Chat or your MCP client so it picks up the new server.

## 3. Verify tool discovery

In Copilot Chat:

```
/mcp list
```

You should see `hotpass.refine`, `hotpass.enrich`, `hotpass.qa`, `hotpass.setup`, `hotpass.net`, `hotpass.ctx`, `hotpass.env`, `hotpass.aws`, `hotpass.arc`, `hotpass.explain_provenance`, `hotpass.plan.research`, `hotpass.crawl`, `hotpass.pipeline.supervise`, `hotpass.ta.check`.

If discovery fails, check the server logs in the integrated terminal and confirm `uv run hotpass overview` works locally.

## 4. Run a pipeline via Copilot Chat

Prompt Copilot:

```
Run hotpass.refine with input_path=./data output_path=./dist/refined.xlsx profile=aviation archive=true allow_network=false.
```

Copilot forwards the request to the MCP server. Validate the artefacts:

- `dist/refined.xlsx`
- `dist/refined.xlsx.archive.zip` (if `--archive` was true)
- Updated quality report in `dist/reports/`

Ask Copilot to upload or summarise the outputs so reviewers can confirm success.

## 5. Clean up

- Stop tunnels you created during the run:

  ```bash
  uv run hotpass net down --all
  ```

- Remove secrets from your shell session when you finish (`unset HOTPASS_GEOCODE_API_KEY`).

## 6. Troubleshooting

| Symptom | Fix |
| ------- | --- |
| `/mcp list` returns no tools | Ensure the server is running and `HOTPASS_UV_EXTRAS` matches your synced extras. |
| Tool call blocked with “role denied” | Export `HOTPASS_MCP_DEFAULT_ROLE=operator` (or adjust your policy file). |
| Enrichment fails due to network restrictions | Confirm `FEATURE_ENABLE_REMOTE_RESEARCH=1` and `ALLOW_NETWORK_RESEARCH=1` before requesting network access. |
| CLI profile not found | Pass `profile_search_path` in the tool arguments (`apps/data-platform/hotpass/profiles`). |

You now have Copilot or Codex orchestrating Hotpass with the same privileges and guardrails as a human operator.
