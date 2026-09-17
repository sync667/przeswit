# Park4Night — dostęp i decyzja MVP

Sprawdzone 17/18.09.2026. To raport techniczny z publicznych materiałów, nie rozstrzygnięcie prawne.

| Obszar | Co sprawdzono | Wniosek |
|---|---|---|
| Strona | Zwykły GET podanego URL wyszukiwania zwrócił HTML | Możliwe publiczne otwarcie; nie sprawdzano kompletnego wyliczenia spotów |
| Robots | GET `/robots.txt`: blokady `/admin/` i stron użytkowników językowych; odnośnik sitemap | Brak zakazu tej ścieżki w robots nie udziela licencji na bazę |
| API | Wyszukanie oficjalnej dokumentacji i strony partnerów | Nie znaleziono oficjalnego otwartego kontraktu API/licencji zbiorczego pobierania |
| Warunki | Art. 2 i 5 CGU | Konsultacja indywidualna; reprodukcja treści/bazy wymaga uprawnienia. Odrębnie sprawdzić zdjęcia i linkowanie |
| Integracja | Strona partnerów zawiera współprace komercyjne | Nie jest dokumentacją API. Dostęp/warunki trzeba ustalić z operatorem |

Nie wykonano prób odtworzenia mobilnego API, logowania, obchodzenia CAPTCHA, limitów czy zabezpieczeń. Nie pobrano zbiorczo treści miejsc ani zdjęć. Publicznie opisane przez osoby trzecie endpointy nie są dowodem oficjalnego wsparcia lub licencji; MVP ich nie wykorzystuje.

Źródła pierwotne:

- [Warunki Park4Night](https://park4night.com/en/cgu) — art. 2: konsultacja indywidualna; art. 5: treści i baza, brak ogólnej licencji. Przepisy cytowane na stronie są stanowiskiem operatora.
- [robots.txt](https://park4night.com/robots.txt) — odczytany bezpośrednio zwykłym GET.
- [Podany URL](https://park4night.com/en/search?lat=50.92471783246766&lng=16.27261106762728&z=9) — odczytany bezpośrednio jako HTML; narzędzie wyszukiwarki zgłaszało błąd odczytu tej strony.
- [Partnerzy](https://park4night.com/en/partenaires) — brak dokumentacji API na sprawdzonej stronie.
- [Kontakt i operator](https://www.park4night.com/en/legal) — AppMobilEdition, kontakt wskazany na stronie.
- [Lasy Państwowe: wjazd do lasu](https://www.lasy.gov.pl/pl/informacje/faq/samochod/) — drogę przejezdną trzeba odróżnić od drogi dopuszczonej do ruchu pojazdów silnikowych.
- [Lasy Państwowe: biwakowanie](https://www.lasy.gov.pl/pl/informacje/faq/biwakowanie) — warunki biwakowania sprawdza się odrębnie od wjazdu; nie zakładamy, że obszar biwakowy daje prawo wjazdu motocyklem.
- [OpenAI Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create) — kontrakt analizy tekstu/obrazów. W prototypie stosujemy standardowy HTTP Responses API i wynik JSON schema.

Decyzja: adapter importu jest aktywny, zbiorcza integracja Park4Night pozostaje niezaimplementowana do czasu uzyskania oficjalnego kontraktu i uprawnień. Prototyp nie obiecuje „wszystkich spotów” i nie zamienia braku zakazu w zgodę. Nie wysłano żadnych wiadomości do operatora.
