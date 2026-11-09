#!/usr/bin/env bash
# Thin wrapper around download_experiments.py (preferred entrypoint).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$ROOT/download_experiments.py" "$@"
