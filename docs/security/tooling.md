---
title: Security tooling
summary: Run security automation (Semgrep) in controlled environments with custom CA bundles.
last_updated: 2025-11-02
---

## Semgrep auto scans

Use the helper script when you need the managed `--config=auto` rule set, especially on runners that enforce outbound TLS inspection.

### Local or ephemeral runner

```bash
# optional: provide the corporate CA bundle in base64 form
export HOTPASS_CA_BUNDLE_B64="$(base64 < corp-root.pem)"
make semgrep-auto
```

The `semgrep-auto` make target wraps `ops/security/semgrep_auto.sh`, which decodes the CA bundle (if provided), sets `REQUESTS_CA_BUNDLE`, and invokes `uv run semgrep --config=auto --metrics=off`.

### GitHub Actions / Codex

1. Store the base64-encoded CA bundle in a secret such as `SEMGREP_CA_BUNDLE_B64`.
2. Set the workflow, task, or environment variable `HOTPASS_CA_BUNDLE_B64` to that secret before calling the script or target.
3. Run `make semgrep-auto` (or call the script directly) as part of your pipeline.

When the CA bundle is omitted the script falls back to the runner’s default trust store, matching the previous behaviour.

## Fallback policy scan

If external connectivity is unavailable, continue using the repository policy configuration:

```bash
uv run semgrep --config=policy/semgrep/hotpass.yml --metrics=off
```

This keeps the static analysis gate green while the managed rule feed is temporarily unreachable.
