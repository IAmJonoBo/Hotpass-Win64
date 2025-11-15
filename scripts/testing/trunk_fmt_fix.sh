#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

echo "Ensuring trunk is installed..."
bash scripts/testing/install_trunk.sh

echo "Running trunk fmt --all (this will modify files on disk)"
trunk fmt --all
echo "Formatting run complete; showing diff summary:"
git --no-pager diff --name-only

echo "Optionally run 'git add -A && git commit -m "Apply trunk formatting"' to update your branch."

exit 0
