# Prześwit

*[English version](README.md)*

Lokalna, prywatna biblioteka miejsc w naturze na biwak z motocyklem ADV: import miejsc (JSON / GeoJSON / CSV / GPX / ZIP, P4N, OSM, BDL), własne punkty ze zdjęciami, przeglądanie w galerii i na mapie (OSM, satelita, rzeźba terenu, obszary „Zanocuj w lesie”), trasy GPX z odległością każdego miejsca od trasy, decyzje zachowaj / odrzuć (także masowo lassem), notatki — oraz **profilowanie miejsc lokalnym modelem wizyjnym (Ollama, gemma3)** i wyszukiwanie według opisu. Wszystko działa na Twoim komputerze; żadne dane nie wychodzą do chmury.

## Zrzuty ekranu

| Galeria | Karta miejsca z profilem AI | Mapa + lista |
|---|---|---|
| ![Galeria kafli](docs/screenshots/galeria.jpg) | ![Profil AI miejsca](docs/screenshots/profil-ai.jpg) | ![Mapa z listą](docs/screenshots/mapa.jpg) |

## Wymagania

- Windows 10/11 (skrypty `.cmd`; sam serwer to zwykły FastAPI i działa też na Linux/macOS), Python 3.10+.
- [Ollama](https://ollama.com) z modelem wizyjnym: `ollama pull gemma3:12b` (mniejszy `gemma3:4b` też działa, gorzej). Aplikacja uruchamia własny proces Ollamy na porcie 11435 z katalogu modeli `~/.ollama/models` (zmień przez `PRZESWIT_MODELS`). GPU z ≥ 12 GB VRAM dla 12B; profilowanie bez GPU jest bardzo wolne.
- Internet tylko do pobierania zdjęć z importów i podkładów map; działanie offline na już pobranych danych.

## Szybki start

1. `START.cmd` — tworzy `.venv`, instaluje `requirements.txt`, uruchamia serwer. Ręcznie: `python -m venv .venv`, `.venv\Scripts\pip install -r requirements.txt`, `.venv\Scripts\python -m app`.
2. Otwórz http://127.0.0.1:8765 (dokumentacja API: `/docs`).
3. „Importuj miejsca” → wczytaj plik (wzór: `examples/template.json`, dane demonstracyjne: `examples/demo.json`) albo wrzuć eksport do folderu `inbox/`. Profile AI powstają automatycznie w tle.

Duże karty pokazują zdjęcia bez otwierania szczegółów; strzałki zmieniają zdjęcie, kliknięcie otwiera galerię. Odrzuć / Zachowaj zapisują wybór w SQLite (kafel znika, scroll zostaje), „Cofnij” odwraca ostatnią decyzję. Zakładki: Do przejrzenia, Zachowane, Odrzucone, Wszystkie. Odrzucenie nie usuwa danych. Każde miejsce ma kopiowalny identyfikator i link `#place=…`. Ponowny import zachowuje notatki. Zdjęcia zewnętrzne potrzebują internetu; nie są zastępowane fikcyjnymi widokami.

Klawiatura: `J`/`K` kolejny/poprzedni kafel, `S` zachowaj, `X` odrzuć, `Enter` karta, `M` mapa, `/` szukaj, `D` motyw ciemny/jasny, `?` przypomnienie. Presety filtrów (wbudowane i własne) w pasku filtrów. Aplikację można dodać do ekranu telefonu jako PWA (przez HTTPS; statyki działają offline, dane wymagają połączenia).

Baza i notatki: `data/scout.sqlite3`. Kopię zapasową całego `data/` wykonuj po zatrzymaniu aplikacji (albo przyciskiem w oknie importu). Nie publikuj bazy ani cache wraz z kodem — katalog `data/` jest w `.gitignore`. Rankingi to wskazówki z dostępnych danych, nie potwierdzenie dojazdu ani zgody na namiot.

Logo: własny znak SVG. Kolory: leśny #203f35, papier #f6f4ef, bursztyn #e5aa61.

## Rozwój

Zależności deweloperskie: `.venv\Scripts\pip install -r requirements-dev.txt`. Testy: `python -m unittest discover -s tests -t .` (albo `pytest`) — testy API używają `fastapi.testclient` i tymczasowej bazy, nie dotykają `data/` ani Ollamy. Styl: `ruff check app tests && ruff format app tests`. Frontend to czyste moduły ES bez kroku budowania; `node --check app/static/js/*.js` sprawdza składnię. CI (GitHub Actions) uruchamia lint i testy na Ubuntu i Windows. Jakość profili AI mierzy `python tools/qa_profiles.py` (metryki, reguły podejrzeń, próbka do przeglądu) — uruchamiaj przed i po zmianie promptu. Linux/macOS: `./start.sh`, tunel `scripts/run_tunnel.sh`.

Źródła danych i prawo: aplikacja jest do użytku osobistego. Moduł `app/p4n/` pobiera publiczne dane P4N na potrzeby własnej biblioteki — przed użyciem sprawdź regulamin serwisu, zachowaj odstępy między żądaniami i nie rozpowszechniaj pobranych danych poza własny użytek. Dane OSM i BDL mają własne licencje (atrybucja na mapie).

## Dane P4N: moduł i zbiór startowy

`python -m app.p4n <krok>` — wznawialny pipeline z stanem w `data/p4n/`: `scan` (siatka punktów co 0,35°, promień 50 km, domyślnie cała Polska; `--bbox lat_min,lon_min,lat_max,lon_max`), `details` (udogodnienia, ceny, sezonowość, zdjęcia ze starego API), `comments` (pełne komentarze ze stron miejsc; `--country Poland` najpierw), `ingest` (konwersja i upsert do bazy, klucz `p4n:<id>`), `seed` (plik `seed/places_pl.pack`), `all` (scan → details → comments → ingest), `status`. Odstępy 1–2,4 s między żądaniami, przy HTTP 403/429 przerwanie bez ponawiania. Dane kontaktowe właścicieli miejsc nie są zapisywane.

**Zbiór startowy**: repozytorium zawiera `seed/places_pl.pack` — spakowany, nieczytelny jako tekst zbiór miejsc typu PN z Polski (1364 miejsc, komentarze bez autorów, bez danych kontaktowych). Przy pierwszym uruchomieniu na pustej bazie aplikacja wczytuje go automatycznie (ustawienie `seed_imported`), więc od razu jest co przeglądać; profile AI powstają w tle. Usunięte miejsca nie wracają. Zbiór to migawka z daty w etykiecie pliku — odśwież ją własnym pobraniem (`python -m app.p4n all`).

## Struktura projektu

```
app/                 pakiet Pythona (backend)
  server.py          start uvicorn (127.0.0.1:8765)
  web.py             aplikacja FastAPI: middleware, obsługa błędów, statyki, cykl życia wątków
  api.py             endpointy /api/* i /photos/*
  schemas.py         modele żądań (Pydantic)
  security.py        token sesji, dozwolone Host/Origin, nagłówki CSP
  storage.py         SQLite, kopie zapasowe, ustawienia
  core.py            normalizacja, filtry obszaru, ranking
  importers.py       import JSON/GeoJSON/CSV/GPX/ZIP i folder inbox
  providers.py       konektory publicznych danych (OSM, BDL)
  public_web.py      pobieranie P4N
  sync.py            zadania synchronizacji obszarów
  ai_runtime.py      własny proces Ollama (127.0.0.1:11435), telemetria zasobów
  local_vision.py    lokalne wnioskowanie na zdjęciach
  profiles.py        automatyczne profile miejsc i wyszukiwanie opisem
  photo_cache.py     lokalna pamięć zdjęć (data/photos)
  prompts/           prompty modelu
  static/            frontend (część pakietu, bez kroku budowania)
    index.html, style.css, logo.svg, vendor/leaflet
    js/main.js       punkt wejścia (moduły ES): podpięcie zdarzeń i start
    js/state.js      wspólny stan i stałe; dom.js pomocniki; api.js fetch z tokenem
    js/library.js    ładowanie, filtrowanie, sortowanie; cards.js galeria kart; detail.js szczegóły
    js/map.js        Leaflet + warstwa BDL; jobs.js źródła/importy/polling; transfer.js import pliku i eksporty
    js/ai.js         wyszukiwanie opisem, kolejka profili, cache zdjęć, baza
examples/            template.json (szablon importu), demo.json (dane demonstracyjne)
tests/               testy unittest (core, importery, profile, cache zdjęć, baza, API)
docs/                notatki badawcze, porównanie modeli, raport weryfikacji
data/                baza, kopie, cache zdjęć, logi (ignorowane przez git)
inbox/               obserwowany folder eksportów (ignorowany przez git)
```

Adresy w przeglądarce: `/` (aplikacja), `/static/...` (frontend z `app/static/`), `/examples/template.json`, `/photos/<skrót>` (lokalne zdjęcia), `/api/...` (JSON), `/docs` (OpenAPI). Każdy POST wymaga nagłówka `X-ADV-Token` z wartością z `/api/config` oraz Origin z tej aplikacji; serwer przyjmuje tylko Host `127.0.0.1:8765` / `localhost:8765`.

## Trasy GPX i plan jazdy

W trybie „Mapa + lista” wczytaj dowolną liczbę plików GPX (ślady z segmentami, trasy, punkty). Każde miejsce dostaje odległość od najbliższej trasy (punkt → odcinek), lista sortuje się według niej, filtr „tylko do X km od trasy” działa też w galerii. Panel „Plan jazdy” układa zachowane miejsca (i własne punkty „planowane”) w kolejności km od startu trasy, dzieli na dni (km/dzień) i eksportuje GPX z ponumerowanymi waypointami oraz śladem trasy — dla Garmina, OsmAnd itp.

## Dostęp z telefonu (Cloudflare Tunnel + Access)

Aplikacja może być dostępna pod własną domeną bez otwierania portów: `cloudflared` na tym komputerze utrzymuje tunel do 127.0.0.1:8765, a Cloudflare Access wpuszcza wyłącznie zalogowanego właściciela (Google / kod na e-mail). Konfiguracja tunelu i poświadczenia leżą w `data/cloudflared/` (poza gitem). Serwer wymaga zmiennych `PRZESWIT_PUBLIC_HOST` (np. `przeswit.example.com`) i `PRZESWIT_ACCESS_EMAILS` (adresy po przecinku; wzór w `przeswit.env.example`, plik `data/przeswit.env` wczytuje `scripts/run_app.cmd`); żądania z publicznego hosta bez nagłówka `Cf-Access-Authenticated-User-Email` z jednym z tych adresów dostają 403 — nawet gdyby ktoś ominął Access. Właściciele (`PRZESWIT_OWNER_EMAILS`) mogą zapisywać; pozostałe dozwolone adresy dostają tryb tylko do odczytu (baner, ukryte przyciski, POST → 403). Każda decyzja i notatka zapamiętuje autora (e-mail z Access albo `local`) i czas. Opcjonalnie serwer weryfikuje podpis JWT Access (`PRZESWIT_ACCESS_TEAM`, `PRZESWIT_ACCESS_AUD`; klucze publiczne zespołu pobierane co godzinę). Dostęp lokalny działa jak dotąd. Uruchamianie jest ręczne: `START.cmd` (serwer) i `scripts/run_tunnel.cmd` (tunel) — bez autostartu; logi w `data/app.log` i `data/cloudflared/tunnel.log`.

## Lokalne modele i zdjęcia

Wnioskowanie odbywa się wyłącznie przez lokalny proces Ollamy (127.0.0.1:11435), bez płatnego API; korzysta z zasobów komputera i energii. Ocena jest subiektywna; model nie potwierdza legalności ani dojazdu. Zdjęcia i opisy nie otrzymują uprawnień do wykonywania narzędzi. Obrazy mogą być osadzone w JSON jako `data:image/jpeg;base64` (także PNG/WebP). Automatycznie pobierane są bezpośrednie obrazy z CDN źródła P4N i upload.wikimedia.org; linki do stron galerii nie są obrazami. Limit 6 MB na obraz, przekierowania wyłączone.

## Automatyczne profile i wyszukiwanie — aktualny tryb

Zastępuje ręczne ocenianie stron opisane powyżej. Każda nowa lub zmieniona lokacja otrzymuje profil w tle, niezależny od prompta wyszukiwania. Obecna baza jest profilowana tą samą kolejką. Po starcie i co 15 sekund wykrywane są zmiany danych. Tabela SQLite profiles przechowuje stan, wersję prompta, skrót danych źródłowych, błędy i wynik. Restart wznawia przerwane rekordy, błędy mają maksymalnie trzy automatyczne próby z odstępem; interfejs pozwala ponowić je ręcznie i wstrzymać pracę po bieżącym miejscu. Jedna analiza naraz.

Pełny prompt klasyfikacji: app/prompts/profile_prompt.md. Katalog ma 37 cech, m.in. krajobraz, wodę, nawierzchnię, namiot, motocykl, prywatność, ruch, udogodnienia, koszty i ryzyka. Każda rozpoznana cecha ma natężenie, pewność, uzasadnienie i odniesienia do źródeł. Do 5 zdjęć i do 15 komentarzy / dowodów na rekord. Brak zdjęć oznacza profil text_only, a nie udawaną analizę obrazu. Zmiany treści pod niezmienionym URL zdjęcia nie są wykrywane bez nowego importu z innymi danymi.

Szukaj według opisu uruchamia drugi prompt modelu: tłumaczy życzenie na cechy, ich pożądane wartości, wagi i wymagania konieczne. Potem kod porównuje WSZYSTKIE gotowe aktualne profile, nie tylko bieżącą stronę. Wynik uwzględnia pewność dowodów, a nieznane cechy nie spełniają wymagań. Plan jest pokazany w „Jak AI zrozumiało wyszukiwanie?”. Niewspierane wymagania są ujawniane. Dokładna geografia powinna być określona filtrami obszaru; model nie jest silnikiem tras ani weryfikatorem zgód. Złożone alternatywy są przybliżane wagami, nie pełną logiką boolowską.

Wyniki wyszukiwania są migawką gotowych profili i wymagają ponownego wyszukania, by uwzględnić zakończone później analizy. Oceny dopasowania są ważone według pewności; 0 nie oznacza potwierdzonej nieprzydatności. Profilowanie nie zmienia zapisanych/odrzuconych wyborów. Profile pozostają w bazie także przy ponownym imporcie identycznych danych.

## Oceny na kafelkach z profilu AI

Metryki ADV / Widok / Woda / Spokój pochodzą z reguł (geo, słowa kluczowe) i — gdy profil AI jest gotowy — z jego cech: Widok z panoramy, gór, położenia, zachodu/wschodu, natury; Woda z brzegu, rzeki, jeziora, plaży, dojścia do wody; ADV z dojazdu, szutru, lekkiego terenu, miejsca na motocykl i płaskiego terenu, obniżane przez trudny teren, błoto, szlabany i stromiznę; Spokój z osłonięcia, ciszy, małej liczby ludzi, zabudowy i ruchu. Liczy się najlepiej udokumentowana cecha z pewnością ≥ 40%. Wartości z profilu uzupełniają reguły (nie kasują oceny wody z odległości w imporcie); zapisana analiza chmurowa ma pierwszeństwo. Na kafelku widać znacznik „AI”, w karcie miejsca tryb „Profil AI (lokalny) + reguły” oraz uzasadnienie każdej metryki w sekcji dowodów. Karta miejsca pokazuje też ocenę i liczbę komentarzy ze źródła, mapę lokalizacji (podkład OSM, jeśli włączony), komentarze i przyciski zachowaj / odrzuć.

## Wybrany model i dane tekstowe

Aktualny model: gemma3:12b (zastępuje wcześniejszy 4B). Wyniki małego porównania jakości/czasu i jego ograniczenia opisuje docs/MODEL_COMPARISON.md. Profile (prompt v3, z ugruntowaniem cytatów w kodzie) uwzględniają opis, 15 najnowszych komentarzy i dowodów, zdjęcia, geo i metadane. Zakres materiału widać w szczegółach miejsca.

## Trwała baza i równoległość

Baza: data/scout.sqlite3, SQLite WAL, synchronous=FULL, busy_timeout=20 s. Miejsca, wybory, notatki, profile i stany kolejki pozostają po zamknięciu. Ścieżkę można zmienić przez PRZESWIT_DATA (starsze ADV_SCOUT_DATA nadal działa). Kopie online tworzy SQLite Backup API, następnie kontrola quick_check i atomowa zmiana nazwy. Raz dziennie powstaje data/backups/przeswit-YYYY-MM-DD.sqlite3; dodatkową kopię tworzy przycisk w „Importuj miejsca → Baza danych i kopie zapasowe”. Kopie nie są automatycznie kasowane. Są na tym samym dysku: dla ochrony przed awarią dysku skopiuj backup również na inny nośnik. Odtwarzaj po zatrzymaniu aplikacji; nie zastępuj pliku SQLite w trakcie pracy ani przy aktywnych plikach WAL.

Własny proces Ollama Prześwitu działa na 127.0.0.1:11435, OLLAMA_NUM_PARALLEL=2, jeden załadowany model. Korzysta z katalogu modeli `~/.ollama/models` (albo `OLLAMA_MODELS` / `PRZESWIT_MODELS`). Chmura i automatyczne porządkowanie modeli wyłączone dla tego procesu. Zwykła Ollama na porcie 11434 pozostaje osobną usługą. START.cmd / `python -m app` uruchamia lokalny silnik, jeśli potrzeba.

Profilowanie ma do dwóch wykonawców. Rezerwacje zadań używają BEGIN IMMEDIATE i trwałego statusu running. Zmiany źródła i wersji uniemożliwiają nadpisanie nowszego profilu starszą odpowiedzią. W interfejsie Auto / 1 / 2; Auto przyznaje dwa zadania na GPU >=18 GB i >=3 GB wolnego VRAM, jedno poniżej tego zapasu, wstrzymuje nowe zadania przy <1,5 GB VRAM albo <4 GB wolnego RAM. Gdy telemetria GPU niedostępna, limit wynosi jeden. Telemetria co 10 s; to ostrożny limit przyjmowania prac, nie gwarancja braku OOM. Już rozpoczęte analizy kończą się normalnie. Limit 2 został zweryfikowany na tym komputerze; więcej wolnego VRAM nie dowodzi korzyści z większej liczby zadań. Wyszukiwanie ma pierwszeństwo przed startem kolejnych profili.

Zdjęcia w bazie mogą być adresami URL, a nie lokalnymi plikami. Sama trwałość bazy nie zapewnia dostępności zewnętrznych fotografii offline.

## Lokalna pamięć zdjęć

Obrazy ze znanych, bezpośrednich adresów CDN zapisujemy w data/photos pod skrótem SHA-256 adresu. Metadane i błędy w tabeli photo_cache. Pobieramy wyłącznie adresy już zaimportowane w photos; nie skanujemy serwisów ani CDN w poszukiwaniu dodatkowych zdjęć. Pobieranie w tle działa równolegle (domyślnie 6 wątków, `PRZESWIT_PHOTO_PARALLEL` 1–10), starty żądań są rozłożone co 0,25 s, ten sam adres nigdy nie jest pobierany dwa razy naraz; cache jest współdzielony z profilowaniem. Limit 50 GiB całego cache, 6 MB na zdjęcie, rezerwa 2 GiB wolnego dysku. Przycisk wstrzymuje pobieranie wyprzedzające; analiza konkretnego miejsca nadal może pobrać potrzebne zdjęcie.

Galeria i model używają tego samego pliku. Lokalne zdjęcia są dostępne pod /photos/<skrót>, bez przekierowań na CDN. Ponowne użycie nie wymaga internetu. Pozostałe linki (np. stron galerii zamiast plików obrazów) nie są automatycznie pobierane. Odpowiedź 401/403/429 odkłada źródło na 24 godziny. Błędy pojedynczych zdjęć są odraczane na 24 godziny. Brak pliku na dysku przy zachowanych metadanych powoduje ponowne pobranie.

Kopia SQLite obejmuje metadane zdjęć, nie same pliki data/photos. Dla pełnej kopii offline zachowaj także ten folder. Lokalny cache nie zwiększa rozdzielczości fotografii i nie zmienia praw do treści; zachowane są oryginalne URL i podpisy.

Naprawa profilowania: dynamiczny schemat odpowiedzi ogranicza evidence do identyfikatorów rzeczywiście przekazanych modelowi. Usuwa to błędy placeholderów typu comment:N. Ograniczone długości list i zwiększony limit generacji zapobiegają części niepełnych odpowiedzi. Nadal działa ścisła walidacja; niezatwierdzona odpowiedź nie trafia do rankingu.

## Licencja

MIT — zobacz `LICENSE`. Leaflet (`app/static/vendor/`) na licencji BSD-2 (`app/static/vendor/LICENSE`).
