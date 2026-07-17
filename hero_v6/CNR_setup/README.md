# HERO v6 UI - Guida all'Avvio (CNR_setup)

In questa cartella trovi le configurazioni e gli script per avviare la Dashboard di HERO v6, sia tramite **Docker** sia **senza container** (usando Python).

Scegli una delle seguenti modalità:

---

## Opzione 1: Docker Compose (Consigliato)
Esegue la UI all'interno di un server web Nginx e monta le cartelle locali per aggiornare l'interfaccia ad ogni modifica (hot-reload).

*   **Su Windows:** Fai doppio click sul file `run_ui_docker.bat`
*   **Su Linux / macOS:** Esegui nel terminale:
    ```bash
    chmod +x run_ui_docker.sh
    ./run_ui_docker.sh
    ```
*   **Indirizzo d'accesso:** **http://localhost:8080**

---

## Opzione 2: Server Python Locale (Senza Container)
Avvia un server HTTP leggero direttamente sul tuo computer usando Python.

*   **Su Windows:** Fai doppio click sul file `run_ui.bat`
*   **Su Linux / macOS:** Esegui nel terminale:
    ```bash
    chmod +x run_ui.sh
    ./run_ui.sh
    ```
*   **Indirizzo d'accesso:** **http://localhost:8080/UI/index.html**

---

### Nota sui Risultati della Time Series Analysis (TSA)
Entrambe le opzioni caricano automaticamente i grafici e i dati presenti nella cartella `hero_v6/TSA/results`.
