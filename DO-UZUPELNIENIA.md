# SOLUM: co trzeba uzupełnić przed startem

Strona jest kompletna jako makieta sklepu. Poniższe rzeczy może dostarczyć lub potwierdzić tylko właściciel sklepu.

## 1. Dane firmy

Plik `zrodla/dane/config.json`, sekcja `shop`. Teraz są tam wartości zastępcze:

- nazwa firmy, adres, NIP, REGON
- e-mail (`kontakt@solum.example` to adres nieistniejący) i telefon
- godziny pracy, bank i numer konta
- profil Instagram

Po zmianie uruchom `node zrodla/build.mjs`.

## 2. Prawdziwe zamówienia i płatności

Obecnie sklep to makieta. Te elementy nie wykonują prawdziwych działań:

| Element | Stan teraz | Co trzeba zrobić |
|---|---|---|
| Płatność | Symulowana, bez pobierania pieniędzy i danych karty | Podpiąć operatora, np. Przelewy24, PayU lub Stripe |
| Zamówienie | Zapisane tylko w przeglądarce klienta | Dodać backend albo przenieść sklep na platformę sprzedażową |
| E-mail z potwierdzeniem | Nie jest wysyłany | Podpiąć usługę wysyłki e-maili |
| Formularz kontaktowy | Sprawdza pola, ale niczego nie wysyła | Podpiąć serwis formularzy lub własny backend |
| Newsletter | Sprawdza adres, ale go nie zapisuje | Podpiąć narzędzie do newslettera |
| Wybór paczkomatu | Ręczne wpisanie kodu i link do mapy | Podpiąć widżet InPost Geowidget |
| Stany magazynowe | Brak, wszystko jest dostępne | Dodać, jeśli część modeli będzie mieć limit sztuk |

Dopóki `"demo": true` w `config.json`, klient widzi informację, że płatność jest symulowana. **Nie zmieniaj tej wartości na `false`, dopóki płatności i zamówienia nie działają naprawdę.** W przeciwnym razie klient uzna, że zapłacił i złożył zamówienie.

## 3. Treści do potwierdzenia przez właściciela

Te teksty są propozycją i opisują obietnice wobec klienta. Właściciel musi potwierdzić, że są prawdziwe, albo je zmienić:

- **Cechy materiałów:** kamienie niebarwione, bursztyn niepodgrzewany i nieprasowany, skóra bez soli chromu, jedwab barwiony roślinnie, wosk pszczeli, olej lniany.
- **Hasło „100% naturalne”:** obowiązuje tylko wtedy, gdy naprawdę nie ma metalu, plastiku, gumki ani kleju syntetycznego. Nieprawdziwe hasło może zostać uznane za wprowadzanie w błąd.
- **Pochodzenie:** krzemień z Gór Świętokrzyskich, dąb bagienny z dolin polskich rzek. Przy pozostałych kamieniach podane są typowe złoża, a nie potwierdzone źródło partii.
- **Sposób pracy:** opis pracowni, dobór pod lupą, ścieg siodlarski, gięcie drewna parą, suszenie przez dwa tygodnie, szlif do gradacji 2000.
- **Warunki:** nadanie w 3 dni robocze, 30 dni na zwrot, 2 lata bezpłatnych napraw (wartości w `config.json`).
- **Ceny i koszty dostawy:** wszystkie są przykładowe. Sprawdź też ceny przewoźników.
- **Kod rabatowy:** `WITAJ10` to przykład. Usuń go lub zmień.
- **Waga produktów:** wartości są szacunkowe.

## 4. Zdjęcia

Wszystkie obrazy to rendery 3D. Do czasu wykonania prawdziwych zdjęć warto je tak oznaczać, bo produkt nie może wyglądać inaczej niż to, co klient dostanie. Nazwy plików do podmiany opisuje `README.md`. Strona nie zawiera opinii klientów, bo żadnych jeszcze nie ma i nie wolno ich wymyślać.

## 5. Sprawy prawne

- **Regulamin i polityka prywatności** to szablony. Przed startem powinien je sprawdzić prawnik. W tekstach są też nawiasy kwadratowe do uzupełnienia: operator płatności, lista odbiorców danych, data obowiązywania.
- **Nazwa SOLUM:** wyszukiwarka nie pokazała sklepu z biżuterią o tej nazwie, ale nie jest to badanie znaków towarowych. Przed wydatkami na markę sprawdź bazy UPRP i EUIPO oraz profile społecznościowe.
- **Domena:** `solum.pl`, `solum.com.pl`, `solum.store` i `solum.studio` mają już rekordy DNS, więc prawdopodobnie są zajęte. `solumstudio.pl` nie ma rekordu DNS, ale to nie dowodzi, że jest wolna. Sprawdź to u rejestratora.
- **Dane producenta na karcie produktu** (wymóg rozporządzenia GPSR) pobierają się z `config.json`.

## 6. Technika przed publikacją

- Jeśli strona trafi na własną domenę, zmień `siteUrl` w `config.json`. Teraz jest tam adres GitHub Pages.
- Makieta jest ukryta przed wyszukiwarkami, dopóki działa tryb demo. Przełącz go dopiero razem z prawdziwymi płatnościami i danymi.
- Ustaw stronę błędu 404 na `404.html` u dostawcy hostingu.
- Podepnij domenę i HTTPS.
- Jeśli dodasz analitykę lub piksele reklamowe, dodaj baner zgód i zaktualizuj politykę prywatności. Teraz strona ich nie używa, więc baner nie jest potrzebny.
