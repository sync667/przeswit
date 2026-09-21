# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/). Projekt nie ma jeszcze numerowanych wydań — wpisy grupowane datami.

## 2026-09-21
- Moduł `app/p4n/`: wznawialne pobieranie danych źródła (siatka, szczegóły, komentarze), konwersja, ingest, zbiór startowy `seed/places_pl.pack` wczytywany przy pustej bazie.
- Własne punkty (planowane / byłem / na kiedyś) ze zdjęciami (z mapy, z linku, ze wskazania), trasy GPX z odległością miejsc, lasso i decyzje masowe, podkłady satelitarne z rzeźbą terenu, identyfikatory i linki miejsc, pamięć widoku.
- Dostęp z internetu przez Cloudflare Tunnel + Access z bramą e-mail na serwerze.
- Prompt profilowania v3 z ugruntowaniem cytatów w kodzie; deduplikacja cech; czyszczenie identyfikatorów w tekstach.
- Backend na FastAPI, frontend w modułach ES, redesign CSS, formatowanie kodu (ruff), CI (Ubuntu/Windows), licencja MIT.

## 2026-09-18
- Uporządkowanie struktury repozytorium, pakiet `app/`, testy, pierwsze kroki gita.
