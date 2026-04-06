#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export TONGCHENG_HEADLESS="${TONGCHENG_HEADLESS:-1}"

PY_BIN=""
if [ -x .venv/bin/python ]; then
  PY_BIN=".venv/bin/python"
elif command -v python3.12 >/dev/null 2>&1; then
  PY_BIN="$(command -v python3.12)"
elif [ -x /opt/homebrew/bin/python3.12 ]; then
  PY_BIN="/opt/homebrew/bin/python3.12"
elif command -v python3 >/dev/null 2>&1; then
  PY_BIN="$(command -v python3)"
else
  echo '没找到可用的 Python。先运行 ./setup_python312.sh'
  exit 1
fi

if [ ! -d .venv ]; then
  "$PY_BIN" -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if [ -f package.json ]; then
  npm install
fi

exec uvicorn app.main:app --reload --port 8020
