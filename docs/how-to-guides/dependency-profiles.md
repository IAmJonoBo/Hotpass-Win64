---
title: Choose dependency profiles
summary: Install only the uv extras you need while keeping runners reproducible and firewall-friendly.
last_updated: 2025-11-02
---

Hotpass ships several optional dependency “extras” (docs, geospatial, compliance, dashboards, etc.). Use the guidance below to keep ephemeral runners fast while ensuring every task has the libraries it needs before the firewall comes up.

## Quick reference

| Profile          | Extras string                                                   | Includes                                      |
| ---------------- | --------------------------------------------------------------- | --------------------------------------------- |
| `core` (default) | `dev orchestration`                                             | CLI, Prefect orchestration, QA tooling.       |
| `docs`           | `dev docs`                                                      | Sphinx, MyST, linkcheck dependencies.         |
| `geospatial`     | `dev orchestration geospatial`                                  | GeoPandas, Geopy, spatial utilities.          |
| `compliance`     | `dev orchestration compliance`                                  | Presidio analyzers/anonymisers and helpers.   |
| `enrichment`     | `dev orchestration enrichment`                                  | Crawling/browser extras for enrichment flows. |
| `full`           | `dev orchestration enrichment geospatial compliance dashboards` | Full stack for governance and demos.          |

Each profile is a space-separated string that the helper script converts into `uv sync --extra …` flags.

## Local or sandboxed runners

```bash
python -m pip install -U uv
uv venv
export HOTPASS_UV_EXTRAS="dev orchestration geospatial"
bash ops/uv_sync_extras.sh
```

### Using Make targets

For day-to-day development you can rely on the helper target:

```bash
make sync EXTRAS="dev orchestration"
```

Override `EXTRAS` with the space-separated list you need. The target wraps `ops/uv_sync_extras.sh` so CI and local runs stay consistent.
The script validates the list, echoes the chosen extras, and executes `uv sync --frozen` with the correct switches. If you prefer pip editable installs, mirror the same extras:

```bash
python -m pip install -U pip
python -m pip install -e ".[dev,orchestration,geospatial]"
```

## Codex Cloud tasks

1. In the **Setup script** section choose the uv block and prefix it with the extras you need:

   ```bash
   python -m pip install -U uv
   uv venv
   export HOTPASS_UV_EXTRAS="dev orchestration compliance"
   bash ops/uv_sync_extras.sh
   ```

2. Declare all required extras before the firewall enable step. Once network access is dropped, additional `uv sync` runs will fail.

3. Note the profile you selected in the task hand-off so reviewers know which optional stacks were installed.

## GitHub Actions

The main pipeline (`.github/workflows/process-data.yml`) now exposes a `uv_extras` input on the `workflow_dispatch` trigger. When launching a manual run, supply a space-separated list:

```yaml
uv_extras: "dev orchestration geospatial"
```

For push/PR builds the workflow falls back to the default `dev orchestration` profile. Each job exports the list to `ops/uv_sync_extras.sh`, keeping every stage aligned.

## Troubleshooting

- **Missing library after firewall enablement** — rerun the job with the correct extras string or prefetch wheels in the setup stage.
- **Typos in the extras string** — `ops/uv_sync_extras.sh` rejects empty values but won’t validate the names. Watch the step logs for the final `uv sync` command to confirm the extras applied.
- **Pip editable installs still required** — pass the same extras in the `.[extra1,extra2]` syntax; ensure the firewall remains open long enough to download wheels.
- **New dependency surfaced during a run** — add the package to the appropriate optional extra in `pyproject.toml`, update `HOTPASS_UV_EXTRAS` (or run `make sync EXTRAS="…"`) to include that extra, and, if CI relies on it, extend the corresponding workflow input default so ephemeral runners and Codex agents pick it up automatically.
- **Cache busting** — if you need to force a rebuild, add `--no-cache` to the `uv sync` invocation in the helper script temporarily or clear the runner cache.
