# SOLUM: sklep z ręcznie robionymi bransoletkami

Statyczna strona sklepu po polsku. Działa na każdym hostingu plików (Vercel, Netlify, GitHub Pages, zwykły serwer), bo gotowa strona to sam folder `public/`.

## Podgląd lokalny

Strona wymaga serwera, ponieważ podgląd 3D wczytuje modele przez sieć.

```bash
python -m http.server 5560 --directory public
```

Potem otwórz http://localhost:5560.

## Co gdzie leży

| Folder lub plik | Zawartość |
|---|---|
| `public/` | Gotowa strona. Ten folder wgrywa się na serwer. |
| `public/assets/js/solum.js` | Koszyk, panele, formularze |
| `public/assets/js/product.js` | Warianty, rozmiary, podgląd 3D |
| `public/assets/js/scroll.js` | Płynny powrót na górę po cofnięciu i po wejściu w produkt. Odległości zmienia się na początku pliku. |
| `public/assets/js/checkout.js` | Zamówienie i symulowana płatność |
| `zrodla/dane/config.json` | Dane firmy, dostawa, płatności, kody rabatowe, rozmiary |
| `zrodla/dane/products.json` | Produkty: nazwy, ceny, opisy, warianty, parametry modeli |
| `zrodla/dane/materials.json` | Karty materiałów |
| `zrodla/strony/` | Treść stron: główna, regulamin, kontakt i pozostałe |
| `zrodla/build.mjs` | Generator stron HTML |
| `zrodla/render/` | Tekstury i modele 3D (Python oraz Blender) |
| `zrodla/logo/` | Generator logo i wersje robocze |

## Jak wprowadzać zmiany

Teksty, ceny i dane firmy zmieniaj w `zrodla/`, a potem przebuduj strony:

```bash
node zrodla/build.mjs
```

Nie edytuj plików HTML w `public/`, ponieważ kolejne przebudowanie je nadpisze. Pliki CSS i JS w `public/assets/` edytuje się bezpośrednio.

## Modele i zdjęcia

Wszystkie obrazy produktów to rendery 3D, a nie fotografie. Modele powstają z parametrów zapisanych w `products.json`, dzięki czemu nowy wariant wymaga zwykle jednego wpisu w tym pliku.

Do ponownego wygenerowania potrzebny jest Blender 4.5:

```bash
cd zrodla/render
python textures.py tex
blender -b --factory-startup -P bracelets.py -- --out out/produkty --shots hero,macro,top,detail --all-shots --samples 160 --glb --skip-existing
blender -b --factory-startup -P scenes.py -- --out out/sceny --samples 200
python optimize.py
cd ../..
node zrodla/build.mjs
```

Gdy klient dostarczy prawdziwe zdjęcia, wystarczy podmienić pliki `public/assets/img/p/<produkt>/<wariant>-<ujęcie>-600.webp` i `-1200.webp` z zachowaniem nazw. Ujęcia to `hero`, `macro`, `detail` i `top`, a format to 4:5.

## Publikacja na GitHub Pages

Strona jest publikowana z gałęzi `gh-pages`, która zawiera wyłącznie zawartość folderu `public/`. Kod źródłowy leży na gałęzi `main`. Po każdej zmianie wystarczy uruchomić w cmd:

```cmd
publikuj.cmd
```

Skrypt przebudowuje strony, robi commit, wysyła `main` i aktualizuje `gh-pages`. Adres strony ustawia się w polu `siteUrl` w `zrodla/dane/config.json`. Teraz jest to `https://szumi32.github.io/solum`.

Dopóki `"demo": true`, wszystkie strony mają `noindex`, a `robots.txt` blokuje wyszukiwarki. Po przełączeniu na `false` strona zacznie się indeksować i powstanie `sitemap.xml`.

## Przed uruchomieniem sprzedaży

Pełna lista jest w pliku [DO-UZUPELNIENIA.md](DO-UZUPELNIENIA.md).
