#!/usr/bin/env pwsh
<#
 Regenerate lockfiles for Windows/Win64 platform
 Usage: pwsh scripts/regen_lockfiles.ps1 [-Commit] [-BranchName <branch>]

 This script performs the following actions:
 1. Creates/activates uv venv
 2. Syncs dependencies for the recommended extras
 3. Writes a uv.lock file
 4. Regenerates the apps/web-ui pnpm lockfile on Windows
 5. Optional: commits and pushes the lockfile changes to a new branch
#>

param(
  [string]$Commit = 'false',
  [string]$BranchName = 'regenerate/lockfiles-windows'
)

Set-StrictMode -Version Latest
Write-Host "Starting Windows lockfile regeneration"

function Run($cmd) {
  Write-Host "-> $cmd"
  $ret = & pwsh -Command $cmd
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: $cmd`nExit code: $LASTEXITCODE"
  }
}

# 1) Ensure `uv` is installed and venv created
Run "python -m pip install -U uv"
Run "uv venv"

# 2) Sync extras (adjust extras as needed for the environment)
$env:HOTPASS_UV_EXTRAS = 'dev orchestration enrichment geospatial compliance dashboards'
Run "uv sync --extra dev --extra orchestration --extra enrichment --extra geospatial --extra compliance --frozen"

# 3) Write uv.lock file
# `uv lock` writes the lockfile in current uv versions; older versions used `--write-lock`.
Run "uv lock"

# 4) Regenerate web UI pnpm lock on Windows (uses Corepack + pnpm)
if (-Not (Get-Command corepack -ErrorAction SilentlyContinue)) {
  Write-Host "Corepack not available; installing Node.js and corepack via Chocolatey if available"
  if (Get-Command choco -ErrorAction SilentlyContinue) {
    choco install -y nodejs-lts
  } else {
    Write-Host "Please install Node.js (LTS) and corepack to continue with pnpm steps"
  }
}
Run "corepack enable pnpm"
Run "corepack prepare pnpm@9.12.2 --activate"

Push-Location "apps/web-ui"
Run "pnpm install --frozen-lockfile"
Run "pnpm install"
Pop-Location

Write-Host "Lockfile regeneration complete (uv.lock and apps/web-ui/pnpm-lock.yaml)"

# Interpret commit flag (string to boolean)
$shouldCommit = $false
if ($Commit -and ($Commit.ToLower() -eq 'true' -or $Commit -eq '1')) {
  $shouldCommit = $true
}

if ($shouldCommit) {
  # Ensure git is setup and commit these lockfiles to a new branch
  Write-Host "Committing lockfile changes to branch: $BranchName"
  # If branch already exists, check it out; otherwise create it
  $branchExists = $false
  try {
    pwsh -Command "git show-ref --verify --quiet refs/heads/$BranchName"
    if ($LASTEXITCODE -eq 0) { $branchExists = $true }
  } catch { $branchExists = $false }
  if ($branchExists) { Run "git checkout $BranchName" } else { Run "git checkout -b $BranchName" }
  Run "git add uv.lock apps/web-ui/pnpm-lock.yaml"
  Run "git commit -m 'chore: regenerate lockfiles for Win64 (uv.lock, pnpm-lock)'"
  Run "git push -u origin $BranchName"
  Write-Host "Branch pushed: $BranchName - Create PR against main and request CI validations"
}

Write-Host "Done"
