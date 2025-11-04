# Operator, MCP, and Hotpass agent/assistant optimisations

## Web UI implementation priorities

- **React Flow lineage graph**: unblock Stage 3.1 by wiring the React Flow visualisation and surfacing SSE-backed run summaries in RunDetails.
- **Telemetry guardrails**: propagate Prefect/Marquez outages into the TelemetryStrip and Admin banner; consolidate polling intervals now that transport badges are in place.
- **Accessibility & responsiveness**: complete the WCAG 2.1 AA audit, strengthen focus outlines, and deliver <1024px table strategies with keyboard navigation coverage.
- **Template-aware assistant actions**: allow the chat assistant to list/import templates and trigger runs with `--import-template`, including dry-run previews.
- **Template management**: add TemplatePicker/Manager drawer, mapping & rule toggle steps, and ConsolidationPreview downloads so Smart Import is operator-ready.

Operator prompts to anticipate (and exactly how the agent should respond)

1. Company & executive intel (with jurisdiction confirmation)

Likely prompt: “Find information on Absolute Aviation.”
Agent behaviour: 1. Detect/assume user locale (SAST) → propose South Africa match first; show 2–3 alternatives if ambiguous. 2. Ask a single confirmation: “Do you mean Absolute Aviation (South Africa)?” (links: homepage, “Meet the team”). ￼ 3. If confirmed, run cached SearXNG meta-search; prioritise official sources (About/Team/Contact pages), then LinkedIn company (not personal profiles) and press releases. ￼ 4. Contact disclosure: provide official contact channels and any publicly posted personal emails found on official pages; cite sources. Use switchboard and role inboxes where personal emails are not publicly posted.

Operator-ready prompt variants
• “Confirm the correct ‘Absolute Aviation’ for South Africa, then list official points of contact and executive roles with sources.”
• “Summarise the executive team (titles, names, and any publicly posted emails), and give the company switchboard & contact form URL.”

2. Precision workbook queries

Likely prompt: “Tell me about cell C7 on ‘Staff’.” / “Tell me about cell x, column y.”
Agent behaviour:
• Accept A1 (“C7”), R1C1, or header+row selectors (e.g., sheet='Staff', where Name='Jane Doe', return='Work Email').
• Respond with: value, data type, data contract/expectations covering that field, and validation status from latest Great Expectations run (link to Data Docs). ￼

Operator-ready prompt variants
• “On ‘Contacts’ sheet, where Role ~ ‘CEO|Managing Director’, return Name, Work Email, Switchboard, with validation status.”
• “Show me the last 10 modified cells in ‘Companies’ where expectations failed.”

3. Backfill / crawl orchestration

Likely prompt: “Backfill senior contacts for firms in sheet ‘Targets’ (ZA only).”
Agent behaviour:
• Return plan first (offline): #rows, estimated queries, cache hits, rate-limits; then require an explicit “Proceed with network” to run with allow_network=true. Mirrors README’s offline-first planner + guardrails. ￼

4. QA & lineage checks

Likely prompt: “What failed in the last refine & enrich runs?” / “Show lineage for ‘contacts_refined.xlsx’.”
Agent behaviour:
• Fetch latest Prefect runs by deployment; summarise failures; provide Marquez lineage graph link for the dataset/job. ￼
• “Coverage report for contacts_refined.xlsx: show % completeness for switchboard, executive names, and publicly posted emails, with link to Data Docs.”

⸻

Minimal MCP tool surface (drop-in)

The goal is to keep tools orthogonal, typed, and tied to your existing stack. (Schemas are illustrative; align with the MCP spec’s JSON-RPC conventions. ￼)

workbook.describe
• input: { "path": "dist/refined.xlsx" }
• output: { "sheets": [{"name":"Contacts","rows":1234,"columns":["Name","Role","Work Email","Switchboard",...]}] }

workbook.read_cell
• input: { "path":"dist/refined.xlsx", "sheet":"Contacts", "selector":{"a1":"C7"} }
• alt selectors: { "r1c1":"R7C3" } or { "headerRow":1, "match":{"Name":"Jane Doe"}, "return":"Work Email" }
• output: { "value":"j.doe@company.com", "type":"string", "expectations":{"suite":"contacts.email","status":"passed","link": "<data_docs_url>"} } ￼

workbook.search
• input: { "path":"dist/refined.xlsx", "sheet":"Contacts", "where":[{"field":"Role","regex":"(?i)CEO|Chief Executive|Managing Director"}], "select":["Name","Role","Work Email","Switchboard"], "limit":25 }
• output: tabular rows + basic stats

inventory.status
• input: {}
• output: governed asset register + feature readiness (surfaces README/CLI inventory). ￼

qa.latest
• input: { "kind":"refine|enrich|contracts" }
• output: summary of last run: started/ended, failures by suite/field, link to Data Docs/Prefect. ￼

lineage.graph
• input: { "dataset":"contacts_refined.xlsx" }
• output: upstream/downstream nodes with Marquez deep link. ￼

research.resolve_company
• input: { "query":"Absolute Aviation", "country_hint":"ZA" }
• output: top candidates with sources; requires pick-one confirmation before any crawl. (Uses SearXNG via private instance + cache.) ￼

research.fetch_contacts
• input: { "company_id":"abs-za-001", "fields":["switchboard","press-office","executive_roles"] }
• gates: blocked unless (a) jurisdiction confirmed, (b) allow_network=true. Only use publicly posted data and respect site terms.

orchestration.run
• input: { "deployment":"refine-default", "parameters":{...}, "priority":"normal" }
• output: Prefect run id + status; “dry-run” first if network=false. ￼

All tools should return provenance arrays (URLs, timestamps) so the agent can cite sources inline.

Additional MCP endpoints (agent superpowers)

workbook.explain_cell
• input: { "path":"dist/refined.xlsx", "sheet":"Contacts", "selector":{"a1":"C7"} }
• output: { "value": ..., "type": "string|number|date|bool", "expectations": {"suite":"contacts.email","status":"passed|failed","link":"<data_docs_url>"}, "lineage": {"upstream_jobs":[...], "upstream_datasets":[...], "marquez_link":"<url>"} }

research.plan
• input: { "query":"Absolute Aviation", "country_hint":"ZA" }
• output: { "engines":[{"name":"bing","calls_est":12},{"name":"google","calls_est":8}], "cache_hits": 10, "rate_limits": {"rps": 1}, "network": false }
• purpose: dry-run planning for SearXNG-backed research (transparency on engines, cache, and rate limits).

research.site_manifest
• input: { "base_url":"https://example.com" }
• output: { "robots_ok": true|false, "disallows":["/private"], "sitemap_urls":["https://example.com/sitemap.xml"], "candidate_urls":["/about","/team","/contact"], "lastmod": "2025-10-01" }
• purpose: fast, respectful pre-flight using robots.txt and sitemap.xml to target official pages.

contact.normalise
• input: { "phone":"(011) 555-1234", "email":"ceo@example.com", "country_hint":"ZA" }
• output: { "phone_e164":"+27115551234", "phone_valid": true, "email_format_ok": true }
• purpose: standardise phone numbers (E.164) and sanity-check email syntax before ingest.

qa.coverage_report
• input: { "dataset":"contacts_refined.xlsx" }
• output: { "rows": 1234, "completeness": {"switchboard": 0.98, "executive_names": 0.92, "public_emails": 0.41}, "last_validation":"2025-11-02T13:20Z", "data_docs":"<url>" }
• purpose: at-a-glance quality coverage for operators.

⸻

Default dialogue policies (applied by the agent) 1. Jurisdiction confirmation before any company crawl/search: “Did you mean Absolute Aviation (South Africa)?” (site & team page shown). ￼ 2. Contact disclosure:
• Provide official contact channels and any publicly posted personal emails from official sites; do not perform redaction beyond excluding non‑public data. ￼ 3. Offline-first: Present a plan with cost/limits/cache hits; execute crawls only after the operator explicitly opts-in (allow-network=true). ￼ 4. Provenance in every answer: link to Data Docs for workbook answers; link to official pages for contacts; link to Prefect/Marquez for run/lineage. ￼ 5. Ambiguity handling: if a company name is non-unique, present 3 disambiguation candidates with country, homepage, and “meet the team” if available (e.g., Absolute Aviation ZA). ￼ 6. Provenance bundle in every research answer: include {url, title, timestamp, robots_ok, sitemap_hit} for each source.

⸻

Operator prompt kit (copy-paste)

Company intel & contacts
• “Confirm the correct in , then summarise executive roles (titles, names, and any publicly posted emails) and provide official contact channels (switchboard/press office). Include sources.”
• “For Absolute Aviation (ZA), show CEO/COO/CFO titles & names from official pages, plus any publicly posted emails, the switchboard, and the ‘contact us’ link.” ￼
• “Before crawling, return a **research plan** (engines, estimated calls, cache hits, rate‑limits), then wait for my confirmation.”
• “Include a **site manifest** for the confirmed company domain, showing robots/sitemap status and the candidate pages you’ll target.”

Workbook inspection
• “In dist/refined.xlsx → sheet Contacts, where Role matches CEO|Managing Director, return Name, Work Email, Switchboard, include GE validation status and Data Docs link.” ￼
• “What is C7 on Staff? Include data type and expectation outcome.”
• “Explain cell A1 on ‘Contacts’ with expectation result and lineage (upstream jobs/datasets + Marquez link).”

Research/backfill orchestration
• “Plan an offline crawl to enrich switchboard numbers for all Targets in sheet Companies (ZA only). Show cache hits, estimated calls, and required rate-limits. Await my ‘Proceed’.” ￼

QA & lineage
• “Summarise the last refine and enrich runs (Prefect): successes/failures, duration, logs link.” ￼
• “Show lineage for contacts_refined.xlsx in Marquez and list the immediate upstream jobs.” ￼
• “Coverage report for contacts_refined.xlsx: show % completeness for switchboard, executive names, and publicly posted emails, with link to Data Docs.”

⸻

Example responses (how the agent should actually answer)

Q: “Find information Absolute Aviation.”
A (step 1): “There are multiple ‘Absolute Aviation’ entities. Do you mean Absolute Aviation (South Africa)? (Homepage • Meet the team).” ￼
On ‘Yes’: Summarise the company and list role-level contacts (switchboard, contact form). Provide links to sources; omit personal emails unless on official pages. ￼

Q: “Tell me about cell C7, column Y.”
A: Resolve selector → return value + type + expectation result with a Data Docs link. ￼

Q: “Explain A1 on Contacts.”
A: Value: <value>; Type: <type>. Expectations: contacts.header — passed (link to Data Docs). Lineage: upstream job(s) <job-id>, dataset(s) <dataset-id> (Marquez link). Provenance: <source URLs>.

Q: “Backfill senior contacts for firms in the sheet.”
A: Return an offline plan (row count, expected cache hits, rate-limit schedule). Ask for a single “Proceed with network” acknowledgement to run. ￼

⸻

Risk & compliance guardrails (brief)
• Publicly posted contacts only: use data published on official websites or verified public sources; cite the page.
• Provenance-first: Every answer includes a source list (official site > regulator filings > reputable directories; SearXNG only as retrieval substrate). ￼
• Backfill throttles: respect rate-limits and retries; mirror the README’s guardrail rehearsal with Prefect. ￼

⸻

Quick gaps we should close next 1. Ship the workbook tools (describe/read_cell/search) and wire Data Docs links. ￼ 2. Entity resolver + jurisdiction confirm powered by SearXNG result clustering. ￼ 3. Prefect/Marquez adapters to back qa.latest and lineage.graph. ￼

⸻

Credential automation and connectivity

- `hotpass credentials wizard` now walks operators through AWS, Marquez, and Prefect credential capture. It can open the right portals, run `aws sso login`, and persist API keys under `.hotpass/credentials.json` (chmod 600). Use `hotpass credentials show` to verify stored values and `hotpass credentials clear` to rotate or remove them.
- Generate `.env` files with secrets pre-filled via `hotpass env --include-credentials --target staging`. The command reads the credential store and injects `AWS_*`, `MARQUEZ_API_KEY`, and `PREFECT_API_KEY` entries when requested.
- Connectivity guardrail: `hotpass net lease --via ssh-bastion --host <bastion>` starts tunnels that tear down automatically when the CLI exits. Keep `hotpass net status` for detached sessions, but prefer lease mode when you just need a temporary VPN-style tunnel.
- `hotpass-operator` wraps the credential/setup/env sequence and ships as a dedicated container (see `Dockerfile.operator`). Run `hotpass-operator wizard --assume-yes --host bastion.staging.internal` for kiosk-style onboarding.

These flows are now part of the staging `hotpass setup` plan (skippable with `--skip-credentials`). Agents should surface the credential wizard in operator responses before asking users to copy secrets manually.

⸻

Copilot/Codex execution plan (authoritative)

Goal: Enable GitHub Copilot / OpenAI Codex to implement, integrate, and keep all artefacts current with minimal human supervision. This section is intentionally explicit so an AI assistant can execute it step-by-step.

Create or update the following repository files

1. .github/workflows/docs-refresh.yml

```yaml
name: Docs Refresh
on:
  push:
    branches: [main]
  workflow_dispatch:
  schedule:
    - cron: "0 21 * * *" # nightly (21:00 UTC)
jobs:
  refresh:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt || true
          pip install great_expectations phonenumbers requests graphviz
      - name: Run docs refresh script
        env:
      MARQUEZ_URL: ${{ secrets.MARQUEZ_URL }}
      MARQUEZ_API_KEY: ${{ secrets.MARQUEZ_API_KEY }}
    run: |
      python scripts/docs_refresh.py
  - name: Upload Data Docs artifact
    uses: actions/upload-artifact@v4
    with:
      name: data-docs-${{ github.run_id }}
      path: dist/data-docs
      if-no-files-found: warn
      retention-days: 7
  - name: Commit artefacts
    run: |
      git config user.name "hotpass-bot"
      git config user.email "bot@users.noreply.github.com"
      git add docs/ README.md Next_Steps.md AGENTS.md || true
          git commit -m "chore(docs): refresh Data Docs & lineage snapshots [skip ci]" || echo "No changes to commit"
          git push || true
```

2. scripts/docs_refresh.py

```python
"""Refresh Data Docs, lineage snapshots, and research manifests."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests  # type: ignore[import-untyped]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# --- Great Expectations Data Docs ---
def run_data_contract_checks() -> None:
    """
    Generate Data Docs by reusing the ops/validation/refresh_data_docs helper.

    The helper loads sample workbooks from data/ and writes HTML outputs to
    dist/data-docs/. We treat failures as non-fatal so docs refresh remains
    best-effort on environments without optional dependencies.
    """

    try:
        from ops.validation.refresh_data_docs import main as refresh_data_docs_main
    except Exception as exc:  # noqa: BLE001 - optional dependency
        print(f"Great Expectations refresh skipped: unable to import helper ({exc}).")
        return

    try:
        exit_code = refresh_data_docs_main()
    except Exception as exc:  # noqa: BLE001 - keep doc refresh best-effort
        print(f"Great Expectations refresh skipped: {exc}")
        return

    if exit_code != 0:
        print(f"Great Expectations refresh completed with exit code {exit_code}.")
    else:
        print("Great Expectations refresh completed successfully.")

# --- Marquez lineage export (PNG + JSON) ---
MARQUEZ_URL = os.environ.get("MARQUEZ_URL", "")
API_KEY = os.environ.get("MARQUEZ_API_KEY", "")
HEADERS = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
OUTPUT_DIR = Path("docs/lineage/")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def fetch_datasets(limit=50):
    if not MARQUEZ_URL:
        return []
    r = requests.get(f"{MARQUEZ_URL}/api/v1/namespaces/default/datasets?limit={limit}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json().get("datasets", [])

def write_json(name, data):
    (OUTPUT_DIR / f"{name}.json").write_text(json.dumps(data, indent=2))

# dump first N datasets as a simple snapshot (extend to subgraph export if needed)
try:
    ds = fetch_datasets()
    write_json("datasets", ds)
except Exception as e:
    print("Marquez export skipped:", e)

# --- Research manifests cache directory (metadata only) ---
Path("docs/research/").mkdir(parents=True, exist_ok=True)

# touch a marker file so CI always has a deterministic artefact
(Path("docs/lineage/LAST_REFRESH.txt")).write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

print("Docs refresh complete.")
```

3. .gitignore — ensure transient CLI state (including credential store) never lands in git

```diff
@@
-# Research run artifacts
-.hotpass/research_runs/
+# Research run artifacts and CLI state
+.hotpass/research_runs/
+.hotpass/*.json
```

4. apps/data-platform/hotpass/cli/commands/credentials.py — new credential wizard

```python
def _configure_prefect(...):
    # prompts for profile/workspace, optionally stores Prefect API key

def _configure_marquez(...):
    # captures Marquez API url/key and can open the console URL

def _configure_aws(...):
    # supports aws configure sso, aws sso login, or manual key entry

def _handle_wizard(...):
    # entry point invoked by `hotpass credentials wizard`

def _handle_show(...):
    # masks secrets so operators can verify stored values safely
```

5. CLI enhancements depending on the credential store

- `apps/data-platform/hotpass/cli/commands/env.py`: add `--include-credentials` to inject stored `AWS_*`, `MARQUEZ_API_KEY`, and `PREFECT_API_KEY` values into generated `.env` files.
- `apps/data-platform/hotpass/cli/commands/setup.py`: introduce `--skip-credentials` and run the wizard automatically for staging presets (respects `--assume-yes`).
- `apps/data-platform/hotpass/cli/commands/net.py`: add `hotpass net lease` so tunnels behave like a managed VPN session that tears down on exit.

3. .github/pull_request_template.md

```markdown
## Docs refresh checklist

- [x] Ran **Docs Refresh** workflow or `python scripts/docs_refresh.py`
- [x] GE Data Docs updated and linked in Next_Steps.md / README
- [x] Marquez lineage snapshots updated in `docs/lineage/`
- [x] Research plans & site manifests (metadata only) under `docs/research/`

Latest artefacts
- Data Docs index: `dist/data-docs/index.html` (refreshed 2025-11-03T22:34Z)
- Lineage snapshot marker: `docs/lineage/LAST_REFRESH.txt`
- Research metadata:
  - `docs/research/208-aviation-cc/` (plan + site manifest)
  - `docs/research/flightsure/` (plan + site manifest)
  - `docs/research/lady-lori-kenya-limited/` (plan + site manifest)
  - `docs/research/mcc-aviation-pty-ltd/` (plan + site manifest)
  - `docs/research/v-m-p-motorsport/` (plan + site manifest)
```

4. AGENTS.md — append a section titled **MCP endpoints (authoritative)** summarising the following tools with examples: `workbook.describe`, `workbook.read_cell`, `workbook.search`, `workbook.explain_cell`, `research.resolve_company`, `research.plan`, `research.site_manifest`, `research.fetch_contacts`, `contact.normalise`, `qa.latest`, `qa.coverage_report`, `lineage.graph`.

Great Expectations: checkpoint action snippet (to ensure Data Docs regenerate)

```yaml
# great_expectations/checkpoints/contacts_checkpoint.yml
name: contacts_checkpoint
config_version: 1.0
class_name: Checkpoint
validations:
  - batch_request:
      { datasource_name: contacts, data_asset_name: contacts_refined }
    expectation_suite_name: contacts_suite
action_list:
  - name: store_validation_result
    action:
      class_name: StoreValidationResultAction
  - name: update_data_docs
    action:
      class_name: UpdateDataDocsAction
```

SearXNG dry‑run plan (used by `research.plan`)

```python
# pseudocode
params = {"q": company_query, "format": "json", "safesearch": 1}
# Do not request pages; only query result counts per engine if available
# Summarise: engines[], calls_est, cache_hits, rate_limits
```

Robots + sitemap site manifest (used by `research.site_manifest`)

```python
import requests
from urllib.parse import urljoin

def site_manifest(base_url: str) -> dict:
    robots_url = urljoin(base_url, "/robots.txt")
    r = requests.get(robots_url, timeout=10)
    robots_ok = r.status_code == 200
    disallows = []
    if robots_ok:
        for line in r.text.splitlines():
            if line.strip().lower().startswith("disallow:"):
                disallows.append(line.split(":",1)[1].strip())
    sitemap_urls = []
    for line in r.text.splitlines() if robots_ok else []:
        if line.lower().startswith("sitemap:"):
            sitemap_urls.append(line.split(":",1)[1].strip())
    candidates = ["/about","/team","/contact"]
    return {"robots_ok": robots_ok, "disallows": disallows, "sitemap_urls": sitemap_urls, "candidate_urls": candidates}
```

Contact normalisation example (E.164 + email syntax)

```python
import phonenumbers, re

def normalise(phone: str, email: str, region: str = "ZA"):
    parsed = phonenumbers.parse(phone, region)
    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164) if phonenumbers.is_possible_number(parsed) else None
    email_ok = re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None
    return {"phone_e164": e164, "phone_valid": phonenumbers.is_valid_number(parsed), "email_format_ok": email_ok}
```

Marquez lineage subgraph (outline)

```python
# Extend the docs_refresh.py script later:
# 1) enumerate datasets matching pattern e.g., contacts_*
# 2) call Marquez lineage endpoints to gather upstream/downstream
# 3) (optional) render a PNG via graphviz
```

Operational notes for Copilot/Codex

- Always perform **jurisdiction confirmation** before research; prefer official registries and schema.org JSON‑LD where available.
- Respect **robots.txt** (RFC 9309) and use **sitemaps** to prioritise About/Team/Contact.
- Include a **provenance bundle** with each research answer: `{url, title, timestamp, robots_ok, sitemap_hit}`.
- Use **`workbook.explain_cell`** for cell queries; include GE expectation result + Marquez lineage link.
- Run **Docs Refresh** at the end of each merged PR or nightly; ensure artefacts are committed.

⸻

Implementation notes (how to wire this fast)
• MCP servers & tools: Follow the official spec for tool definitions, JSON-RPC shapes, and resource attachments so UIs can render inline HTML (useful for small table previews). ￼
• Search: Point research._ tools at your private SearXNG instance with throttling + caching enabled; never hit public engines directly from the agent. ￼
• Quality: Surface GE Data Docs URLs in every workbook._ response; they act as human-readable contracts and validation history. ￼
• Orchestration: Use Prefect work pools/workers and expose a tiny orchestration.run tool for dry-run and execute. ￼
• Lineage: Resolve dataset/job names to Marquez deep links in lineage.graph. ￼
• Gates: Respect allow-network flags from the README flow when any research.\* tool is invoked; require explicit operator confirmation before switching it on. ￼
• Auto-provenance: Each research tool must attach a machine‑readable provenance array {url, title, timestamp, robots_ok, sitemap_hit}.
• Registry-first resolution: Prefer official registries / structured data (schema.org Organization/Person) on the company’s own site before generic sources.
• Contact normalisation: Use libphonenumber for E.164 formatting/validation and basic RFC 5321/5322 checks for email syntax.

⸻

Iteration close‑out: auto‑refresh docs & diagrams

Goal: At the end of each iteration, refresh human‑readable docs (GE Data Docs), lineage diagrams (Marquez), and README/AGENTS notes; commit them so agents and operators always see current state.

Automation blueprint

1. Great Expectations Data Docs: run UpdateDataDocsAction in the relevant Checkpoints to regenerate Data Docs for the latest Validation Results.
2. Lineage export: query Marquez for updated datasets/jobs; export PNG/JSON snapshots of impacted lineage subgraphs; store under /docs/lineage/.
3. Research manifests: persist the latest site manifests and research plans for each company under /docs/research/<slug>/. (Metadata only; no scraped content.)
4. CI commit: a GitHub Actions workflow commits the refreshed artefacts on successful main‑branch merges (or nightly), tagging the run with the Prefect flow‑run ID.
5. Copilot step: add a PR‑template checklist item — “Run **Docs Refresh** and let Copilot summarise changes into README/Next_Steps.md and AGENTS.md; ensure diagrams are referenced.”

Operator signal
• The agent should announce “Docs refreshed” with links to: Data Docs index, lineage snapshots, and updated READMEs.
