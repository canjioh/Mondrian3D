@echo off
REM ============================================================
REM  Avvia Mondrian 3D: mini-server locale + apertura browser.
REM  (I browser bloccano i moduli JS aperti come file://,
REM   quindi serviamo la pagina via http://localhost.)
REM ============================================================
cd /d "%~dp0"
echo.
echo   Avvio del server locale su http://localhost:8000 ...
echo   (chiudi la finestra del server per fermare l'app)
echo.
start "Mondrian3D server" cmd /c "python -m http.server 8000"
timeout /t 1 >nul
start "" "http://localhost:8000/mondrian3d.html"
