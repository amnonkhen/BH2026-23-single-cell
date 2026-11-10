#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec python3 download_studies.py --summarize "$@"
