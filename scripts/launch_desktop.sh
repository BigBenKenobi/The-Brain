#!/usr/bin/env bash
set -euo pipefail
brain_app_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$brain_app_root"
exec python3 -m brain.desktop --brain "$brain_app_root/Project-Brain" "$@"
