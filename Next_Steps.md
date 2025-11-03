# Operator, MCP, and Hotpass agent/assistant optimisations

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
• Provide official contact channels and any publicly posted personal emails from official sites; do not perform redaction beyond excluding non‑public data. ￼ 3. Offline-first: Present a plan with cost/limits/cache hits; execute crawls only after the operator explicitly opts-in (allow-network=true). ￼ 4. Provenance in every answer: link to Data Docs for workbook answers; link to official pages for contacts; link to Prefect/Marquez for run/lineage. ￼ 5. Ambiguity handling: if a company name is non-unique, present 3 disambiguation candidates with country, homepage, and “meet the team” if available (e.g., Absolute Aviation ZA). ￼
6. Provenance bundle in every research answer: include {url, title, timestamp, robots_ok, sitemap_hit} for each source.

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
1) Great Expectations Data Docs: run UpdateDataDocsAction in the relevant Checkpoints to regenerate Data Docs for the latest Validation Results.
2) Lineage export: query Marquez for updated datasets/jobs; export PNG/JSON snapshots of impacted lineage subgraphs; store under /docs/lineage/.
3) Research manifests: persist the latest site manifests and research plans for each company under /docs/research/<slug>/. (Metadata only; no scraped content.)
4) CI commit: a GitHub Actions workflow commits the refreshed artefacts on successful main‑branch merges (or nightly), tagging the run with the Prefect flow‑run ID.
5) Copilot step: add a PR‑template checklist item — “Run **Docs Refresh** and let Copilot summarise changes into README/Next_Steps.md and AGENTS.md; ensure diagrams are referenced.”

Operator signal
• The agent should announce “Docs refreshed” with links to: Data Docs index, lineage snapshots, and updated READMEs.
