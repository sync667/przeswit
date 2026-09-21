#!/usr/bin/env sh
# Cloudflare Tunnel na Linux/macOS: cloudflared z PATH, konfiguracja data/cloudflared/config.yml.
cd "$(dirname "$0")/.."
exec cloudflared tunnel --config data/cloudflared/config.yml --loglevel info run
