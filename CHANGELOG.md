# Changelog

*[Wersja polska](CHANGELOG.pl.md)* · Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). No numbered releases yet — entries are grouped by date.

## 2026-09-22
- English README, CONTRIBUTING and CHANGELOG; Polish versions kept as `*.pl.md`.

## 2026-09-21
- `app/p4n/` module: resumable data pipeline (grid scan, details, comments), conversion, ingest, packed starter set `seed/places_pl.pack` imported into an empty database.
- Own points (planned / visited / someday) with photos (from the map, a link, or EXIF GPS), GPX routes with distances and a trip plan, lasso with bulk decisions, satellite basemaps with terrain relief, place ids and deep links, remembered view, filter presets, keyboard shortcuts, dark theme, PWA.
- Internet access via Cloudflare Tunnel + Access with an e-mail gate on the server, JWT verification, read-only guest mode and decision authorship.
- Profiling prompt v3 with quote grounding in code; feature de-duplication; identifier clean-up in texts.
- FastAPI backend, ES-module frontend, CSS redesign, ruff formatting, CI (Ubuntu/Windows), MIT licence.

## 2026-09-18
- Repository restructuring, `app/` package, tests, first git commits.
