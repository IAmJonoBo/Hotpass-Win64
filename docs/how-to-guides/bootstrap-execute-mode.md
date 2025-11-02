---
title: Safely run the bootstrap execute mode
summary: Guardrails and rollback guidance for applying Hotpass bootstrap changes.
last_updated: 2025-11-02
---

The Hotpass bootstrap utility (`ops/idp/bootstrap.py`) provisions local dependencies,
Prefect profiles, supply-chain tooling, and developer experience defaults. By default the
command performs a dry run so you can review the plan before any files change. Executing
with `--execute` applies the plan to disk—use the guardrails below to avoid surprises and
roll back quickly if something misbehaves.

## Before you begin

1. Run the bootstrap in dry-run mode and review the generated plan:
   ```bash
   uv run python ops/idp/bootstrap.py
   ```
2. Capture the diff of any repositories or configuration folders that will be touched.
   For Git repositories, commit or stash outstanding work first so the bootstrap output is
   easy to inspect.
3. Ensure your `.env` and secrets files are backed up or checked into a secure vault. The
   bootstrap never deletes secrets, but it can regenerate configuration files that reference them.

## Apply changes safely

When you are ready to commit the changes, re-run the bootstrap with execute mode enabled:

```bash
uv run python ops/idp/bootstrap.py --execute
```

The guardrails baked into execute mode include:

- **Idempotent tasks** – each provisioning step checks whether the target already exists
  and skips destructive operations unless you pass an explicit `--force` flag.
- **Transaction logs** – the script writes a timestamped log to
  `dist/logs/bootstrap/<timestamp>.json` capturing every file it touched. Keep the latest
  log handy when verifying the rollout.
- **Workspace snapshots** – when running against a Git repository the bootstrap stages a
  snapshot commit (without pushing) so you can inspect the diff before finalising.
- **Safe subprocess invocation** – external commands run with `check=True` and rich
  console output so failures are surfaced immediately.

## Roll back quickly

If you need to revert the execute run:

1. Use the staged snapshot commit created by the bootstrap to roll back file changes:
   ```bash
   git reset --hard
   ```
2. Restore any configuration or secrets from the backups you captured in the
   "Before you begin" section.
3. Re-run the bootstrap in dry-run mode to confirm the environment is back in the expected
   state. The output should show the same plan as before the execute run.
4. If a Prefect deployment or external integration was modified, follow the component's
   runbook (for example, disable the Prefect deployment or rotate credentials) before
   attempting another execute run.

Document any follow-up actions or unexpected behaviour in `Next_Steps.md` so the team can
track remediation work.
