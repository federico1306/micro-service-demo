import subprocess
import time
import sys
import os
from datetime import datetime

# ================================================================
# CONFIGURAZIONE CAMPAGNA DI TEST
# ================================================================

BLOCCHI_UTENTI       = [50,62,75,87,100]   # N. thread JMeter per ogni blocco
N_TEST_PER_BLOCCO    = 10             # Quante ripetizioni per blocco
DURATA_TEST_SECONDI  = 300            # Durata di ogni test (5 minuti)
PAUSA_TRA_TEST_S     = 60             # Pausa tra un test e il successivo (1 min)
PAUSA_TRA_BLOCCHI_S  = 300            # Pausa tra un blocco e il successivo (5 min)

JMETER_BIN = r"C:\apache-jmeter-5.6.3\bin\jmeter.bat"
FILE_JMX   = r"C:\Users\berar\Documents\micro-service-demo\stress_test_realistic.jmx"

# Cartella dove si trovano gli script Python (questa stessa cartella)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ================================================================
# UTILITÀ
# ================================================================

def conto_alla_rovescia(secondi, messaggio):
    """Attende 'secondi' mostrando il conto alla rovescia ogni secondo."""
    print(f"\n  {messaggio}")
    for i in range(secondi, 0, -1):
        print(f"\r  Ripresa tra {i:3d} s...", end="", flush=True)
        time.sleep(1)
    print(f"\r  Attesa completata!              ")


# ================================================================
# SINGOLO TEST
# ================================================================

def esegui_singolo_test(n_utenti, durata_s, output_dir):
    """
    Esegue un singolo ciclo completo:
      0. Restart Zipkin (svuota memoria in-memory)
      1. Avvia il logger hardware (mio_logger.py) in background
      2. Calibrazione a riposo (10s)
      3. Lancia JMeter con i parametri corretti
      4. Ferma il logger
      5. Scarica le tracce da Zipkin (fetch_traces.py)
      6. Calcola e inietta l'energia (energy_injector.py)

    Tutti i file di output vengono scritti in 'output_dir'.
    Restituisce True se tutto è andato bene, False in caso di errore critico.
    """
    os.makedirs(output_dir, exist_ok=True)
    lookback_ms      = (durata_s + 30) * 1000   # finestra Zipkin con 30s di margine
    risultati_jmeter = os.path.join(output_dir, "risultati_jmeter.csv")

    # ---- 0. Reset Zipkin ----
    print(f"    [0/6] Reset Zipkin (docker restart)...")
    subprocess.run(
        ["docker", "restart", "zipkin"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(5)   # attendi che Zipkin sia nuovamente operativo

    # ---- 1. Logger hardware ----
    print(f"    [1/6] Avvio Logger Hardware...")
    logger_process = subprocess.Popen(
        [sys.executable, os.path.join(SCRIPT_DIR, "mio_logger.py")],
        cwd=output_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print("    Calibrazione 10s a riposo...")
    time.sleep(10)

    # ---- 2. JMeter ----
    print(f"    [2/6] JMeter: {n_utenti} utenti × {durata_s}s...")
    if os.path.exists(risultati_jmeter):
        os.remove(risultati_jmeter)

    comando_jmeter = [
        JMETER_BIN, "-n",
        "-t", FILE_JMX,
        "-l", risultati_jmeter,
        f"-Jutenti={n_utenti}",
        f"-Jdurata={durata_s}",
    ]

    try:
        subprocess.run(
            comando_jmeter, check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        print(f"\n    [!] ERRORE: JMeter non trovato: {JMETER_BIN}")
        logger_process.terminate()
        return False
    except subprocess.CalledProcessError as e:
        print(f"\n    [!] ERRORE JMeter (exit code {e.returncode})")
        logger_process.terminate()
        return False

    # ---- 3. Ferma il logger ----
    print("    [3/6] Fermo Logger Hardware...")
    logger_process.terminate()
    logger_process.wait()

    # ---- 4. Fetch tracce Zipkin ----
    print(f"    [4/6] Scarico tracce Zipkin (lookback={lookback_ms}ms)...")
    time.sleep(2)   # piccola attesa per garantire che Zipkin abbia processato le ultime tracce
    subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "fetch_traces.py"), str(lookback_ms)],
        cwd=output_dir,
    )

    # ---- 5. Calcola energia ----
    print("    [5/6] Calcolo energia (CPU Nanos)...")
    subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "energy_injector.py")],
        cwd=output_dir,
    )

    return True


# ================================================================
# ORCHESTRATORE PRINCIPALE
# ================================================================

def main():
    inizio_globale = datetime.now()
    n_blocchi      = len(BLOCCHI_UTENTI)
    n_totale_test  = n_blocchi * N_TEST_PER_BLOCCO

    print("=" * 65)
    print("  CAMPAGNA DI TEST AUTOMATIZZATA — MICRO-SERVICE-DEMO")
    print(f"  Avvio: {inizio_globale.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)
    print(f"  Blocchi utenti   : {BLOCCHI_UTENTI}")
    print(f"  Test per blocco  : {N_TEST_PER_BLOCCO}")
    print(f"  Durata test      : {DURATA_TEST_SECONDI}s ({DURATA_TEST_SECONDI // 60} min)")
    print(f"  Pausa tra test   : {PAUSA_TRA_TEST_S}s")
    print(f"  Pausa tra blocchi: {PAUSA_TRA_BLOCCHI_S}s ({PAUSA_TRA_BLOCCHI_S // 60} min)")
    print(f"  Totale test      : {n_totale_test}")
    print(f"  Output           : risultati/blocco_X_Yutenti/test_ZZ/")
    print("=" * 65)

    risultati = []

    for idx_blocco, n_utenti in enumerate(BLOCCHI_UTENTI, start=1):
        print(f"\n{'#' * 65}")
        print(f"  BLOCCO {idx_blocco}/{n_blocchi} — {n_utenti} UTENTI")
        print(f"{'#' * 65}")

        nome_blocco = f"blocco_{idx_blocco}_{n_utenti}utenti"

        for idx_test in range(1, N_TEST_PER_BLOCCO + 1):
            output_dir = os.path.join(
                SCRIPT_DIR, "risultati", nome_blocco, f"test_{idx_test:02d}"
            )

            print(f"\n  --- TEST {idx_test}/{N_TEST_PER_BLOCCO} "
                  f"(Blocco {idx_blocco}/{n_blocchi}, {n_utenti} utenti) ---")
            print(f"  Output: {output_dir}")

            inizio_test = datetime.now()
            ok = esegui_singolo_test(n_utenti, DURATA_TEST_SECONDI, output_dir)
            durata_reale = (datetime.now() - inizio_test).total_seconds()

            stato = "OK" if ok else "ERRORE"
            risultati.append({
                "blocco": idx_blocco, "utenti": n_utenti,
                "test": idx_test, "stato": stato,
            })
            print(f"  Test completato in {durata_reale:.0f}s — {stato}")

            # Pausa tra test (non dopo l'ultimo del blocco)
            if idx_test < N_TEST_PER_BLOCCO:
                conto_alla_rovescia(
                    PAUSA_TRA_TEST_S,
                    f"Pausa tra test ({PAUSA_TRA_TEST_S}s)...",
                )

        # Pausa tra blocchi (non dopo l'ultimo blocco)
        if idx_blocco < n_blocchi:
            conto_alla_rovescia(
                PAUSA_TRA_BLOCCHI_S,
                f"Pausa tra blocchi ({PAUSA_TRA_BLOCCHI_S // 60} min) — sistema in raffreddamento...",
            )

    # ----------------------------------------------------------------
    # Report finale
    # ----------------------------------------------------------------
    durata_totale = datetime.now() - inizio_globale
    test_ok  = sum(1 for r in risultati if r["stato"] == "OK")
    test_err = sum(1 for r in risultati if r["stato"] == "ERRORE")

    print(f"\n{'=' * 65}")
    print("  CAMPAGNA COMPLETATA!")
    print(f"  Durata totale: {durata_totale}")
    print(f"\n  RIEPILOGO:")
    print(f"  Successi : {test_ok}/{len(risultati)}")
    if test_err > 0:
        print(f"  Errori   : {test_err}/{len(risultati)}")
        for r in risultati:
            if r["stato"] == "ERRORE":
                print(f"    - Blocco {r['blocco']} ({r['utenti']} utenti), test {r['test']:02d}")
    print(f"\n  Risultati in: {os.path.join(SCRIPT_DIR, 'risultati')}/")
    print("=" * 65)


if __name__ == "__main__":
    main()
