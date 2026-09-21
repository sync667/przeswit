@echo off
rem Uruchamia Cloudflare Tunnel (twoja domena -> 127.0.0.1:8765) wg data\cloudflared\config.yml, recznie. Log: data\cloudflared\tunnel.log
rem Sciezke do cloudflared mozna nadpisac zmienna CLOUDFLARED (domyslnie z PATH lub instalacja w Program Files).
cd /d "%~dp0.."
if "%CLOUDFLARED%"=="" set "CLOUDFLARED=cloudflared"
where cloudflared >nul 2>&1 || if exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" set "CLOUDFLARED=C:\Program Files (x86)\cloudflared\cloudflared.exe"
"%CLOUDFLARED%" tunnel --config "data\cloudflared\config.yml" --loglevel info run >> "data\cloudflared\tunnel.log" 2>&1
