import csv
import json
import os

CSV_FILE   = "LibreHardwareMonitorLog-Custom.csv"
JSON_FILE  = "dataset_tesi.json"
OUTPUT_FILE = "dataset_con_energia.json"

INTERVALLO_SECONDI = 0.25
SECONDS_IDLE = 10


def calcola_energia_netta_dal_csv(file_path):
    print(f" 1. Lettura dati Hardware ({file_path}) a {INTERVALLO_SECONDI}s...")

    valori_watt = []
    with open(file_path, mode='r', encoding='utf-8') as file:
        lettore_csv = csv.reader(file)
        next(lettore_csv)
        next(lettore_csv)
        for riga in lettore_csv:
            if not riga or len(riga) < 2:
                continue
            try:
                valori_watt.append(float(riga[1]))
            except ValueError:
                pass

    righe_totali = len(valori_watt)
    righe_idle   = int(SECONDS_IDLE / INTERVALLO_SECONDI)

    if righe_totali <= righe_idle:
        print(" Errore: Il test è troppo corto!")
        return 0.1

    fase_calma    = valori_watt[:righe_idle]
    tara_watt     = min(fase_calma)
    fase_stress   = valori_watt[righe_idle:]
    secondi_stress = len(fase_stress) * INTERVALLO_SECONDI

    energia_netta_joule  = 0.0
    energia_lorda_joule  = 0.0

    for watt_attuali in fase_stress:
        energia_lorda_joule += watt_attuali * INTERVALLO_SECONDI
        watt_netti = watt_attuali - tara_watt
        if watt_netti > 0:
            energia_netta_joule += watt_netti * INTERVALLO_SECONDI

    print("    CALIBRAZIONE DINAMICA COMPLETATA (Metodo Integrale):")
    print(f"   ├─ Tara MINIMA a riposo: {tara_watt:.2f} Watt")
    print(f"   ├─ Durata fase stress  : {secondi_stress:.2f} secondi")
    print(f"   ├─ Energia Lorda       : {energia_lorda_joule:.2f} J")
    print(f"   └─ ENERGIA NETTA       : {energia_netta_joule:.2f} J")

    return max(energia_netta_joule, 0.1)


def processa_tracce(json_path, energia_netta_joule):
    print(f"\n 2. Lettura Tracce Software ({json_path})...")

    with open(json_path, 'r', encoding='utf-8') as f:
        traces = json.load(f)

    cpu_totale_nanos      = 0
    numero_span_con_cpu   = 0

    for trace in traces:
        for span in trace:
            tags = span.get('tags', {})
            if 'cpu.nanos' in tags:
                cpu_totale_nanos += int(tags['cpu.nanos'])
                numero_span_con_cpu += 1

    print(f"   ├─ Trovati {numero_span_con_cpu} span con misurazione CPU pura.")

    if cpu_totale_nanos == 0:
        print("   Nessun tag 'cpu.nanos' trovato. Verifica la libreria cputracing.")
        return traces

    joule_per_nano = energia_netta_joule / cpu_totale_nanos
    print(f"   └─ Costo energetico CPU: {joule_per_nano:.12f} Joule/nanosecondo")

    print("\n 3. Iniezione Energia negli Span...")
    for trace in traces:
        for span in trace:
            tags = span.get('tags', {})
            if 'cpu.nanos' in tags:
                cpu_usata    = int(tags['cpu.nanos'])
                energia_span = cpu_usata * joule_per_nano
                span['tags']['energy.joules']             = f"{energia_span:.6f}"
                span['tags']['energy.attribution_model']  = "CPU-Proportional (cpu.nanos)"
            else:
                span['tags'].setdefault('energy.joules', "0.000000")

    return traces


def salva_risultato(traces, output_path):
    span_piatti = [span for trace in traces for span in trace]

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(span_piatti, f, indent=4)
    print(f"\n File COMPLETO salvato: {output_path}")

    output_light = output_path.replace(".json", "_LIGHT.json")
    with open(output_light, 'w', encoding='utf-8') as f:
        json.dump(span_piatti[:20], f, indent=4)
    print(f" File LEGGERO salvato : {output_light}")


if __name__ == "__main__":
    if not os.path.exists(CSV_FILE) or not os.path.exists(JSON_FILE):
        print(" ERRORE: Servono sia il CSV hardware che il JSON delle tracce!")
    else:
        energia_netta   = calcola_energia_netta_dal_csv(CSV_FILE)
        tracce_arricchite = processa_tracce(JSON_FILE, energia_netta)
        salva_risultato(tracce_arricchite, OUTPUT_FILE)
