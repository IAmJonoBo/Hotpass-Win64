#!/bin/sh
cat <<MSG
==============================================================
Hotpass Compose stack starting…
Docs: http://localhost:3001/docs/e2e-walkthrough.md
Prefect: ${PREFECT_API_URL:-http://prefect:4200/api}
Marquez: ${OPENLINEAGE_URL:-http://marquez:5000/api/v1}
If any health checks stay red, run `prefect profile import prefect/profiles/local.toml`
and re-run `uv run hotpass env --target local` once the services are up.
==============================================================
MSG
