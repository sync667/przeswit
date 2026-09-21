#!/usr/bin/env sh
# Uruchamia Prześwit na Linux/macOS: tworzy .venv, instaluje zależności, startuje serwer (zmienne z data/przeswit.env).
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
exec .venv/bin/python -X utf8 -m app
