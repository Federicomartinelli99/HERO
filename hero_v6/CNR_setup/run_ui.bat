@echo off
echo =================================================================
echo  HERO v6 UI - Avvio Locale (Senza Container)
echo =================================================================
echo.

:: Vai alla cartella padre di CNR_setup (ovvero hero_v6)
cd %~dp0\..

echo Avvio del server HTTP di Python sulla porta 8080...
echo Cartella root del server: %CD%
echo.
echo L'interfaccia sara' accessibile all'indirizzo:
echo   http://localhost:8080/UI/index.html
echo.
echo [INFO] Premere CTRL+C in questa finestra per arrestare il server.
echo.

:: Avvia il browser predefinito all'indirizzo corretto
start http://localhost:8080/UI/index.html

:: Avvia il server http nativo di Python nella directory corrente (hero_v6)
python -m http.server 8080
