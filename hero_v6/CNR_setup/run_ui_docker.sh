#!/bin/bash
echo "================================================================="
echo " HERO v6 UI - Avvio con Docker Compose - Linux/macOS"
echo "================================================================="
echo ""

# Posizionati nella cartella contenente lo script (CNR_setup)
cd "$(dirname "$0")" || exit

echo "Avvio dei container Docker tramite Docker Compose..."
echo ""
echo "L'interfaccia sara' accessibile all'indirizzo:"
echo "  http://localhost:8080"
echo ""
echo "[INFO] Premere CTRL+C per arrestare i container."
echo ""

# Prova ad aprire il browser predefinito
if command -v xdg-open > /dev/null; then
    xdg-open http://localhost:8080 &
elif command -v open > /dev/null; then
    open http://localhost:8080 &
fi

# Rileva ed esegui docker compose
if command -v docker-compose > /dev/null; then
    docker-compose up --build
elif docker compose version > /dev/null 2>&1; then
    docker compose up --build
else
    echo "Errore: Docker Compose (docker compose o docker-compose) non e' installato!"
    exit 1
fi
