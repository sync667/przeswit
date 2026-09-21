# Contributing to Prześwit

*[Wersja polska](CONTRIBUTING.pl.md)*

Thanks for your interest. The project is small and local-first — concrete bug reports and small, tested changes help most.

## Reports
- Bug: use the "Bug" issue template; include Python version, OS, steps, and a snippet of `data/app.log` (no personal data).
- Idea: describe the problem it solves, not only the solution.

## Environment
```
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt     # Windows: .venv\Scripts\pip
python -m unittest discover -s tests -t .
ruff check app tests && ruff format app tests
```
The frontend is plain ES modules in `app/static/js/` — no build step (`node --check app/static/js/*.js` validates syntax). Do not add frameworks or CDN dependencies (the CSP allows only `self`).

## Rules
- The app is local and private: no cloud calls without explicit user consent, no telemetry.
- External data sources: personal use, delays between requests, no bypassing of blocks, no contact data in records.
- Changing the prompt or the profile schema (`app/prompts/`, `app/profiles.py`) requires bumping `VERSION` (invalidates ready profiles) and comparing quality on a sample (`tools/qa_profiles.py`).
- Every API change comes with a test in `tests/test_api.py`; UI changes are checked in a browser (list, place card, map).
- Commit messages in English or Polish, one topic per commit.
