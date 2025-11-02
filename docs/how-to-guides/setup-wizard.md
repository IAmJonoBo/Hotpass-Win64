---
title: Use the Hotpass setup wizard
summary: Run the guided CLI wizard to sync dependencies, open tunnels, configure contexts, and emit environment files in one pass.
last_updated: 2025-11-02
---

The `hotpass setup` command wraps the most common operator tasks—dependency sync, tunnel
setup, AWS verification, context bootstrap, and `.env` generation—into a single guided flow.
Use it whenever you need to prepare staging operators (human or agent) without memorising
individual commands.

## 1. Preview the plan

Run the wizard in dry-run mode to review each step before executing:

```bash
uv run hotpass setup \
  --preset staging \
  --host bastion.example.com \
  --dry-run
```

The command prints a Rich table showing the exact `hotpass` or shell commands that will
run (for example `ops/uv_sync_extras.sh`, `hotpass net up`, `hotpass ctx init`, `hotpass env`).

## 2. Execute the full flow

When you are happy with the plan, add `--execute` (or reply “yes” when prompted in
interactive terminals):

```bash
uv run hotpass setup \
  --preset staging \
  --host bastion.example.com \
  --aws-profile hotpass-staging \
  --execute
```

Successful runs store a summary under `.hotpass/setup.json` so auditors can see which
steps completed.

## 3. Customise stages

The wizard exposes flags for every stage:

- `--extras` and `--skip-deps` control `ops/uv_sync_extras.sh`.
- `--via`, `--host`, `--label`, and `--skip-tunnels` customise tunnel behaviour.
- `--aws-profile`, `--aws-region`, `--skip-aws`, and `--eks-cluster` tune AWS/EKS checks.
- `--prefect-profile`, `--prefect-url`, `--namespace`, `--skip-ctx`, and `--kube-context`
  fine-tune context bootstrap.
- `--env-target`, `--allow-network`, `--force-env`, and `--skip-env` manage environment file output.
- `--arc-owner`, `--arc-repository`, `--arc-scale-set`, and `--skip-arc` control ARC verification.

Combine these with `--preset local` for offline machines or `--skip-prereqs`
when you are certain required binaries are already installed.

## 4. Integrate with agents

- **Copilot/VS Code**: add `hotpass setup --preset staging --host $BASTION --execute`
  to task snippets so agents can provision workspaces for operators automatically.
- **MCP tooling**: run the wizard once to seed `.hotpass/net.json`, `.hotpass/contexts.json`,
  and `.env.staging`; MCP tools reuse those state files when resolving profiles.
- **Chat agents**: call the MCP tool directly:
  ```
  /call hotpass.setup preset=staging host=bastion.example.com dry_run=true skip_steps=["aws","ctx","env","arc"]
  /call hotpass.setup preset=staging host=bastion.example.com execute=true arc_owner=ExampleOrg arc_repository=Hotpass arc_scale_set=hotpass-arc
  ```
  Combine with `/call hotpass.net action=status` or `/call hotpass.env target=staging dry_run=true`
  to manage tunnels and environment files without leaving chat.

## 5. Troubleshooting

- The prerequisite check highlights missing commands (`uv`, `prefect`, `aws`, `kubectl`, `ssh`).
  Install them or rerun with `--skip-prereqs`.
- If your bastion host or SSM target differs per environment, export
  `HOTPASS_BASTION_HOST` to avoid retyping `--host`.
- For ARC rehearsals without cluster access, provide `--arc-snapshot path/to/snapshot.json`
  to replay pre-recorded runner states.

Refer back to `docs/reference/cli.md#infrastructure-automation` for the full option matrix.
