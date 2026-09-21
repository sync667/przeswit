# Jak pomóc w rozwoju Prześwitu

Dziękujemy za zainteresowanie. Projekt jest mały i lokalny — najbardziej pomagają konkretne zgłoszenia i małe, przetestowane zmiany.

## Zgłoszenia
- Błąd: użyj szablonu issue „Błąd”; podaj wersję Pythona, system, kroki i fragment `data/app.log` (bez danych osobowych).
- Pomysł: opisz problem, który rozwiązuje, nie tylko rozwiązanie.

## Środowisko
```
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt     # Windows: .venv\Scripts\pip
python -m unittest discover -s tests -t .
ruff check app tests && ruff format app tests
```
Frontend to czyste moduły ES w `app/static/js/` — bez kroku budowania (`node --check app/static/js/*.js` sprawdza składnię). Nie dodawaj frameworków ani zależności z CDN (CSP dopuszcza tylko `self`).

## Zasady
- Aplikacja jest lokalna i prywatna: żadnych wywołań chmury bez wyraźnej zgody użytkownika, żadnych telemetrii.
- Dane źródeł zewnętrznych: użytek osobisty, odstępy między żądaniami, brak obchodzenia blokad, brak danych kontaktowych w rekordach.
- Zmiana promptu lub schematu profilu (`app/prompts/`, `app/profiles.py`) wymaga podbicia `VERSION` (unieważnia gotowe profile) i porównania jakości na próbce (`tools/qa_profiles.py`).
- Każda zmiana w API ma test w `tests/test_api.py`; zmiany w UI sprawdź w przeglądarce (lista, karta miejsca, mapa).
- Commity po polsku lub angielsku, jeden temat na commit.
