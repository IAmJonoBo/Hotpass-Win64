---
title: Supply-chain security plan
summary: SBOM, signing, provenance, and policy controls for Hotpass.
last_updated: 2025-11-02
---

## Objectives

- Generate CycloneDX SBOM on every PR and release.
- Produce in-toto provenance metadata for build artefacts.
- Enforce policy-as-code checks before promotion.
- Verify external supplier SBOMs and ingest VEX data.

## Pipeline additions

| Stage       | Tool             | Command                                                                         | Artefact                          |
| ----------- | ---------------- | ------------------------------------------------------------------------------- | --------------------------------- |
| SBOM        | CycloneDX        | `uv run python ops/supply_chain/generate_sbom.py`                               | `dist/sbom/hotpass-sbom.json`     |
| Provenance  | In-toto          | `uv run python ops/supply_chain/generate_provenance.py`                         | `dist/provenance/provenance.json` |
| Checksums   | Python stdlib    | `python ops/supply_chain/generate_provenance.py` (sha256)                       | Embedded in provenance            |
| Policy gate | Python rego shim | `uv run python ops/supply_chain/evaluate_policy.py dist/sbom/hotpass-sbom.json` | Pass/fail                         |

## Signing strategy

- Adopt Sigstore keyless signing once GitHub OIDC integration approved.
- Interim: publish SBOM + provenance digests and store `checksums.txt` in release assets.
- Validate downstream consumption via `sigstore verify identity` (planned once adoption complete).

## External dependency hygiene

1. Track dependencies/owners in [dependency matrix](../roadmap/dependency-matrix.md).
2. Enable `dependabot`/Renovate for security patches (Renovate config already present).
3. Run Semgrep supply-chain rules (see [quality gates](./quality-gates.md)).
4. Onboard to OpenSSF Scorecard scanning (future work).

## Supplier SBOM validation

- Require suppliers to publish signed SBOM + VEX.
- Verify signature via Sigstore; ensure `supplier` trust policy satisfied (documented in `policy/sbom.rego`).
- Ingest accepted SBOM into internal registry, annotate with ingestion timestamp.
- Map vulnerabilities to remediation backlog entries and risk register.

## Artefact retention

- Store SBOM/provenance artefacts in `data/artifacts/supply-chain/` with 1 year retention.
- Mirror to Backstage TechDocs for discoverability.
- Reference artefacts in incident response playbooks.

## Ownership & review cadence

- **DevOps** — Maintains workflows, ensures SBOM/provenance generation remains healthy.
- **Security** — Owns policy definitions, verifies enforcement results, triages violations.
- **Compliance** — Confirms evidence captured for audits.
- Review supply-chain posture quarterly alongside compliance verification cadence.
