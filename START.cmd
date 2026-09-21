@echo off
rem Windows: creates .venv, installs dependencies, starts the server at http://127.0.0.1:8765
rem Environment variables are read from data\przeswit.env (see przeswit.env.example).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv...
  python -m venv .venv || goto :error
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto :error
where ollama >nul 2>&1 || echo Note: ollama not found in PATH - AI profiling will not start ^(install from https://ollama.com, then: ollama pull gemma3:12b^)
".venv\Scripts\python.exe" -X utf8 -m app
pause
exit /b 0
:error
echo Could not prepare the environment. Check that Python 3.10+ is installed and in PATH.
pause
exit /b 1
