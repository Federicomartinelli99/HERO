import ctypes
import time
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc

# Configurazione finestra visibile ma spostata
#WINDOW_SPOSTATA = True  

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
    return uc.Chrome(driver_executable_path=ChromeDriverManager(driver_version="149").install(), options=options)

print("--- INIZIO FASE 1: RACCOLTA URL ---")

# Blocca lo standby prima di far partire il browser
impedisci_standby()

driver = configura_driver()
base_url = "https://www.ipcinfo.org/ipc-country-analysis/en/"
try: 
    driver.get(base_url)

    wait = WebDriverWait(driver, 30)
    dropdown_country_elem = wait.until(EC.presence_of_element_located((By.ID, "id_country")))

    lista_anni = range(2011, 2027, 1)
    #lista_anni=[2017,2018]
    lista_url = []
    #lista_paesi = ['Afghanistan']
    dropdown_country = Select(dropdown_country_elem)
    lista_paesi = [opt.text for opt in dropdown_country.options[1:]]

    dropdown_type = Select(driver.find_element(By.ID, "id_maptype"))
    dropdown_type.select_by_index(1) 
    time.sleep(2)

    for country in lista_paesi:    
        for year in lista_anni:
            try:
                dropdown_country = Select(wait.until(EC.presence_of_element_located((By.ID, "id_country"))))
                dropdown_country.select_by_visible_text(country)
                print(f"Esplorazione: {country} - Anno: {year}")
                time.sleep(1)
                
                dropdown_year = Select(wait.until(EC.presence_of_element_located((By.ID, "id_timeframe_y"))))
                #dropdown_year = Select(driver.find_element(By.ID, "id_timeframe_y"))
                dropdown_year.select_by_visible_text(str(year))
                
                #bottone_confirm = driver.find_element(By.CSS_SELECTOR, "input[value='CONFIRM']")
                bottone_confirm = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[value='CONFIRM']")))
                bottone_confirm.click()
                time.sleep(4) 
                
                righe_risultato = driver.find_elements(By.CSS_SELECTOR, "div.dettaglio")
                for riga in righe_risultato:
                    try:
                        elemento_link = riga.find_element(By.CSS_SELECTOR, "div:nth-child(1) a")  
                        url_parziale = elemento_link.get_attribute("href")
                            
                        elemento_periodo = riga.find_element(By.CSS_SELECTOR, "div:nth-child(4) > p:nth-child(1)")
                        periodo = elemento_periodo.text.strip()
                            
                        # Salva le informazioni come dizionario (compatibile con JSON)
                        lista_url.append({"paese": country, "periodo": periodo, "url": url_parziale})
                        print(f"   -> Link trovato per {country} ({periodo})")
                    except Exception:
                        pass
            except Exception:
                print(f"Filtro non disponibile o errore per {country} ({year})")
finally:
    driver.close()
     # Sblocca lo standby nel blocco finally per garantire il ripristino in ogni scenario
    ripristina_standby()

# Salvataggio dei risultati su file JSON (rimuovendo i duplicati)
link_unici = {json.dumps(d, sort_keys=True) for d in lista_url}
lista_final = [json.loads(s) for s in link_unici]

with open("link_estratti.json", "w", encoding="utf-8") as f:
    json.dump(lista_final, f, indent=4, ensure_ascii=False)

# --- CONTEGGIO TEMPORANEO DI CONTROLLO ---
link_2017_2025 = 0
for voce in lista_final:
    # Controlla se nel testo del periodo c'è un anno tra il 2017 e il 2025
    if any(str(anno) in voce.get("periodo", "") for anno in range(2017, 2026)):
        link_2017_2025 += 1
print(f" -> Di cui nel periodo 2017-2025: {link_2017_2025} link")
# ----------------------------------------

print(f"\n--- FASE 1 COMPLETATA: Salvati {len(lista_final)} link in 'link_estratti.json' ---")
