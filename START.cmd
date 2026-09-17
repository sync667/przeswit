@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Tworze srodowisko .venv...
  python -m venv .venv || goto :error
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto :error
".venv\Scripts\python.exe" -m app
pause
exit /b 0
:error
echo Nie udalo sie przygotowac srodowiska. Sprawdz, czy Python 3.10+ jest zainstalowany.
pause
exit /b 1
