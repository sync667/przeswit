# Windows PowerShell: creates .venv, installs dependencies, starts the server at http://127.0.0.1:8765
# Environment variables are read from data\przeswit.env (see przeswit.env.example). Alternative: START.cmd
Set-Location -Path $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) { python -m venv .venv; if ($LASTEXITCODE) { Write-Error 'Python 3.10+ not found'; exit 1 } }
& '.venv\Scripts\python.exe' -m pip install -q -r requirements.txt
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { Write-Host "Note: 'ollama' not found in PATH - AI profiling will not start (install from https://ollama.com, then: ollama pull gemma3:12b)" }
& '.venv\Scripts\python.exe' -X utf8 -m app
