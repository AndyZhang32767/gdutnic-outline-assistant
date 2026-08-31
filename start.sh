#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "需要 Python 3.10+（建议 3.12）。" >&2
  exit 1
fi

"$PY" -m pip install -r requirements.txt
"$PY" -m uvicorn server.app:app --host 0.0.0.0 --port 8787
