# Pipeline di Scraping IPC Country Analysis Reports
**Progetto HERO – Hunger Early-warning & Risk Optimizer**

---

## Obiettivo

Raccolta sistematica dei report ufficiali IPC (Integrated Food Security Phase Classification) pubblicati su [ipcinfo.org](https://www.ipcinfo.org/ipc-country-analysis/en/) per tutti i paesi disponibili nel periodo 2011–2026, limitatamente alle analisi di tipo **Acute Food Insecurity Classification**.

I documenti raccolti saranno utilizzati per analisi testuale dei driver della crisi alimentare e per il confronto semantico tra situazioni di crisi in paesi e periodi diversi, complementando i segnali quantitativi già raccolti (GDELT, ACLED, IOM DTM, WFP).

---

## Struttura della pipeline

La pipeline è divisa in due script Python indipendenti, eseguibili separatamente.

```
fase1_raccolta_url.py   →   link_estratti.json   →   fase2_download.py
```

Questa separazione permette di:
- Rieseguire solo il download senza ripetere la navigazione del sito
- Ispezionare e filtrare manualmente `link_estratti.json` prima del download
- Riprendere il download da dove si era interrotto in caso di errori

---

## Fase 1: Raccolta URL (`fase1_raccolta_url.py`)

### Funzionamento

Naviga la pagina lista di IPC Country Analysis applicando i filtri disponibili nel form:
- **Type of Analysis**: seleziona indice 1 (Acute Food Insecurity Classification)
- **Country**: itera su tutti i paesi disponibili nel dropdown `id_country`
- **Year**: itera sugli anni 2011–2026

Per ogni combinazione paese × anno, estrae tutte le righe di risultato (`div.dettaglio`) raccogliendo:
- Nome del paese
- Periodo di validità dell'analisi (es. `Aug 2018 / Feb 2019`)
- URL della pagina di dettaglio

### Gestione dei duplicati

Ogni report può comparire in più anni (un report con periodo `Aug 2018 / Feb 2019` compare sia nei risultati del 2018 che del 2019). I duplicati vengono rimossi tramite conversione a set di stringhe JSON prima del salvataggio finale.

### Output

File `link_estratti.json` con struttura:

```json
[
    {
        "paese": "Afghanistan",
        "periodo": "Aug 2018 / Feb 2019",
        "url": "https://www.ipcinfo.org/ipc-country-analysis/details-map/en/c/1151733/?iso3=AFG"
    },
    ...
]
```

### Note tecniche

- Usa `undetected_chromedriver` per bypassare il sistema Cloudflare di bot detection del sito
- `WebDriverWait` con timeout di 30 secondi per gestire caricamenti lenti
- `ctypes.windll.kernel32.SetThreadExecutionState` per impedire lo standby di Windows durante sessioni lunghe
- Il driver viene chiuso nel blocco `finally` per garantire la pulizia anche in caso di errori

---

## Fase 2: Download PDF e testi (`fase2_download.py`)

### Funzionamento

Legge `link_estratti.json` e per ogni entry naviga la pagina di dettaglio del report, eseguendo due operazioni:

**Estrazione testo Key Results**: cerca il contenitore `#kereres` nella pagina e salva il testo in un file `.txt` con intestazione (paese, periodo).

**Download PDF**: trova tutti i link con testo contenente "download" (case insensitive) tramite XPath, e per ciascuno:
1. Determina se il documento è uno **snapshot** (il testo del link o l'href contiene "snapshot")
2. Imposta dinamicamente la cartella di destinazione tramite CDP (`Browser.setDownloadBehavior`)
3. Esegue il click tramite `ActionChains` (simula un click utente reale, necessario per i permessi di download di Chrome)

### Meccanismo anti-ban

Il browser viene riavviato ogni 50 pagine elaborate per ridurre il rischio di rilevamento automatico da parte del server. Nella sessione completa il browser è stato riavviato 10 volte.

### Struttura delle cartelle di output

```
pdf_report/
├── Afghanistan_Aug_2018_-_Feb_2019/
│   └── IPC_Afghanistan_AcuteFoodInsec_report.pdf
├── Afghanistan_Mar_2021_-_Nov_2021/
│   └── ...
└── ...

pdf_snapshot/
├── IPC_Afghanistan_snapshot_2021.pdf
└── ...

key_results_testi/
├── Afghanistan_Aug_2018_-_Feb_2019_KeyResults.txt
├── Afghanistan_Mar_2021_-_Nov_2021_KeyResults.txt
└── ...
```

Ogni sottocartella in `pdf_report/` corrisponde a una coppia univoca `(paese, periodo)` — questo garantisce che nella fase di analisi testuale successiva non vengano processati due volte gli stessi dati, e che report completi e snapshot siano tenuti separati.

### Separazione report / snapshot

I **report completi** (20–30 pagine) contengono analisi dettagliate per distretto/regione con driver della crisi, indicatori nutrizionali, proiezioni e raccomandazioni. Gli **snapshot** sono riassunti di 1–2 pagine non sempre presenti per ogni analisi. Questa separazione è importante perché i due tipi di documento hanno struttura e livello di dettaglio molto diversi.

### Note tecniche

- `Browser.setDownloadBehavior` (Chrome DevTools Protocol) cambia dinamicamente la cartella di download tra un click e l'altro senza riaprire il browser
- `ActionChains.move_to_element().click()` invece del click diretto per bypassare elementi sovrapposti nel DOM che causavano `ElementClickInterceptedException`
- Pausa di 3 secondi tra click successivi per evitare download simultanei
- `plugins.always_open_pdf_externally: True` forza il download dei PDF invece dell'anteprima inline

---

## Dipendenze

```bash
pip install undetected-chromedriver selenium webdriver-manager
```

| Libreria | Scopo |
|---|---|
| `undetected-chromedriver` | Bypass Cloudflare bot detection |
| `selenium` | Automazione browser |
| `webdriver-manager` | Download automatico ChromeDriver compatibile |
| `ctypes` (stdlib) | Prevenzione standby Windows |

**Chrome**: versione 149 (ChromeDriver scaricato automaticamente dalla versione corrispondente)

---

## Risultati

### Fase 1 – Raccolta URL

| Metrica | Valore |
|---|---|
| Anni esplorati | 2011–2026 |
| Paesi esplorati | 45 |
| Paesi con almeno un report disponibile | 36 |
| Combinazioni paese × anno senza risultati | 358 |
| Link unici salvati in `link_estratti.json` | 502 |
| Di cui nel periodo 2017–2025 | 390 |

I 9 paesi esplorati senza risultati disponibili sono probabilmente paesi per i quali IPC non ha condotto analisi di tipo Acute Food Insecurity Classification nel periodo considerato, o per i quali le analisi sono catalogate con una denominazione diversa nel sistema.

### Paesi con più report disponibili (top 10)

| Paese | Report disponibili |
|---|---|
| Somalia | 48 |
| Honduras | 47 |
| South Sudan | 46 |
| Central African Republic | 36 |
| Madagascar | 36 |
| Guatemala | 35 |
| Democratic Republic of the Congo | 34 |
| Kenya | 34 |
| Sudan | 34 |
| Uganda | 32 |

### Lista completa dei 36 paesi coperti

Afghanistan, Angola, Bangladesh, Burundi, Cambodia, Central African Republic, Democratic Republic of the Congo, Djibouti, Dominican Republic, Ecuador, El Salvador, Eswatini, Ethiopia, Gaza Strip, Guatemala, Haiti, Honduras, Kenya, Lebanon, Lesotho, Madagascar, Malawi, Mozambique, Namibia, Pakistan, Somalia, South Africa, South Sudan, Sudan, Tajikistan, Timor-Leste, Uganda, United Republic of Tanzania, Yemen, Zambia, Zimbabwe.

### Fase 2 – Download

| Metrica | Valore |
|---|---|
| Pagine elaborate | 502 |
| Testi Key Results salvati | 501 |
| Testi Key Results non trovati | 1 |
| Download PDF avviati (click) | 860 |
| Errori click | 1 |
| Errori generali di pagina | 0 |
| Riavvii browser (anti-bot, ogni 50 pagine) | 10 |

Il tasso di successo dell'estrazione testuale è del 99,8% (501/502). L'unico caso non trovato corrisponde ad una pagina dove non era presente la sezione 'Key results'.
---

## Utilizzo nella pipeline HERO

```
link_estratti.json
        ↓
pdf_report/{paese}_{periodo}/    →   Estrazione testo 
                                              ↓
                                     Analisi testuale 
                                              ↓
                                     Embedding semantici
                                              ↓
                                     Confronto tra situazioni di crisi

pdf_snapshot/                    →   Analisi separata (testi di sintesi)

key_results_testi/               →   Analisi testuale rapida senza PDF