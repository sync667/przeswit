#!/usr/bin/env sh
# Linux / macOS: creates .venv, installs dependencies, starts the server at http://127.0.0.1:8765
# Environment variables are read from data/przeswit.env (see przeswit.env.example).
set -e
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then echo "Python 3.10+ not found (set PYTHON=/path/to/python3)"; exit 1; fi
[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
if ! command -v ollama >/dev/null 2>&1; then echo "Note: 'ollama' not found in PATH — AI profiling will not start (install from https://ollama.com, then: ollama pull gemma3:12b)"; fi
exec .venv/bin/python -X utf8 -m app
