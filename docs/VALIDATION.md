# Weryfikacja Prześwitu — 2026-09-18

34 testy backendu zakończone powodzeniem. static/app.js przeszedł sprawdzenie składni Node.
Przeniesienie SQLite: suma SHA-256 przed i po identyczna; integrity_check = ok, 1163 miejsca.
W przeglądarce sprawdzono galerię z rzeczywistymi zdjęciami, zachowanie miejsca, trwałość wyboru po odświeżeniu, zakładkę zachowanych, odrzucenie, cofnięcie. Wybór testowy przywrócono do stanu początkowego.
Zdjęcia są odnośnikami źródłowymi: mogą zniknąć lub wymagać internetu. Brakujące obrazy pokazują komunikat, a nie zastępczą fotografię. Automatyczne oceny nie potwierdzają legalności biwaku ani przejezdności drogi.

Automatyczne profile: 47 testów przeszło (kolejka po restarcie, zmiana danych źródłowych, nieznane cechy, negacje, pewność, nieistniejące dowody i wymyślone warunki zapytania). Potwierdzono na prawdziwych rekordach zapis wielu profili w tle, wznowienie po restarcie oraz wyszukiwanie po gotowych profilach. Część odpowiedzi modelu jest odrzucana przez walidację dowodów i trafia do ponowienia zamiast do rankingu. Pełne profilowanie 1163 rekordów jest zadaniem w tle; test nie oznacza zakończenia całej kolejki.

Baza i równoległość: 52 testy przeszły. Test 12 atomowych rezerwacji przez 4 wątki bez duplikatów; spójna kopia SQLite zachowała miejsca i notatkę, integrity_check=ok. Na rzeczywistym modelu 12B log silnika potwierdził równoczesne generowanie slot 0/task 2 i slot 1/task 0; UI pokazało 2/2, ~9 GB wolnego VRAM. Kopia dzienna utworzona dla 1163 miejsc.

Cache i profilowanie: 54 testy przeszły. Dwa równoległe odczyty tego samego URL pobierają obraz raz; ponowny odczyt działa bez sieci; serwer nie przyjmuje traversal w ścieżce zdjęcia. Schemat wyklucza nieistniejące komentarze i zdjęcia. Odtworzono błąd park4night:103712 (comment:N), po ograniczeniu enum odpowiedź przeszła walidację. UI potwierdziło pobrane zdjęcia, brak bieżących błędów kolejki po ponowieniu i lokalny src /photos/... dla (58-540) Pole Namiotowe.
