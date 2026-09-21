@echo off
rem Uruchamia serwer Przeswitu w tle (recznie). Zmienne z data\przeswit.env (KEY=VALUE, wzor: przeswit.env.example). Log: data\app.log
cd /d "%~dp0.."
if exist "data\przeswit.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%a in ("data\przeswit.env") do set "%%a=%%b"
)
".venv\Scripts\python.exe" -X utf8 -m app >> "data\app.log" 2>&1
