# Prześwit

Lokalna biblioteka miejsc w naturze. Uruchom START.cmd albo `python -m app` (Python 3.10+, bez zależności zewnętrznych) i otwórz http://127.0.0.1:8765.

Duże karty pokazują zdjęcia bez otwierania szczegółów. Strzałki zmieniają zdjęcie; kliknięcie otwiera większą galerię. Odrzuć / Zachowaj do oceny zapisują wybór w SQLite. Cofnij odwraca ostatnią decyzję. Zakładki: Do przejrzenia, Zachowane, Odrzucone, Wszystkie. Odrzucenie nie usuwa danych.

Importuj miejsca przyjmuje JSON, GeoJSON, CSV, GPX i ZIP. Możesz też umieścić pliki w inbox. Przykład struktury w examples/template.json. Ponowny import zachowuje notatki. Domyślnie widać całą bazę i tylko rekordy ze zdjęciami; filtr można wyłączyć. Zdjęcia zewnętrzne potrzebują internetu. Nie są zastępowane fikcyjnymi widokami.

Baza i notatki: data/scout.sqlite3 (historyczna nazwa pliku zachowana dla ciągłości). Kopię zapasową całego data wykonuj po zatrzymaniu aplikacji. Nie publikuj bazy ani cache wraz z kodem. Rankingi to wskazówki z dostępnych danych, nie potwierdzenie dojazdu lub zgody na namiot.

Logo: własny znak SVG, prześwit z linią krajobrazu i słońcem. Kolory: leśny #203f35, papier #f6f4ef, bursztyn #e5aa61.

Testy: `python -m unittest discover -s tests -t .` (albo `pytest`).

## Struktura projektu

```
app/                 pakiet Pythona (backend)
  server.py          serwer HTTP (stdlib), API i pliki statyczne
  storage.py         SQLite, kopie zapasowe, ustawienia
  core.py            normalizacja, filtry obszaru, ranking
  importers.py       import JSON/GeoJSON/CSV/GPX/ZIP i folder inbox
  providers.py       konektory publicznych danych (OSM, BDL)
  public_web.py      pobieranie Park4Night
  sync.py            zadania synchronizacji obszarów
  ai_runtime.py      własny proces Ollama (127.0.0.1:11435), telemetria zasobów
  local_vision.py    lokalne wnioskowanie na zdjęciach
  profiles.py        automatyczne profile miejsc i wyszukiwanie opisem
  photo_cache.py     lokalna pamięć zdjęć (data/photos)
  prompts/           prompty modelu
static/              frontend: index.html, app.js, style.css, logo.svg, vendor/leaflet
examples/            template.json (szablon importu), demo.json (dane demonstracyjne)
tests/               testy unittest
docs/                notatki badawcze, porównanie modeli, raport weryfikacji
data/                baza, kopie, cache zdjęć, logi (ignorowane przez git)
inbox/               obserwowany folder eksportów (ignorowany przez git)
```

## Lokalne dopasowanie zdjęć

Ollama i model gemma3:4b. Model pobierzesz poleceniem `ollama pull gemma3:4b`. Uruchom Ollamę przed analizą. Wpisz oczekiwania, wybierz „Zbadaj zdjęcia z tej strony” (maks. 24 rekordy, kolejno) albo przycisk w szczegółach miejsca. Możesz zatrzymać kolejkę po bieżącym miejscu. Analiza obejmuje do 3 zdjęć, opis, komentarze i kontekst z importu. Wyniki zapisują się lokalnie i sortują miejsca według dopasowania do aktualnego opisu; zmiana opisu wymaga nowej analizy. Odrzucone i zachowane wybory pozostają niezależne od AI.

Obrazy mogą być osadzone w JSON jako data:image/jpeg;base64, data:image/png;base64 lub data:image/webp;base64. Automatycznie pobierane są bezpośrednie obrazy z cdn3.park4night.com, cdn6.park4night.com i upload.wikimedia.org. Linki do stron galerii nie są obrazami. Inne źródła wymagają osadzenia obrazów w imporcie. Limit 6 MB na obraz, przekierowania wyłączone. Nie ma analizy zastępczej samym tekstem, gdy żaden obraz nie został wczytany.

Wnioskowanie odbywa się wyłącznie przez lokalny adres 127.0.0.1:11434, bez płatnego API. Korzysta z zasobów komputera i energii. Ocena jest subiektywna; model nie potwierdza legalności ani dojazdu. Zdjęcia i opisy nie otrzymują uprawnień do wykonywania narzędzi.

## Automatyczne profile i wyszukiwanie — aktualny tryb

Zastępuje ręczne ocenianie stron opisane powyżej. Każda nowa lub zmieniona lokacja otrzymuje profil w tle, niezależny od prompta wyszukiwania. Obecna baza jest profilowana tą samą kolejką. Po starcie i co 15 sekund wykrywane są zmiany danych. Tabela SQLite profiles przechowuje stan, wersję prompta, skrót danych źródłowych, błędy i wynik. Restart wznawia przerwane rekordy, błędy mają maksymalnie trzy automatyczne próby z odstępem; interfejs pozwala ponowić je ręcznie i wstrzymać pracę po bieżącym miejscu. Jedna analiza naraz.

Pełny prompt klasyfikacji: app/prompts/profile_prompt.md. Katalog ma 37 cech, m.in. krajobraz, wodę, nawierzchnię, namiot, motocykl, prywatność, ruch, udogodnienia, koszty i ryzyka. Każda rozpoznana cecha ma natężenie, pewność, uzasadnienie i odniesienia do źródeł. Do 5 zdjęć i do 15 komentarzy / dowodów na rekord. Brak zdjęć oznacza profil text_only, a nie udawaną analizę obrazu. Zmiany treści pod niezmienionym URL zdjęcia nie są wykrywane bez nowego importu z innymi danymi.

Szukaj według opisu uruchamia drugi prompt modelu: tłumaczy życzenie na cechy, ich pożądane wartości, wagi i wymagania konieczne. Potem kod porównuje WSZYSTKIE gotowe aktualne profile, nie tylko bieżącą stronę. Wynik uwzględnia pewność dowodów, a nieznane cechy nie spełniają wymagań. Plan jest pokazany w „Jak AI zrozumiało wyszukiwanie?”. Niewspierane wymagania są ujawniane. Dokładna geografia powinna być określona filtrami obszaru; model nie jest silnikiem tras ani weryfikatorem zgód. Złożone alternatywy są przybliżane wagami, nie pełną logiką boolowską.

Wyniki wyszukiwania są migawką gotowych profili i wymagają ponownego wyszukania, by uwzględnić zakończone później analizy. Oceny dopasowania są ważone według pewności; 0 nie oznacza potwierdzonej nieprzydatności. Profilowanie nie zmienia zapisanych/odrzuconych wyborów. Profile pozostają w bazie także przy ponownym imporcie identycznych danych.

## Wybrany model i dane tekstowe

Aktualny model: gemma3:12b (zastępuje wcześniejszy 4B). Wyniki małego porównania jakości/czasu i jego ograniczenia opisuje docs/MODEL_COMPARISON.md. Profile v2 uwzględniają opis, 15 najnowszych komentarzy i dowodów, zdjęcia, geo i metadane. Zakres materiału widać w szczegółach miejsca.

## Trwała baza i równoległość

Baza: data/scout.sqlite3, SQLite WAL, synchronous=FULL, busy_timeout=20 s. Miejsca, wybory, notatki, profile i stany kolejki pozostają po zamknięciu. Ścieżkę można zmienić przez PRZESWIT_DATA (starsze ADV_SCOUT_DATA nadal działa). Kopie online tworzy SQLite Backup API, następnie kontrola quick_check i atomowa zmiana nazwy. Raz dziennie powstaje data/backups/przeswit-YYYY-MM-DD.sqlite3; dodatkową kopię tworzy przycisk w „Importuj miejsca → Baza danych i kopie zapasowe”. Kopie nie są automatycznie kasowane. Są na tym samym dysku: dla ochrony przed awarią dysku skopiuj backup również na inny nośnik. Odtwarzaj po zatrzymaniu aplikacji; nie zastępuj pliku SQLite w trakcie pracy ani przy aktywnych plikach WAL.

Własny proces Ollama Prześwitu działa na 127.0.0.1:11435, OLLAMA_NUM_PARALLEL=2, jeden załadowany model. Korzysta z istniejącego katalogu D:\Ollama; można ustawić PRZESWIT_MODELS. Chmura i automatyczne porządkowanie modeli wyłączone dla tego procesu. Zwykła Ollama na porcie 11434 pozostaje osobną usługą. START.cmd / `python -m app` uruchamia lokalny silnik, jeśli potrzeba.

Profilowanie ma do dwóch wykonawców. Rezerwacje zadań używają BEGIN IMMEDIATE i trwałego statusu running. Zmiany źródła i wersji uniemożliwiają nadpisanie nowszego profilu starszą odpowiedzią. W interfejsie Auto / 1 / 2; Auto przyznaje dwa zadania na GPU >=18 GB i >=3 GB wolnego VRAM, jedno poniżej tego zapasu, wstrzymuje nowe zadania przy <1,5 GB VRAM albo <4 GB wolnego RAM. Gdy telemetria GPU niedostępna, limit wynosi jeden. Telemetria co 10 s; to ostrożny limit przyjmowania prac, nie gwarancja braku OOM. Już rozpoczęte analizy kończą się normalnie. Limit 2 został zweryfikowany na tym komputerze; więcej wolnego VRAM nie dowodzi korzyści z większej liczby zadań. Wyszukiwanie ma pierwszeństwo przed startem kolejnych profili.

Zdjęcia w bazie mogą być adresami URL, a nie lokalnymi plikami. Sama trwałość bazy nie zapewnia dostępności zewnętrznych fotografii offline.

## Lokalna pamięć zdjęć

Obrazy ze znanych, bezpośrednich adresów CDN zapisujemy w data/photos pod skrótem SHA-256 adresu. Metadane i błędy w tabeli photo_cache. Pobieramy wyłącznie adresy już zaimportowane w photos; nie skanujemy serwisów ani CDN w poszukiwaniu dodatkowych zdjęć. Pobieranie w tle jest seryjne, najwyżej jedno nowe żądanie na 2 sekundy, i współdzieli cache z profilowaniem. Limit 50 GiB całego cache, 6 MB na zdjęcie, rezerwa 2 GiB wolnego dysku. Przycisk wstrzymuje pobieranie wyprzedzające; analiza konkretnego miejsca nadal może pobrać potrzebne zdjęcie.

Galeria i model używają tego samego pliku. Lokalne zdjęcia są dostępne pod /photos/<skrót>, bez przekierowań na CDN. Ponowne użycie nie wymaga internetu. Pozostałe linki (np. stron galerii zamiast plików obrazów) nie są automatycznie pobierane. Odpowiedź 401/403/429 odkłada źródło na 24 godziny. Błędy pojedynczych zdjęć są odraczane na 24 godziny. Brak pliku na dysku przy zachowanych metadanych powoduje ponowne pobranie.

Kopia SQLite obejmuje metadane zdjęć, nie same pliki data/photos. Dla pełnej kopii offline zachowaj także ten folder. Lokalny cache nie zwiększa rozdzielczości fotografii i nie zmienia praw do treści; zachowane są oryginalne URL i podpisy.

Naprawa profilowania: dynamiczny schemat odpowiedzi ogranicza evidence do identyfikatorów rzeczywiście przekazanych modelowi. Usuwa to błędy placeholderów typu comment:N. Ograniczone długości list i zwiększony limit generacji zapobiegają części niepełnych odpowiedzi. Nadal działa ścisła walidacja; niezatwierdzona odpowiedź nie trafia do rankingu.
