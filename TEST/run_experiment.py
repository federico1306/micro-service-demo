import subprocess
import time
import sys
import os

def esegui_esperimento():
    print("="*60)
    print(" AVVIO ESPERIMENTO AUTOMATIZZATO MICRO-SERVICE-DEMO")
    print("="*60)

    # ---------------------------------------------------------
    # CONFIGURAZIONE JMETER
    # ---------------------------------------------------------
    JMETER_BIN = r"C:\apache-jmeter-5.6.3\bin\jmeter.bat"

    FILE_JMX = r"C:\Users\berar\Documents\micro-service-demo\stress_test_auto.jmx"
    FILE_RISULTATI = "risultati_jmeter.csv"

    # Parametri test (configurabili)
    N_UTENTI = 10      # Numero utenti concorrenti
    DURATA_S = 60      # Durata test in secondi

    # 1. Avvia il logger hardware in background
    print("\n[1/6] Avvio LibreHardwareMonitor Logger in background...")
    logger_process = subprocess.Popen([sys.executable, "mio_logger.py"])

    # Aspettiamo 10 secondi per calcolare la "Tara" a riposo
    print("Attesa di 10 secondi per calibrazione della Tara a riposo...")
    time.sleep(10)

    # 2. Avvia lo stress test con JMeter
    print(f"\n[2/6] Avvio Apache JMeter ({N_UTENTI} utenti, {DURATA_S}s)...")

    # Elimina vecchi file di risultati di JMeter per evitare errori
    if os.path.exists(FILE_RISULTATI):
        os.remove(FILE_RISULTATI)

    comando_jmeter = [
        JMETER_BIN,
        "-n",
        "-t", FILE_JMX,
        "-l", FILE_RISULTATI,
        f"-Jutenti={N_UTENTI}",
        f"-Jdurata={DURATA_S}",
    ]

    # Questo comando blocca lo script finché JMeter non finisce
    try:
        subprocess.run(comando_jmeter, check=True)
    except FileNotFoundError:
        print(f"\n[!] ERRORE: Non trovo JMeter nel percorso specificato: {JMETER_BIN}")
        print("    Per favore, apri lo script e correggi la variabile JMETER_BIN.")
        logger_process.terminate()
        return

    # 3. Ferma il logger hardware
    print("\n[3/6] Stress test completato. Fermo il Logger Hardware...")
    logger_process.terminate()
    logger_process.wait() # Assicura che il CSV sia salvato e chiuso correttamente

    # 4. Scarica i dati da Zipkin
    print("\n[4/6] Estrazione tracce grezze da Zipkin...")
    # Aspettiamo 2 secondi per dare a Zipkin il tempo di processare le ultimissime tracce
    time.sleep(2)
    lookback_ms = (DURATA_S + 30) * 1000  # Lookback con margine di 30s
    subprocess.run([sys.executable, "fetch_traces.py", str(lookback_ms)])

    # 5. Calcola l'energia e la inietta nel JSON
    print("\n[5/6] Calcolo fisico e iniezione dell'energia (CPU Nanos)...")
    subprocess.run([sys.executable, "energy_injector.py"])

    # 6. Report finale
    print("\n" + "="*60)
    print(" ESPERIMENTO CONCLUSO CON SUCCESSO!")
    print(" L'energia è stata misurata, calcolata e fusa nel sistema.")
    print(" Puoi visualizzare i risultati andando su: http://localhost:9411")
    print("="*60)

if __name__ == "__main__":
    esegui_esperimento()
