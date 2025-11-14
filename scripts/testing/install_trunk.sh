#!/usr/bin/env bash
set -euo pipefail

# Install trunk CLI if missing; idempotent.
if command -v trunk >/dev/null 2>&1; then
  echo "trunk CLI already present: $(trunk --version 2>/dev/null || echo 'unknown')"
  exit 0
fi

# Install trunk via the recommended install script. This is suitable for CI and local dev machines.
curl -fsSL https://get.trunk.io | bash -s -- -y
# Add to PATH for the remainder of this script (CI job should write to $GITHUB_PATH already)
if [[ -n "${HOME:-}" ]]; then
  export PATH="$HOME/.trunk/bin:$PATH"
fi

if ! command -v trunk >/dev/null 2>&1; then
  echo "Unable to install trunk CLI" >&2
  exit 1
fi

trunk --version
echo "If you're on Windows and prefer an installer, run: 'choco install -y trunk' or follow https://trunk.io/docs/cli/getting-started/" || true
