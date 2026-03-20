import subprocess
import time
import sys
import os
from datetime import datetime

# ================================================================
# CONFIGURAZIONE CAMPAGNA DI PROVA (1 test per blocco)
# ================================================================

BLOCCHI_UTENTI      = [10, 25, 50]   # N. thread JMeter per ogni blocco
N_TEST_PER_BLOCCO   = 1              # Un solo test per blocco (modalità prova)
DURATA_TEST_SECONDI = 300            # Durata di ogni test (5 minuti)
PAUSA_TRA_BLOCCHI_S = 10            # Pausa tra un blocco e il successivo (5 min)

JMETER_BIN = r"C:\apache-jmeter-5.6.3\bin\jmeter.bat"
FILE_JMX   = (
    r"C:\Users\berar\Documents\micro-service-demo"
    r"\stress_test_auto.jmx"
)

# Script Python nella cartella padre (micro-service-demo/)
SCRIPT_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Output nella cartella corrente (prova/)
PROVA_DIR   = os.path.dirname(os.path.abspath(__file__))


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
    os.makedirs(output_dir, exist_ok=True)
    lookback_ms      = (durata_s + 30) * 1000
    risultati_jmeter = os.path.join(output_dir, "risultati_jmeter.csv")

    # ---- 1. Logger hardware ----
    print(f"    [1/5] Avvio Logger Hardware...")
    logger_process = subprocess.Popen(
        [sys.executable, os.path.join(SCRIPT_DIR, "mio_logger.py")],
        cwd=output_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print("    Calibrazione 10s a riposo...")
    time.sleep(10)

    # ---- 2. JMeter ----
    print(f"    [2/5] JMeter: {n_utenti} utenti × {durata_s}s...")
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
    print("    [3/5] Fermo Logger Hardware...")
    logger_process.terminate()
    logger_process.wait()

    # ---- 4. Fetch tracce Zipkin ----
    print(f"    [4/5] Scarico tracce Zipkin (lookback={lookback_ms}ms)...")
    time.sleep(2)
    subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "fetch_traces.py"), str(lookback_ms)],
        cwd=output_dir,
    )

    # ---- 5. Calcola energia ----
    print("    [5/5] Calcolo energia (CPU Nanos)...")
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
    print("  CAMPAGNA DI PROVA — MICRO-SERVICE-DEMO")
    print(f"  Avvio: {inizio_globale.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)
    print(f"  Blocchi utenti   : {BLOCCHI_UTENTI}")
    print(f"  Test per blocco  : {N_TEST_PER_BLOCCO} (modalità prova)")
    print(f"  Durata test      : {DURATA_TEST_SECONDI}s ({DURATA_TEST_SECONDI // 60} min)")
    print(f"  Pausa tra blocchi: {PAUSA_TRA_BLOCCHI_S}s ({PAUSA_TRA_BLOCCHI_S // 60} min)")
    print(f"  Totale test      : {n_totale_test}")
    print(f"  Output           : prova/risultati/blocco_X_Yutenti/test_01/")
    print("=" * 65)

    risultati = []

    for idx_blocco, n_utenti in enumerate(BLOCCHI_UTENTI, start=1):
        print(f"\n{'#' * 65}")
        print(f"  BLOCCO {idx_blocco}/{n_blocchi} — {n_utenti} UTENTI")
        print(f"{'#' * 65}")

        nome_blocco = f"blocco_{idx_blocco}_{n_utenti}utenti"
        output_dir  = os.path.join(PROVA_DIR, "risultati", nome_blocco, "test_01")

        print(f"\n  --- TEST UNICO (Blocco {idx_blocco}/{n_blocchi}, {n_utenti} utenti) ---")
        print(f"  Output: {output_dir}")

        inizio_test  = datetime.now()
        ok           = esegui_singolo_test(n_utenti, DURATA_TEST_SECONDI, output_dir)
        durata_reale = (datetime.now() - inizio_test).total_seconds()

        stato = "OK" if ok else "ERRORE"
        risultati.append({
            "blocco": idx_blocco, "utenti": n_utenti, "stato": stato,
        })
        print(f"  Test completato in {durata_reale:.0f}s — {stato}")

        # Pausa tra blocchi (non dopo l'ultimo)
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
    print("  PROVA COMPLETATA!")
    print(f"  Durata totale: {durata_totale}")
    print(f"\n  RIEPILOGO:")
    print(f"  Successi : {test_ok}/{len(risultati)}")
    if test_err > 0:
        print(f"  Errori   : {test_err}/{len(risultati)}")
        for r in risultati:
            if r["stato"] == "ERRORE":
                print(f"    - Blocco {r['blocco']} ({r['utenti']} utenti)")
    print(f"\n  Risultati in: {os.path.join(PROVA_DIR, 'risultati')}/")
    print("=" * 65)


if __name__ == "__main__":
    main()
