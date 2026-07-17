@echo off
echo =================================================================
echo  HERO v6 UI - Avvio con Docker Compose
echo =================================================================
echo.

:: Vai alla cartella del file .bat (CNR_setup)
cd %~dp0

echo Avvio dei container Docker tramite Docker Compose...
echo.
echo L'interfaccia sara' accessibile all'indirizzo:
echo   http://localhost:8080
echo.
echo [INFO] Premere CTRL+C in questa finestra per arrestare i container.
echo.

:: Avvia il browser predefinito all'indirizzo corretto (porta 8080 mappata da docker)
start http://localhost:8080

:: Avvia docker compose
docker compose up --build
