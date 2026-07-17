import ctypes
import os
import time
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc

#WINDOW_SPOSTATA = True  

DOWNLOAD_DIR = os.path.abspath("pdf_report")
TESTO_DIR = os.path.abspath("key_results_testi")
SNAPSHOT_DIR = os.path.abspath("pdf_snapshot")

for d in [DOWNLOAD_DIR, SNAPSHOT_DIR, TESTO_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

def impedisci_standby():
    """ Impedisce a Windows di spegnere lo schermo o andare in standby """
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)

def ripristina_standby():
    """ Ripristina la normale gestione del risparmio energetico di Windows """
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)


def configura_driver():
    options = uc.ChromeOptions()
    #options.add_argument("--window-size=1366,768")
    #if WINDOW_SPOSTATA:
    #    options.add_argument("--window-position=-2000,0") 
    options.add_experimental_option(
        "prefs", {
            "download.default_directory": DOWNLOAD_DIR,
            "plugins.always_open_pdf_externally": True,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
        }
    )
    return uc.Chrome(driver_executable_path=ChromeDriverManager(driver_version="149").install(), options=options)

# Controllo se il file dei link esiste
if not os.path.exists("link_estratti.json"):
    print("Errore: Il file 'link_estratti.json' non esiste. Avvia prima la Fase 1.")
    exit()

with open("link_estratti.json", "r", encoding="utf-8") as f:
    pagine_da_elaborare = json.load(f)

print(f"--- INIZIO FASE 2: Download di {len(pagine_da_elaborare)} elementi ---")
# Blocca lo standby prima di far partire il browser
impedisci_standby()

contatore_pagine = 0
LIMITE_RIATTIVAZIONE = 50  # Riavvia il browser ogni 50 pagine

try:
    driver = configura_driver()
    wait = WebDriverWait(driver, 20)
    
    for item in pagine_da_elaborare:

        if contatore_pagine > 0 and contatore_pagine % LIMITE_RIATTIVAZIONE == 0:
            print(f"\n[Anti-Bot] Raggiunte {contatore_pagine} pagine. Riavvio del browser in corso...")
            driver.close()
            time.sleep(5)  # Pausa di sicurezza prima di riaprire
            driver = configura_driver()
            wait = WebDriverWait(driver, 20)
        
        contatore_pagine += 1


        paese = item["paese"]
        periodo = item["periodo"]
        url_dettaglio = item["url"]
        
        try:
            print(f"\nElaborazione: {paese} | {periodo} -> {url_dettaglio}")
            driver.get(url_dettaglio)
            
            # PARTE 1: TESTO KEY RESULTS
            try:
                elemento_contenitore = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#kereres")))
                testo_key_results = elemento_contenitore.text.strip()
                
                if testo_key_results:
                    nome_file_txt = f"{paese}_{periodo}_KeyResults.txt".replace("/", "-").replace(" ", "_")
                    path_completo_txt = os.path.join(TESTO_DIR, nome_file_txt)
                    
                    intestazione = f"COUNTRY: {paese}\nPERIOD: {periodo}\n" + "="*40 + "\n\n"
                    with open(path_completo_txt, "w", encoding="utf-8") as f:
                        f.write(intestazione + testo_key_results)
                    print(f"   -> [Testo] Salvato")
            except Exception:
                print("   -> [Testo] Non trovato")
            
            time.sleep(5)
            # PARTE 2: DOWNLOAD PDF
            links_download = driver.find_elements(By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download')]")
            
            for idx, link in enumerate(links_download):
                try:
                    link_text = link.text.strip().lower()
                    link_href = link.get_attribute("href") or ""
            
                    is_snapshot = "snapshot" in link_text or "snapshot" in link_href.lower()
                    target_dir = SNAPSHOT_DIR if is_snapshot else os.path.join(DOWNLOAD_DIR, f"{paese}_{periodo}".replace("/", "-").replace(" ", "_"))
            
                    os.makedirs(target_dir, exist_ok=True)
            
                    driver.execute_cdp_cmd("Browser.setDownloadBehavior", {
                        "behavior": "allow",
                        "downloadPath": os.path.abspath(target_dir)
                    })
           
                    actions = ActionChains(driver)
                    actions.move_to_element(link).click().perform()
                    print(f"   Cliccato link di download n. {idx + 1}")
                    time.sleep(3)  # Pausa di 3 secondi tra un click e l'altro per non intasare i download
                except Exception as e_click:
                    print(f"   Errore durante il click sul link n. {idx + 1}: {e_click}")
                    
        except Exception:
            print(f"Errore generale sulla pagina {url_dettaglio}")
finally:        
    driver.close()
    # Sblocca lo standby nel blocco finally per garantire il ripristino in ogni scenario
    ripristina_standby()
print("\n--- FASE 2 COMPLETATA ---")
