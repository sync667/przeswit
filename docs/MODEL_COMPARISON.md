# Dobór modelu lokalnego — 2026-09-18

Sprzęt: NVIDIA RTX 3090 Ti, 23028 MiB VRAM raportowane przez sterownik; 137262026752 bajtów pamięci RAM (około 128 GiB).

Wybrano Gemma 3 12B jako domyślny model profili oraz interpretacji wyszukiwania. Wariant Ollama waży około 8,1 GB na dysku. Nie jest to test wszystkich dostępnych modeli ani dowód ogólnej przewagi; porównanie obejmuje dwa kontrolowane przypadki, po jednym przebiegu na model. Czasy obejmują żądanie modelu i ewentualne jego ładowanie. Zdjęcie pobrano przed pomiarem.

| Próba | 4B | 12B |
|---|---|---|
| Jedno prawdziwe zdjęcie + kontrolowany opis i sprzeczne komentarze | 5,24 s, poprawna struktura, błędnie potraktował brak toalety/wody jako brak informacji, nie przypisał cech do komentarzy | 17,56 s, poprawna struktura, uwzględnił błoto, hałas i starszą sprzeczną relację, użył comment:0 i comment:1 |
| Sam tekst: płatne miejsce, brak gór i wody, komentarz o szlabanie | 6,17 s, odrzucona odpowiedź z nieidentyfikowalnym źródłem | 13,54 s, poprawna struktura, negacje i opłata zachowane, szlaban przypisany komentarzowi |

12B nadal może wnioskować zbyt daleko (np. sugerować liczbę osób na podstawie rodzaju obiektu). Skale nie są prawdopodobieństwem ani dowodem legalności. Profil oddziela obserwacje, niewiadome, sprzeczności i źródła. Walidacja identyfikatorów nie dowodzi prawdziwości twierdzenia.

Profile v2 analizują zdjęcia, opis, 15 najnowszych komentarzy, 15 najnowszych dowodów, geo, typ i dostępne metadane. Zakres jest zapisany w source_coverage i widoczny w karcie. Poprzednie profile są ponownie kolejkowane. Brak komentarzy w imporcie oznacza brak ich analizy; program ich nie wymyśla ani nie pobiera samodzielnie ze stron.

Źródło specyfikacji: https://ollama.com/library/gemma3
