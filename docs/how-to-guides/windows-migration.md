---
title: How-to — Windows/Win64 migration checklist
summary: Steps to complete the repository move to a Windows/Win64-first codebase and DevOps flow.
last_updated: 2025-11-14
---

This checklist describes the final steps to finish the Win64 migration after the initial repository changes have been made.

## 1) Regenerate dependency lockfiles

- Recreate `uv.lock` on a Windows host (or Windows-based CI runner) to ensure Python wheels and platform-specific codecs are pinned for Windows-compatible builds:
  ```powershell
  pwsh -Command "uv venv; uv sync --extra dev orchestration && uv lock --write-lock"
  ```
- Recreate `apps/web-ui/pnpm-lock.yaml` from a Windows-enabled node environment (or via WSL/pnpm on Windows):

  ### Optional: Use the automated workflow

  You can run the repository workflow to regenerate lockfiles on a GitHub-hosted `windows-latest` runner. The workflow is available under `.github/workflows/regenerate-lockfiles-windows.yml` and is dispatched manually. It writes both `uv.lock` and `apps/web-ui/pnpm-lock.yaml` as artifacts for inspection and supports an optional commit/push via branch (use a repo PAT if you want it to push changes automatically).

  To use the action:
  1. Open Actions → Regenerate lockfiles (Windows) → Run workflow.
  2. Choose whether to commit & push; if you choose commit, provide a branch name to push to.
  3. After the workflow completes, download `lockfiles` artifacts and review `uv.lock` and `pnpm-lock.yaml` changes before committing them to `platform/windows` branch.

  ```powershell
  cd apps/web-ui
  corepack enable pnpm
  corepack prepare pnpm@9.12.2 --activate
  pnpm install --frozen-lockfile --prefer-offline
  pnpm install # to refresh the lockfile if needed
  ```

- Use the `scripts/update_repo_refs.py` helper to spot residual references to the upstream repo and optionally replace them across the repo (dry run first):
  ```powershell
  python scripts/update_repo_refs.py --old "https://github.com/IAmJonoBo/Hotpass" --new "https://github.com/IAmJonoBo/Hotpass-Win64" --dry-run
  # After review
  python scripts/update_repo_refs.py --old "https://github.com/IAmJonoBo/Hotpass" --new "https://github.com/IAmJonoBo/Hotpass-Win64" --commit
  ```

## pnpm-to-pnpm2 alias/wrapper (optional)

If your environment or CI prefers a `pnpm2` command (for example because pnpm v2 is pinned as `pnpm2`), you can create a small wrapper in a directory on PATH that forwards `pnpm2` to `pnpm`. This is helpful when CI jobs explicitly call `pnpm2` or when a community script expects the alias. Two options are shown below; prefer the `cmd` shim for maximal compatibility in Windows runners.

- Create a `pnpm2.cmd` shim in your user bin folder:

  ```powershell
  $shimPath = Join-Path $env:USERPROFILE 'bin'
  New-Item -Path $shimPath -ItemType Directory -Force
  $cmdFile = Join-Path $shimPath 'pnpm2.cmd'
  '@echo off`r`npnpm %*' | Set-Content -Path $cmdFile -Encoding ASCII
  # Add $shimPath to your PATH with setx; restart your shell session for it to take effect
  setx PATH "$env:PATH;$shimPath"
  ```

- Alternatively, create a PowerShell alias for the current user (only in PowerShell sessions / profile):

  ```powershell
  # Add to your PowerShell profile (~\Documents\PowerShell\Microsoft.PowerShell_profile.ps1)
  Add-Content -Path $PROFILE -Value "Set-Alias -Name pnpm2 -Value pnpm"
  ```

Either approach enables `pnpm2 install` to behave the same as `pnpm install` in CI or interactive shells. We recommend the `pnpm2.cmd` shim for Windows runner compatibility because it works in both `pwsh` and `cmd.exe` shells.

## 2) Validate GitHub Actions

- Verify that the CI workflows set `runs-on: windows-latest` and that Bash-based tasks use `shell: bash` explicitly.
- For steps requiring PowerShell, use `shell: pwsh`.
- If your CI uses Linux-only images or steps, either adapt them to Windows equivalents or run Windows-compatible runner images with `shell: bash` or `shell: pwsh` as needed.

## 3) ARC runner adjustments

- If you deploy ARC runners into your cluster with `infra/arc`, ensure the runner image is Windows-compatible if you set `nodeSelector: kubernetes.io/os: windows`.
- Alternatively, keep `nodeSelector: linux` and use Linux-based runner images if you plan to keep the image composition and orchestration in Linux.

## 4) Docker and compose

- Most Docker images remain Linux containers (linux/amd64). If you need native Windows containers, update service images to Windows images and test on Windows Server/hosted runners.
- Set `platform: linux/amd64` for all containers if you want to guarantee amd64 Linux containers run on Windows hosts (this is supported on Docker Desktop). Add the `platform` property in `deploy/docker/docker-compose.yml` as needed.

## 5) Automation & scripts

- Replace `macOS` mentions in docs and scripts to `Linux` or `Windows` as relevant.
- Remove or update platform-specific logic for macOS to Windows-first behavior.

## 6) CI and Developer Documentation

- Update `README.md`, `AGENTS.md`, `UPGRADE.md`, and other guides to prefer Windows setup (PowerShell) and add `bash` alternatives as needed.
- Add a hint to re-run the `ops/preflight.py` script on Windows to validate the environment.

## 7) Validate platform-specific builds and smoke tests

- Run `scripts/testing/smoke.ps1` and `scripts/testing/full.sh` from a Windows runner to ensure parity.
- For local verification: use WSL or Git Bash for Bash-based tasks and `pwsh` for PowerShell scripts.

---

If you'd like, I can begin performing the lockfile regeneration and CI proof-run steps in this repository (requires running `uv` and `pnpm` on a Windows environment), or optionally create PRs for platform lockfile updates and CI tweaks.
