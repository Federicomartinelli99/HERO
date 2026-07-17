#!/bin/bash
echo "================================================================="
echo " HERO v6 UI - Avvio Locale (Senza Container) - Linux/macOS"
echo "================================================================="
echo ""

# Vai alla cartella padre di CNR_setup (ovvero hero_v6)
cd "$(dirname "$0")/.." || exit

echo "Avvio del server HTTP di Python sulla porta 8080..."
echo "Cartella root del server: $(pwd)"
echo ""
echo "L'interfaccia sara' accessibile all'indirizzo:"
echo "  http://localhost:8080/UI/index.html"
echo ""
echo "[INFO] Premere CTRL+C per arrestare il server."
echo ""

# Prova ad aprire il browser predefinito in base al sistema operativo
if command -v xdg-open > /dev/null; then
    xdg-open http://localhost:8080/UI/index.html &
elif command -v open > /dev/null; then
    open http://localhost:8080/UI/index.html &
fi

# Rileva e avvia Python
if command -v python3 > /dev/null; then
    python3 -m http.server 8080
elif command -v python > /dev/null; then
    python -m http.server 8080
else
    echo "Errore: Python non e' installato nel sistema!"
    exit 1
fi
