import urllib.request  # Libreria standard per richieste HTTP (legge il server web di LHM)
import json            # Libreria per parsare la risposta JSON di LibreHardwareMonitor
import time            # Libreria per gestire le pause tra campionamenti
import csv             # Libreria per scrivere i dati nel file CSV
from datetime import datetime  # Per aggiungere il timestamp a ogni riga del CSV

URL = "http://localhost:8085/data.json"              # Endpoint HTTP del server web di LibreHardwareMonitor
                                                     # Abilitabile da: Options -> Remote Web Server -> Run
OUTPUT_FILE = "LibreHardwareMonitorLog-Custom.csv"  # File CSV di output dove vengono salvati i campioni  # File CSV di output dove vengono salvati i campioni

def estrai_watt_da_json(nodo):
    """
    Naviga ricorsivamente l'albero JSON di LibreHardwareMonitor
    per trovare il valore di consumo del 'CPU Package' in Watt.
    
    La struttura JSON di LHM e' un albero annidato del tipo:
    {
      "Children": [
        { "Text": "PC", "Children": [
            { "Text": "Intel CPU", "Children": [
                { "Text": "CPU Package", "Value": "15,4 W" }
            ]}
        ]}
      ]
    }
    
    Args:
        nodo (dict): Nodo corrente dell'albero JSON da esaminare
    
    Returns:
        float: Consumo in Watt, oppure None se il nodo non e' quello cercato
    """
    # Controlla se il nodo corrente e' esattamente quello che cerchiamo:
    # - Text == "CPU Package" identifica il sensore di consumo totale del processore
    # - Value deve contenere "W" per confermare che l'unita' e' Watt
    if nodo.get("Text") == "CPU Package" and "W" in nodo.get("Value", ""):
        
        # Pulizia del testo: rimuove unita' e normalizza il separatore decimale
        # Es: "15,4 W" -> rimuove " W" -> "15,4" -> sostituisce "," con "." -> 15.4
        valore_testo = nodo.get("Value").replace(" W", "").replace(",", ".")
        try:
            return float(valore_testo)  # Converte la stringa in numero decimale
        except:
            return None  # Se la conversione fallisce, segnala nodo non valido
    
    # Ricorsione: se questo nodo non e' quello giusto, cerca nei suoi figli
    for figlio in nodo.get("Children", []):
        risultato = estrai_watt_da_json(figlio)
        if risultato is not None:
            return risultato  
    
    return None  # Nessun nodo valido trovato in questo ramo dell'albero

# ========================================
# FUNZIONE PRINCIPALE: LOOP DI CAMPIONAMENTO
# ========================================
def main():
    """
    Avvia il loop continuo di campionamento energetico.
    
    Ogni 250ms:
    1. Interroga l'API HTTP di LibreHardwareMonitor
    2. Estrae il valore Watt del CPU Package
    3. Scrive una riga nel CSV con timestamp + valore
    
    Il file CSV prodotto e' compatibile con energy_injector.py.
    Lo script si ferma con CTRL+C (o con processo_logger.terminate()
    quando lanciato da run_experiment.py).
    """
    print(" Connessione a Libre Hardware Monitor...")
    print(" REGISTRAZIONE AVVIATA!")
    
    # ---- Apertura file CSV in modalita' scrittura ----
    # Il file viene aperto UNA VOLTA sola e tenuto aperto per tutto il loop
    # Questo e' piu' efficiente che aprirlo e chiuderlo ad ogni campione
    with open(OUTPUT_FILE, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # ---- Scrittura intestazioni CSV ----
        # Due righe di header
        writer.writerow(["Time", "/intelcpu/0/power/0"])  # Riga 1: percorso sensore LHM
        writer.writerow(["Time", "CPU Package"])           # Riga 2: nome leggibile del sensore
        
        try:
            # ---- LOOP PRINCIPALE DI CAMPIONAMENTO ----
            while True:
                try:
                    # ---- STEP 1: Richiesta HTTP al server LHM ----
                    req = urllib.request.Request(URL)
                    with urllib.request.urlopen(req) as response:
                        # Decodifica la risposta bytes -> stringa -> dizionario Python
                        data = json.loads(response.read().decode('utf-8'))
                    
                    # ---- STEP 2: Estrazione valore Watt dall'albero JSON ----
                    watt = estrai_watt_da_json(data)
                    
                    # ---- STEP 3: Timestamp del campione (con millisecondi) ----
                    adesso = datetime.now()
                    now = adesso.strftime("%m/%d/%Y %H:%M:%S.") + adesso.strftime("%f")[:3]
                    
                    # ---- STEP 4: Scrittura riga CSV (solo se il valore e' valido) ----
                    if watt is not None:
                        writer.writerow([now, watt])  # Scrive [timestamp, watt]
                        f.flush()  # Forza scrittura su disco immediatamente
                        #print(f"[{now}] , CPU: {watt} W")
                        
                except Exception as e:

                    pass
                
                # ---- Pausa tra un campione e il successivo ----
                time.sleep(0.25)
                
        except KeyboardInterrupt:
            # Gestisce CTRL+C 
            print(f"\n Esperimento concluso con successo!")
            print(f" È stato generato un unico file: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()