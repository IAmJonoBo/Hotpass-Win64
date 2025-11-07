---
title: How-to — self-host the Hotpass stack
summary: Run Prefect, Marquez, OpenTelemetry, MinIO, LocalStack, ARC, and LLM sidecars locally so Hotpass can operate without cloud dependencies.
last_updated: 2025-11-07
---

Hotpass ships everything you need to operate locally. Use this guide to bring up the
self-hosted stack, wire the CLI to those services, and keep cloud endpoints as an
opt-in override.

## Executive summary

- **Run everything locally first.** `deploy/docker/docker-compose.yml` already includes
  Prefect, Marquez, the Hotpass web UI, and now MinIO, LocalStack, SearXNG, an
  OpenTelemetry Collector, and an optional Ollama sidecar. Assemble your stack with a
  single Compose command and keep VPN/bastion-only workflows as the exception.
- **Self-host the core services.** Prefect, Marquez (OpenLineage), OTLP, and S3 storage
  all have first-party Docker paths. Configure Hotpass via environment variables so
  swapping endpoints is just a profile change.
- **Where AWS is unavoidable, fake it.** Pair MinIO (for S3) with LocalStack (for other
  AWS APIs) so staging and dev behave the same without real cloud credentials.
- **Runners and LLMs stay local.** ARC runs happily on kind/minikube and the Hotpass
  Docker profile can launch Ollama for fully offline LLM calls. Only point to Groq/
  OpenRouter when you explicitly want a cloud provider.

## Bring up the stack

```bash
cd deploy/docker
# Standard services: Prefect, Marquez, MinIO, LocalStack, SearXNG, OTel, Hotpass web
docker compose up -d --build
# Optional LLM sidecar (Ollama)
docker compose --profile llm up -d
```

Services and ports:

| Service                | Purpose                                | Ports (host) | Environment variable                    |
|------------------------|----------------------------------------|--------------|-----------------------------------------|
| Prefect server         | Flow orchestration & UI                | 4200         | `PREFECT_API_URL=http://127.0.0.1:4200/api` |
| Marquez                | OpenLineage backend                    | 5002→5000    | `OPENLINEAGE_URL=http://127.0.0.1:5002/api/v1` |
| OTEL collector         | Trace/metric fan-out                   | 4317, 4318   | `OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318` |
| MinIO + Console        | S3-compatible object storage           | 9000, 9001   | `HOTPASS_S3_ENDPOINT=http://127.0.0.1:9000` |
| LocalStack             | AWS APIs (SQS/SNS/etc.) for parity     | 4566         | `LOCALSTACK_ENDPOINT=http://127.0.0.1:4566` |
| SearXNG                | Meta-search backend for enrichment     | 8080         | `HOTPASS_SEARX_URL=http://127.0.0.1:8080` |
| Ollama (profile `llm`) | Local LLM serving                      | 11434        | `HOTPASS_LLM_BASE_URL=http://127.0.0.1:11434` |

Hotpass automatically defaults to localhost endpoints, but you can generate a matching
`.env` file with:

```bash
uv run hotpass env --target local --prefect-url http://127.0.0.1:4200/api \
  --openlineage-url http://127.0.0.1:5002/api/v1 --force
```

Add `--include-credentials` if you previously ran `hotpass credentials wizard` and
want API keys injected.

## Prefect (flows/orchestration)

1. Start the Prefect server via Compose (already part of the stack).
2. Point your CLI at the local API:

   ```bash
   prefect profile use hotpass-local || prefect profile create hotpass-local
   prefect config set PREFECT_API_URL="http://127.0.0.1:4200/api"
   ```

3. Run flows as usual:

   ```bash
   uv run hotpass refine --profile generic --archive
   uv run hotpass qa all --prefect-profile hotpass-local
   ```

When you do need to target staging, keep using `hotpass setup`, `hotpass net lease`, and
`hotpass ctx init` so the tunnel metadata still feeds `hotpass env`.

## Lineage (OpenLineage → Marquez)

- Marquez is baked into the Compose file. Visit `http://127.0.0.1:5003` for the admin
  UI and `http://127.0.0.1:5002/api/v1` for the API.
- Configure OpenLineage via either of the following env blocks:

  ```bash
  export OPENLINEAGE_URL=http://127.0.0.1:5002
  # or the dynamic transport syntax
  export OPENLINEAGE__transport__type=http
  export OPENLINEAGE__transport__url=http://127.0.0.1:5002
  ```

The CLI automatically records lineage when `OPENLINEAGE_URL` is set.

## Observability (OTel exporter/collector)

The OTel collector container exposes the default OTLP gRPC (4317) and HTTP (4318)
ports. To publish traces/metrics:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
export HOTPASS_TELEMETRY_ENABLED=1
```

You can fan out to Jaeger, Prometheus, or any backend supported by the collector by
editing `deploy/docker/otel-collector-config.yaml`.

## Object storage and AWS parity

- **MinIO** serves S3-compatible storage. Each compose startup provisions the
  `hotpass-artifacts` bucket using the MinIO client container.
- Point Prefect blocks or application code at MinIO:

  ```python
  from prefect_aws.s3 import S3Bucket
  bucket = S3Bucket(
      bucket_name="hotpass-artifacts",
      aws_access_key_id="hotpass",
      aws_secret_access_key="hotpass123",
      endpoint_url="http://127.0.0.1:9000",
  )
  ```

- **LocalStack** handles additional AWS APIs. Export `LOCALSTACK_ENDPOINT` (or the SDK-
  specific environment variable) and keep the AWS profile pointed at `localhost` when
  you need parity testing.

## Research/enrichment networking

- Offline remains the default (`--allow-network=false`).
- For deterministic but richer results, point the research backend at the bundled
  SearXNG instance: `HOTPASS_SEARX_URL=http://127.0.0.1:8080`.
- When enabling remote enrichment, combine `FEATURE_ENABLE_REMOTE_RESEARCH=1` and
  `ALLOW_NETWORK_RESEARCH=1` with the rate limits baked into your profile.

## GitHub ARC runners

- Use kind or minikube to host ARC locally:

  ```bash
  kind create cluster --name hotpass-arc
  helm repo add actions-runner-controller https://actions-runner-controller.github.io/actions-runner-controller
  helm upgrade --install arc actions-runner-controller/actions-runner-controller \
    --namespace arc --create-namespace
  kubectl apply -f infra/arc/runner-scale-set.yaml
  ```

- The manifests under `infra/arc/` work unchanged; only the kube-context swaps when you
  move from kind → staging → production clusters.

## LLM routing

- Bring up the Ollama sidecar (`docker compose --profile llm up -d`) and set:

  ```bash
  export HOTPASS_LLM_PROVIDER=local
  export HOTPASS_LLM_BASE_URL=http://127.0.0.1:11434
  ```

- For Groq/OpenRouter parity, switch `HOTPASS_LLM_PROVIDER` and provide the relevant
  API keys/base URLs.

## Environment variable quick reference

| Variable                         | Description                                          |
|----------------------------------|------------------------------------------------------|
| `PREFECT_API_URL`                | Prefect server the CLI should target.                |
| `OPENLINEAGE_URL`                | Marquez/OpenLineage endpoint.                        |
| `OTEL_EXPORTER_OTLP_ENDPOINT`    | OTLP collector endpoint (HTTP).                      |
| `HOTPASS_S3_ENDPOINT`           | MinIO URL for artefact storage.                      |
| `LOCALSTACK_ENDPOINT`            | LocalStack URL for simulated AWS APIs.               |
| `HOTPASS_SEARX_URL`              | SearXNG meta-search endpoint.                        |
| `HOTPASS_LLM_BASE_URL`           | Ollama or SaaS base URL.                             |
| `FEATURE_ENABLE_REMOTE_RESEARCH` | Enables research workflows (defaults to `false`).    |
| `ALLOW_NETWORK_RESEARCH`        | Opt-in to network calls when compliance allows.      |

## Verification checklist

1. `docker compose ps` → all services healthy.
2. `prefect config view | grep PREFECT_API_URL` → points to `127.0.0.1:4200`.
3. `uv run hotpass refine --profile generic --archive` → completes using MinIO storage
   and emits lineage into the local Marquez instance.
4. `uv run hotpass plan research --dataset ./dist/refined.xlsx --row-id 0 --json` →
   remains offline unless you pass `--allow-network`.
5. Optional: run `uv run hotpass qa all` to confirm QA gates succeed against the local
   infrastructure.

Once the checklist passes, you can promote the same configuration to staging by only
changing the endpoint environment variables.
