#!/usr/bin/env python3
"""
TEST DI CARICO PROGRESSIVO - RICERCA DEL BREAKING POINT
Incrementa gli utenti fino a trovare il massimale del sistema
"""
import subprocess
import time
import sys
import os
import json
from datetime import datetime
from pathlib import Path

# ================================================================
# CONFIGURAZIONE
# ================================================================

JMETER_BIN = r"C:\apache-jmeter-5.6.3\bin\jmeter.bat"
FILE_JMX   = r"C:\Users\berar\Documents\micro-service-demo\stress_test_auto.jmx"

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "test_breaking_point"

# Parametri ricerca breaking point
UTENTI_START      = 100       # Inizia da 50 (già sai che 40 funziona)
UTENTI_STEP       = 10        # Incremento di 10 utenti per volta
UTENTI_MAX        = 300       # Massimo da testare
N_TEST_PER_BLOCCO = 1         # Solo 3 test per essere veloce (invece di 10)
DURATA_TEST_S     = 180       # 3 minuti per test (invece di 5)
PAUSA_TRA_TEST_S  = 10        # Pausa breve tra test

# Soglie per determinare il breaking point
SOGLIA_ERRORI_WARNING = 50      # % errori: inizia a essere preoccupante
SOGLIA_ERRORI_CRITICO = 80      # % errori: critico, il sistema sta fallendo
SOGLIA_ERRORI_TOTALE = 95       # % errori: sistema in crash totale

# ================================================================
# UTILITA'
# ================================================================

def conto_alla_rovescia(secondi, messaggio):
    """Attende mostrando il conto alla rovescia."""
    print(f"\n  {messaggio}")
    for i in range(secondi, 0, -1):
        print(f"\r  Ripresa tra {i:3d} s...", end="", flush=True)
        time.sleep(1)
    print(f"\r  Attesa completata!              ")

def leggi_risultati_jmeter(csv_path):
    """Legge il CSV di JMeter e estrae metriche key."""
    if not Path(csv_path).exists():
        return None

    import csv
    richieste = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            richieste.append({
                'elapsed': float(row['elapsed']),
                'latency': float(row['Latency']),
                'success': row['success'].lower() == 'true',
                'responseCode': row['responseCode'],
                'failureMessage': row.get('failureMessage', '')
            })

    if not richieste:
        return None

    elapsed_sorted = sorted([r['elapsed'] for r in richieste])

    def percentile(data, p):
        n = len(data)
        idx = int(n * p / 100)
        return data[min(idx, n-1)]

    totale = len(richieste)
    successi = sum(1 for r in richieste if r['success'])
    fallimenti = totale - successi
    tasso_errori = (fallimenti / totale * 100) if totale > 0 else 0

    # Conta response code diversi da 200
    resp_codes = set(r['responseCode'] for r in richieste)
    richieste_non_200 = [r for r in richieste if r['responseCode'] != '200']

    return {
        'totale_richieste': totale,
        'successi': successi,
        'fallimenti': fallimenti,
        'tasso_errori': tasso_errori,
        'tempo_medio_ms': sum(r['elapsed'] for r in richieste) / totale,
        'tempo_min_ms': min(elapsed_sorted),
        'tempo_max_ms': max(elapsed_sorted),
        'p95_ms': percentile(elapsed_sorted, 95),
        'p99_ms': percentile(elapsed_sorted, 99),
        'response_codes': list(resp_codes),
        'richieste_non_200': len(richieste_non_200),
    }

def controlla_zipkin():
    """Verifica se Zipkin è ancora vivo."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", "zipkin"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() == "true"
    except:
        return False

def esegui_test_blocco(n_utenti, durata_s, output_dir):
    """Esegue N test per un blocco di utenti."""
    os.makedirs(output_dir, exist_ok=True)

    risultati_blocco = []

    for idx_test in range(1, N_TEST_PER_BLOCCO + 1):
        test_output_dir = Path(output_dir) / f"test_{idx_test:02d}"
        os.makedirs(test_output_dir, exist_ok=True)

        risultati_jmeter = test_output_dir / "risultati_jmeter.csv"

        print(f"\n    Test {idx_test}/{N_TEST_PER_BLOCCO} ({n_utenti} utenti)...")

        # Reset Zipkin
        print(f"      [1/3] Reset Zipkin...")
        subprocess.run(
            ["docker", "restart", "zipkin"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(5)

        # Verifica Zipkin
        if not controlla_zipkin():
            print(f"      [!] ERRORE: Zipkin non è vivo dopo restart!")
            return None

        # JMeter
        print(f"      [2/3] JMeter in esecuzione...")
        if risultati_jmeter.exists():
            os.remove(risultati_jmeter)

        comando_jmeter = [
            JMETER_BIN, "-n",
            "-t", FILE_JMX,
            "-l", str(risultati_jmeter),
            f"-Jutenti={n_utenti}",
            f"-Jdurata={durata_s}",
        ]

        inizio = datetime.now()
        try:
            subprocess.run(comando_jmeter, check=True,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            durata = (datetime.now() - inizio).total_seconds()
        except subprocess.CalledProcessError as e:
            print(f"      [!] JMeter fallito (exit code {e.returncode})")
            return None

        # Verifica Zipkin dopo test
        print(f"      [3/3] Verifica Zipkin dopo test...")
        time.sleep(2)
        zipkin_vivo = controlla_zipkin()

        if not zipkin_vivo:
            print(f"      [!] ZIPKIN CRASHATO durante il test!")
            docker_status = subprocess.run(
                ["docker", "ps", "-a", "--filter", "name=zipkin", "--format", "{{.Status}}"],
                capture_output=True, text=True
            )
            print(f"      Status: {docker_status.stdout.strip()}")

        # Leggi risultati
        metriche = leggi_risultati_jmeter(str(risultati_jmeter))
        if metriche:
            metriche['zipkin_alive'] = zipkin_vivo
            metriche['durata_test_s'] = durata
            risultati_blocco.append(metriche)

            print(f"      OK: {metriche['totale_richieste']} richieste, "
                  f"{metriche['tasso_errori']:.1f}% errori, "
                  f"P95={metriche['p95_ms']:.0f}ms, "
                  f"Zipkin={'OK' if zipkin_vivo else 'CRASH!'}")
        else:
            print(f"      [!] Nessun risultato JMeter")
            return None

        # Se Zipkin è crashato, ferma il blocco
        if not zipkin_vivo:
            print(f"\n    BLOCCO INTERROTTO: Zipkin crashato a {n_utenti} utenti")
            return resultado_blocco

        # Pausa tra test
        if idx_test < N_TEST_PER_BLOCCO:
            conto_alla_rovescia(PAUSA_TRA_TEST_S, "Pausa tra test...")

    return risultati_blocco if risultati_blocco else None

# ================================================================
# MAIN
# ================================================================

def main():
    print("=" * 70)
    print("  RICERCA BREAKING POINT — MICROSERVICE DEMO")
    print("  Incremento progressivo degli utenti fino a crash")
    print("=" * 70)

    OUTPUT_DIR.mkdir(exist_ok=True)

    # File log dei risultati
    log_file = OUTPUT_DIR / "breaking_point_log.json"
    risultati_totali = []

    utenti_corrente = UTENTI_START
    breaking_point_trovato = False

    while utenti_corrente <= UTENTI_MAX and not breaking_point_trovato:

        print(f"\n{'#' * 70}")
        print(f"  BLOCCO: {utenti_corrente} UTENTI ({N_TEST_PER_BLOCCO} test x {DURATA_TEST_S}s)")
        print(f"{'#' * 70}")

        output_blocco = OUTPUT_DIR / f"blocco_{utenti_corrente}utenti"

        # Esegui test
        risultati = esegui_test_blocco(utenti_corrente, DURATA_TEST_S, str(output_blocco))

        if risultati is None:
            print(f"\n[!] BREAKING POINT TROVATO A {utenti_corrente} UTENTI!")
            print(f"    Il sistema non riesce a gestire {utenti_corrente} utenti.")
            breaking_point_trovato = True
            break

        # Analizza risultati
        medie_blocco = {
            'utenti': utenti_corrente,
            'n_test': len(risultati),
            'tasso_errori_avg': sum(r['tasso_errori'] for r in risultati) / len(risultati),
            'tempo_medio_avg': sum(r['tempo_medio_ms'] for r in risultati) / len(risultati),
            'p95_avg': sum(r['p95_ms'] for r in risultati) / len(risultati),
            'p99_avg': sum(r['p99_ms'] for r in risultati) / len(risultati),
            'zipkin_crashes': sum(1 for r in risultati if not r['zipkin_alive']),
            'timestamp': datetime.now().isoformat()
        }

        risultati_totali.append(medie_blocco)

        # Stampa risultati
        print(f"\n  RISULTATI BLOCCO {utenti_corrente} UTENTI:")
        print(f"    Tasso errori medio : {medie_blocco['tasso_errori_avg']:.2f}%")
        print(f"    Tempo medio        : {medie_blocco['tempo_medio_avg']:.2f} ms")
        print(f"    P95                : {medie_blocco['p95_avg']:.2f} ms")
        print(f"    P99                : {medie_blocco['p99_avg']:.2f} ms")
        print(f"    Zipkin crash       : {medie_blocco['zipkin_crashes']}/{medie_blocco['n_test']}")

        # Salva risultati progressivamente
        with open(log_file, 'w') as f:
            json.dump(risultati_totali, f, indent=2)

        # Controlli per determinare se continuare
        if medie_blocco['zipkin_crashes'] > 0:
            print(f"\n[!] Attenzione: Zipkin ha crashato {medie_blocco['zipkin_crashes']} volte (continuo comunque)")

        # BREAKING POINT: errori HTTP al 95%+
        if medie_blocco['tasso_errori_avg'] >= SOGLIA_ERRORI_TOTALE:
            print(f"\n[!!!] BREAKING POINT: Errori >= {SOGLIA_ERRORI_TOTALE}%! SISTEMA IN CRASH TOTALE")
            print(f"      Percentuale errori: {medie_blocco['tasso_errori_avg']:.2f}%")
            breaking_point_trovato = True
            break

        if medie_blocco['tasso_errori_avg'] >= SOGLIA_ERRORI_CRITICO:
            print(f"\n[!!] ATTENZIONE: Errori >= {SOGLIA_ERRORI_CRITICO}%! Sistema critico")
            print(f"     Percentuale errori: {medie_blocco['tasso_errori_avg']:.2f}%")
            print(f"     Potrebbe essere il breaking point...")

        if medie_blocco['tasso_errori_avg'] >= SOGLIA_ERRORI_WARNING:
            print(f"\n[!] Degradazione: Errori >= {SOGLIA_ERRORI_WARNING}%")
            print(f"    Percentuale errori: {medie_blocco['tasso_errori_avg']:.2f}%")

        # BREAKING POINT ALTERNATIVO: P95 troppo alto (>5 sec = sistema saturo)
        # Questo succede quando il sistema non rifiuta ma è MOLTO lento
        if medie_blocco['p95_avg'] > 5000:
            print(f"\n[!!!] BREAKING POINT (LATENZA): P95={medie_blocco['p95_avg']:.0f}ms > 5000ms")
            print(f"      Sistema saturo, latenza inaccettabile")
            print(f"      Anche se errori sono bassi, il sistema non regge {utenti_corrente} utenti")
            breaking_point_trovato = True
            break

        if medie_blocco['p95_avg'] > 1000:
            print(f"\n[!] ATTENZIONE LATENZA: P95={medie_blocco['p95_avg']:.0f}ms > 1000ms")
            print(f"    Sistema inizia a saturare")

        # Incrementa utenti
        utenti_precedente = utenti_corrente
        utenti_corrente += UTENTI_STEP

        if utenti_corrente <= UTENTI_MAX and not breaking_point_trovato:
            conto_alla_rovescia(60, f"Pausa tra blocchi (raffreddamento sistema)...")

    # ================================================================
    # REPORT FINALE
    # ================================================================
    print(f"\n\n{'=' * 70}")
    print("  RICERCA BREAKING POINT COMPLETATA")
    print(f"{'=' * 70}")

    if risultati_totali:
        print(f"\nBlocchi testati: {len(risultati_totali)}")
        print(f"\nRISULTATI:")
        print(f"\n{'Utenti':<10} {'Errori %':<12} {'Tempo μ':<12} {'P95':<12} {'Zipkin':<10}")
        print(f"{'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*10}")

        for r in risultati_totali:
            print(f"{r['utenti']:<10} {r['tasso_errori_avg']:>10.2f}% {r['tempo_medio_avg']:>10.2f}ms {r['p95_avg']:>10.2f}ms {r['zipkin_crashes']:>10}")

        massimale = risultati_totali[-1]['utenti']
        print(f"\n{'=' * 70}")
        print(f"MASSIMALE STABILE: {massimale} utenti (senza crash)")
        print(f"BREAKING POINT RILEVATO: > {massimale} utenti")
        print(f"  (Errori al {risultati_totali[-1]['tasso_errori_avg']:.2f}%, P95={risultati_totali[-1]['p95_avg']:.0f}ms)")
        print(f"{'=' * 70}")

        # Salva report finale
        report_file = OUTPUT_DIR / "breaking_point_report.txt"
        with open(report_file, 'w') as f:
            f.write(f"RICERCA BREAKING POINT - MICROSERVICE DEMO\n")
            f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'=' * 70}\n\n")
            f.write(f"RISULTATO: Massimale stabile a {massimale} utenti\n")
            f.write(f"Errori al massimale: {risultati_totali[-1]['tasso_errori_avg']:.2f}%\n")
            f.write(f"Latenza P95 al massimale: {risultati_totali[-1]['p95_avg']:.0f}ms\n")
            f.write(f"Latenza P99 al massimale: {risultati_totali[-1]['p99_avg']:.0f}ms\n")
            f.write(f"Numero blocchi testati: {len(risultati_totali)}\n\n")
            f.write(f"Soglie utilizzate:\n")
            f.write(f"  - WARNING ERRORI (>= {SOGLIA_ERRORI_WARNING}%): Sistema inizia a degradarsi\n")
            f.write(f"  - CRITICO ERRORI (>= {SOGLIA_ERRORI_CRITICO}%): Sistema satura (errori)\n")
            f.write(f"  - CRASH ERRORI (>= {SOGLIA_ERRORI_TOTALE}%): Interruzione test\n")
            f.write(f"  - CRASH LATENZA (P95 > 5000ms): Interruzione test (system saturation)\n\n")
            f.write(f"Dettagli blocchi:\n")
            f.write(f"{'Utenti':<10} {'Errori %':<12} {'Tempo μ':<12} {'P95':<12} {'P99':<12}\n")
            f.write(f"{'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*12}\n")
            for r in risultati_totali:
                f.write(f"{r['utenti']:<10} {r['tasso_errori_avg']:>10.2f}% {r['tempo_medio_avg']:>10.2f}ms {r['p95_avg']:>10.0f}ms {r['p99_avg']:>10.0f}ms\n")

        print(f"\nReport salvato: {report_file}")
        print(f"Dati JSON: {log_file}")
    else:
        print("[!] Nessun risultato valido.")

if __name__ == "__main__":
    main()
