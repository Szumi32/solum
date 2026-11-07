@echo off
rem Publikuje strone SOLUM na GitHub Pages.
rem Buduje strony, zapisuje zmiany na galezi main i wysyla folder public na galaz gh-pages.
cd /d "%~dp0"

node zrodla\build.mjs
if errorlevel 1 goto blad

git add -A
git diff --cached --quiet || git commit -m "Aktualizacja strony"

git push -u origin main
if errorlevel 1 goto blad

git subtree push --prefix public origin gh-pages
if errorlevel 1 goto blad

echo.
echo Gotowe. Strona odswiezy sie w ciagu 1-2 minut: https://szumi32.github.io/solum/
exit /b 0

:blad
echo.
echo Publikacja przerwana. Przeczytaj komunikat powyzej.
exit /b 1
