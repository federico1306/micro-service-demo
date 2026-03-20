import urllib.request  # Libreria standard Python per richieste HTTP (no dipendenze esterne)
import json            # Libreria per gestire dati in formato JSON
import os              # Libreria per operazioni sul sistema operativo (attualmente non utilizzata)
import sys             # Per leggere argomenti dalla riga di comando

# ========================================
# CONFIGURAZIONE PARAMETRI
# ========================================
# Lookback in ms: può essere passato come primo argomento (es. "python fetch_traces.py 330000")
# Default: 60000 ms = 1 minuto
LOOKBACK_MS = int(sys.argv[1]) if len(sys.argv) > 1 else 60000

ZIPKIN_URL = f"http://localhost:9411/api/v2/traces?limit=10000&lookback={LOOKBACK_MS}"
OUTPUT_FILE = "dataset_tesi.json"  # Nome del file dove salvare il dataset completo

# ========================================
# FUNZIONE PRINCIPALE DI DOWNLOAD
# ========================================
def scarica_tracce():
    """
    Scarica tutte le tracce dall'API di Zipkin dell'ultimo minuto.
    
    Workflow:
    1. Effettua richiesta HTTP GET a Zipkin
    2. Converte la risposta JSON in oggetti Python
    3. Verifica che ci siano tracce disponibili
    4. Salva i dati in un file JSON
    """
    print(f" Mi collego a Zipkin e chiedo TUTTE le tracce dell'ultimo minuto...")
    
    try:
        # ---- STEP 1: Preparazione e invio richiesta HTTP ----
        # ---- STEP 1: Preparazione e invio richiesta HTTP ----
        # Crea un oggetto Request con header che specifica che vogliamo JSON
        req = urllib.request.Request(ZIPKIN_URL, headers={'Accept': 'application/json'})
        
        # Apre la connessione HTTP e ottiene la risposta
        with urllib.request.urlopen(req) as response:
            # ---- STEP 2: Lettura e parsing della risposta ----
            # Legge i byte, li decodifica in stringa UTF-8, poi converte JSON in oggetti Python
            dati = json.loads(response.read().decode('utf-8'))
        
        # ---- STEP 3: Verifica quantità di tracce ricevute ----
        numero_tracce = len(dati)  # Conta il numero di tracce nella lista
        
        # Se non ci sono tracce, avvisa l'utente e termina
        if numero_tracce == 0:
            print("⚠️ Nessuna traccia trovata! Sicuro di aver fatto lo stress test nell'ultimo minuto?")
            return  # Esce dalla funzione senza salvare file
        
        # ---- STEP 4: Salvataggio dati su file ----
        # Apre il file in modalità scrittura con encoding UTF-8
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            # Scrive il JSON con indentazione di 4 spazi per leggibilità
            json.dump(dati, f, indent=4)
        
        # ---- STEP 5: Conferma operazione completata ----
        print(f" SCARICAMENTO COMPLETATO!")
        print(f" Salvate {numero_tracce} tracce in {OUTPUT_FILE}")
    
    except Exception as e:
        # ---- Gestione errori ----
        # Cattura qualsiasi eccezione (es. connessione fallita, timeout, errore di rete)
        print(f" Errore di connessione a Zipkin: {e}")
        print(" Assicurati che i container Docker siano accesi (docker-compose up)")

# ========================================
# PUNTO DI INGRESSO DEL PROGRAMMA
# ========================================
if __name__ == "__main__":
    # Questo blocco viene eseguito solo se lo script è lanciato direttamente
    # (non se importato come modulo)
    scarica_tracce()  # Avvia il processo di download