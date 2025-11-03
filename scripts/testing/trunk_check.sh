#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

export PYTHONPATH="${PYTHONPATH-}:${ROOT_DIR}/apps/data-platform"

ALLOW_MISSING="${TRUNK_ALLOW_MISSING:-0}"
FMT_MODE="${TRUNK_FMT_MODE:-check}"
UPSTREAM="${TRUNK_UPSTREAM:-origin/main}"

if ! command -v trunk >/dev/null 2>&1; then
	cat <<'MSG' >&2
[trunk] CLI not found. Install it with:
  curl https://get.trunk.io -fsSL | bash
or
  brew install trunk
Set TRUNK_ALLOW_MISSING=1 to skip this check temporarily.
MSG
	if [[ ${ALLOW_MISSING} == "1" ]]; then
		exit 0
	fi
	exit 127
fi

if [[ ${FMT_MODE} != "skip" ]]; then
	FMT_FLAGS=(fmt --ci --upstream "${UPSTREAM}")
	if [[ ${FMT_MODE} == "check" ]]; then
		FMT_FLAGS+=(--no-fix)
	elif [[ ${FMT_MODE} == "fix" ]]; then
		:
	else
		echo "[trunk] Unknown TRUNK_FMT_MODE: ${FMT_MODE}" >&2
		exit 2
	fi
	trunk "${FMT_FLAGS[@]}"
fi

trunk check --ci --upstream "${UPSTREAM}" "$@"
