#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  echo 'Create .env with GEMINI_API_KEY=your_key before running.' >&2
  exit 1
fi
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! "$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3,11)' 2>/dev/null; then
  if [ -x /opt/homebrew/bin/python3.12 ]; then PYTHON_BIN=/opt/homebrew/bin/python3.12;
  elif command -v uv >/dev/null; then PYTHON_BIN="$(uv python find 3.12)";
  else echo 'Python 3.11+ is required. Set PYTHON_BIN to its path.' >&2; exit 1; fi
fi
if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c 'import sys; assert sys.version_info >= (3,11)' 2>/dev/null; then
  "$PYTHON_BIN" -m venv --clear .venv
fi
.venv/bin/python -m pip install --quiet -r requirements.txt
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}" --no-access-log
