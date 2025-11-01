# Hotpass CLI Expansion Plan

> Implemented CLI expansion covering tunnels, AWS checks, contexts, and env generation.
> Last updated: 2025-10-31

## 1. Objectives

- Provide operators with a single entry point for network tunnelling, AWS identity checks, Prefect/kube context configuration, and environment export.
- Wrap established scripts (`ops/arc/verify_runner_lifecycle.py`, `ops/idp/bootstrap.py`, `ops/uv_sync_extras.sh`, etc.) with first-class CLI verbs to reduce manual shell usage.
- Persist operator choices under `.hotpass/` to enable resumable sessions and consistent automation.
- Ship user-friendly documentation (README quickstart, CLI reference, AGENTS runbook) alongside the packaged CLI so dist artefacts remain self-serve.

## 2. Proposed Commands

| Verb                  | Purpose                                                         | Key options                                                                        | Outputs / state                                                                                        |
| --------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `hotpass net up`      | Establish SSH or SSM tunnels to staging assets.                 | `--via {ssh-bastion, ssm}`, `--prefect-port`, `--marquez-port`, `--profile`        | `.hotpass/net.json` with assigned local ports; background process PID.                                 |
| `hotpass net down`    | Tear down active tunnel sessions.                               | `--all` / `--pid`, `--via`                                                         | Removes `.hotpass/net.json`, stops processes.                                                          |
| `hotpass aws check`   | Validate AWS identity and EKS access.                           | `--profile`, `--region`, `--eks-cluster`, `--verify-oidc`                          | Prints STS identity, optional kubeconfig check; writes `.hotpass/aws.json`.                            |
| `hotpass ctx init`    | Bootstrap Prefect + kubectl contexts.                           | `--prefect-profile`, `--eks-cluster`, `--kube-context`, `--overwrite`              | Shells out to `prefect profile create`, `aws eks update-kubeconfig`; records `.hotpass/contexts.json`. |
| `hotpass env write`   | Produce `.env.<environment>` for downstream tooling.            | `--target`, `--prefect-url`, `--openlineage-url`, `--allow-network`, `--overwrite` | Writes `.env.<target>` with validated values; references existing tunnel ports if present.             |
| `hotpass arc verify`  | CLI wrapper for ARC lifecycle checks.                           | Mirrors `ops/arc/verify_runner_lifecycle.py` options.                              | Pretty prints results; optional JSON output path; integrates with `.hotpass/arc/<date>/`.              |
| `hotpass distro docs` | (Packaging helper) Extract CLI/man pages from the dist archive. | `--output`                                                                         | Materialises Markdown/HTML docs for bundle distribution.                                               |

> Additional verbs (e.g., `hotpass net status`, `hotpass ctx list`) can be layered after the initial rollout once operator feedback is collected.

## 3. Parser & Handler Layout

- **Parser registration:** extend `apps/data-platform/hotpass/cli/main.py` to register new command modules (`net`, `aws`, `ctx`, `env`, `arc`). Each module exposes a `register()` returning `CLICommand` (consistent with existing pattern).
- **Shared parents:** re-use `SharedParsers` from `cli/builder.py` for base profile/config flags where relevant; supplement with dedicated subparsers for subcommands (e.g., `net up`, `net down`).
- **State helpers:** introduce `apps/data-platform/hotpass/cli/state.py` to read/write JSON artefacts under `.hotpass/`. Provide atomic writes and schema validation.
- **Process management:** wrap long-lived tunnels using `subprocess.Popen` with background handling (PID tracking, graceful shutdown). Provide prompts when ports already bound.
- **Error handling:** rely on existing `expect`-style assertions in tests; in CLI code, use structured exit codes (0 success, 1 recoverable error, 2 validation error).

## 4. Supporting Utilities

- **Networking:** create `ops/net/tunnels.py` with functions to spawn SSH/SSM commands, detect collisions (leveraging `lsof` logic from `Makefile`), and surface actionable errors.
- **AWS tooling:** adapt logic from `ops/arc/verify_runner_lifecycle` (STS identity) into a reusable helper (`apps/data-platform/hotpass/aws/utils.py`) shared by CLI + arc verifier.
- **Context bootstrap:** re-use `ops/idp/bootstrap.py` patterns for Prefect profile creation and environment file writing; refactor common pieces into importable functions to avoid duplication.
- **Environment writing:** integrate with `hotpass.secrets.load_prefect_environment_secrets` to ensure env generation respects Vault-based configuration when present.

## 5. Documentation Deliverables

- README quickstart: add a “Network & Context automation” section showing `hotpass net up`, `hotpass aws check`, `hotpass ctx init`, `hotpass env write`.
- `docs/reference/cli.md`: new subsections for each verb, including options and `.hotpass` artefact descriptions.
- `docs/how-to-guides/manage-arc-runners.md`: update to reference `hotpass arc verify` instead of direct Python invocation.
- AGENTS.md: extend command table and workflows to include the new automation surface.
- Distribution docs: ensure packaged dist includes `docs/reference/cli.md` excerpts or standalone HTML (exposed via `hotpass distro docs`).

## 6. Testing Strategy

- Unit tests: new modules under `tests/cli/` covering parser wiring (`test_parser.py`), command execution with subprocess stubs (use `pytest` fixtures and the project-wide `expect` helper).
- Integration tests: extend existing arc verifier tests to assert CLI wrapper parity (`tests/scripts/test_arc_runner_verifier.py`).
- Golden path tests: add fixtures to validate `.hotpass/net.json`, `.hotpass/aws.json`, `.env.<target>` output formats.
- Quality gates: ensure QG-1 enumerates the new verbs; consider adding a new gate for tunnel safety if required.

## 7. Rollout Phases

1. **Design validation:** finalise command names, options, and state schemas; confirm stakeholder buy-in via `Next_Steps.md`.
2. **Helper extraction:** refactor reusable pieces from `ops/idp`, `ops/arc`, etc., into shared modules.
3. **CLI implementation:** add parser registrations, command handlers, state helpers; write new tests.
4. **Documentation + dist updates:** refresh README/cli docs/AGENTS; ensure dist packaging includes updated manuals.
5. **Operator rehearsal:** run through `hotpass net/aws/ctx/env` flows against staging or mock environments; capture feedback and adjust defaults.

## 8. Open Questions

- How to manage credential prompts for SSH/SSM (delegate to `ssh` agent vs. collect via CLI)?
- Should tunnel processes run foreground with optional `--daemonize`, or always background with `--attach` equivalent?
- Decide whether `.hotpass/net.json` should support multiple simultaneous tunnels (list) or single active session semantics.
- Packaging: confirm whether dist should bundle platform-specific shell launchers (Windows `.bat`, etc.) once CLI surface is finalised.

---

Use this plan to drive implementation. Update the document as design choices are confirmed or when new requirements emerge.
