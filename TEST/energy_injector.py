
import csv   # Libreria per leggere file CSV (il log di LibreHardwareMonitor)
import json  # Libreria per leggere/scrivere file JSON (le tracce di Zipkin)
import os    # Libreria per operazioni sul filesystem (es. verificare se un file esiste)


CSV_FILE = "LibreHardwareMonitorLog-Custom.csv" # File di log energetico dell'hardware (1 campione/secondo)
JSON_FILE = "dataset_tesi.json"                 # File delle tracce Zipkin scaricato in precedenza
OUTPUT_FILE = "dataset_con_energia.json"        # File di output con energia iniettata negli span

INTERVALLO_SECONDI = 0.25  # Risoluzione del campionamento a 250ms (4 campioni al secondo)
SECONDS_IDLE = 10          # Secondi di calma iniziali per il calcolo della tara


def calcola_energia_netta_dal_csv(file_path):
    """Legge il log energetico, rimuove la tara e integra la potenza in Joule."""

    print(f" 1. Lettura dati Hardware ({file_path}) a {INTERVALLO_SECONDI}s...")

    valori_watt = []

    # ---- STEP 1: Lettura del file ----
    with open(file_path, mode='r', encoding='utf-8') as file:
        lettore_csv = csv.reader(file)
        next(lettore_csv)  
        next(lettore_csv)  

        for riga in lettore_csv:
            if not riga or len(riga) < 2: continue
            try:
                valori_watt.append(float(riga[1]))
            except ValueError:
                pass 

    righe_totali = len(valori_watt)
    righe_idle = int(SECONDS_IDLE / INTERVALLO_SECONDI)

    if righe_totali <= righe_idle:
        print(" Errore: Il test è troppo corto!")
        return 0.1 

    # ---- STEP 2: Calcolo TARA (Il minimo assoluto, non la media!) ----
    fase_calma = valori_watt[:righe_idle]
    # Usiamo il valore MINIMO registrato a riposo come vera baseline del PC
    tara_watt = min(fase_calma) 

    # ---- STEP 3: Calcolo ENERGIA NETTA (Integrazione riga per riga) ----
    # Escludiamo la fase di calma iniziale e teniamo solo il periodo di lavoro
    fase_stress = valori_watt[righe_idle:]
    # Durata effettiva del test sotto carico
    secondi_stress = len(fase_stress) * INTERVALLO_SECONDI
    
    energia_netta_joule = 0.0
    energia_lorda_joule = 0.0
    
    # Analizziamo ogni singolo istante (riga per riga)
    for watt_attuali in fase_stress:
        # L'energia lorda è sempre P * t
        energia_lorda_joule += (watt_attuali * INTERVALLO_SECONDI)
        
        # Sottraiamo la tara istantanea
        watt_netti = watt_attuali - tara_watt
        
        # Se i watt_netti sono positivi (siamo in un picco di sforzo), aggiungiamo i Joule
        if watt_netti > 0:
            energia_netta_joule += (watt_netti * INTERVALLO_SECONDI)

    # ---- Stampa report di calibrazione ----
    print("    CALIBRAZIONE DINAMICA COMPLETATA (Metodo Integrale):")
    print(f"   ├─ Campionamento: {INTERVALLO_SECONDI}s")
    print(f"   ├─ Tara MINIMA a riposo: {tara_watt:.2f} Watt")
    print(f"   ├─ Durata fase registrazione: {secondi_stress:.2f} secondi")
    print(f"   ├─ Energia Lorda Totale: {energia_lorda_joule:.2f} J")
    print(f"   └─ ENERGIA NETTA: {energia_netta_joule:.2f} J")

    # Protezione finale
    if energia_netta_joule < 0.1: 
        return 0.1
        
    return energia_netta_joule
# ========================================
# FUNZIONE 2: INIEZIONE ENERGIA NELLE TRACCE (AGGIORNATA PER CPU.NANOS)
# ========================================
def processa_tracce(json_path, energia_netta_joule):
    """Distribuisce l'energia netta tra gli span usando il tag cpu.nanos."""
    print(f"\n 2. Lettura Tracce Software ({json_path})...")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        traces = json.load(f)

    # 1. Calcolo del lavoro CPU totale di tutto il sistema
    cpu_totale_nanos = 0
    numero_span_con_cpu = 0

    for trace in traces:
        for span in trace:
            tags = span.get('tags', {})
            if 'cpu.nanos' in tags:
                cpu_totale_nanos += int(tags['cpu.nanos'])
                numero_span_con_cpu += 1

    print(f"   ├─ Trovati {numero_span_con_cpu} span con misurazione CPU pura.")
    
    if cpu_totale_nanos == 0: 
        print("   Nessun tag 'cpu.nanos' trovato. Assicurati che il codice Java sia aggiornato!")
        return traces

    # 2. Calcolo costo energetico per singolo nanosecondo di CPU
    joule_per_nano = energia_netta_joule / cpu_totale_nanos
    print(f"   └─ Costo energetico CPU: {joule_per_nano:.12f} Joule/nanosecondo")

    # 3. Iniezione Energia negli Span
    print("\n 3. Iniezione Energia negli Span...")
    for trace in traces:
        for span in trace:
            tags = span.get('tags', {})

            # Attribuiamo energia SOLO se abbiamo la certezza matematica dello sforzo CPU
            if 'cpu.nanos' in tags:
                cpu_usata = int(tags['cpu.nanos'])
                energia_span = cpu_usata * joule_per_nano

                span['tags']['energy.joules'] = f"{energia_span:.6f}"
                span['tags']['energy.attribution_model'] = "CPU-Proportional (cpu.nanos)"
            else:
                # Se uno span non ha cpu.nanos (es. una chiamata fittizia), gli diamo 0
                span['tags'].setdefault('energy.joules', "0.000000")

    return traces

# ========================================
# FUNZIONE 3: SALVATAGGIO DEI RISULTATI
# ========================================
def salva_risultato(traces, output_path):
    """Salva tutte le tracce e una versione ridotta per Zipkin."""
    # ---- STEP 1: Appiattimento della struttura nested ----
    # Zipkin usa una struttura a due livelli: [traccia[span, span], traccia[span]]
    # Per l'analisi e la reimportazione, convertiamo in lista piatta: [span, span, span]
    span_piatti = []
    for trace in traces:
        for span in trace:
            span_piatti.append(span)
            
    # ---- STEP 2: Salvataggio file COMPLETO ----
    # Contiene tutti gli span con i tag energetici - usato per l'analisi matematica della tesi
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(span_piatti, f, indent=4)  # indent=4 per leggibilita' umana
    print(f"\n File COMPLETO salvato per l'analisi: {output_path}")

    # ---- STEP 3: Salvataggio file LIGHT ----
    # Versione ridotta con solo i primi 20 span
    # Utile per visualizzare le tracce su Zipkin senza sovraccaricare l'interfaccia
    span_leggeri = span_piatti[:20]  # Prende solo i primi 20 span
    output_light = output_path.replace(".json", "_LIGHT.json")  # Nome file derivato
    with open(output_light, 'w', encoding='utf-8') as f:
        json.dump(span_leggeri, f, indent=4)
    print(f"📸 File LEGGERO salvato per lo screenshot: {output_light}")

# ========================================
# PUNTO DI INGRESSO DEL PROGRAMMA
# ========================================
if __name__ == "__main__":
    # Esegue la pipeline completa solo se i due input richiesti sono presenti
    # Verifica che entrambi i file di input esistano prima di procedere
    if not os.path.exists(CSV_FILE) or not os.path.exists(JSON_FILE):
        print(" ERRORE: Assicurati di avere sia il file CSV che il JSON nella cartella!")
    else:
        # ---- Pipeline completa in 3 passi ----
        
        # PASSO 1: Leggi il CSV hardware e calcola l'energia netta del sistema
        energia_netta = calcola_energia_netta_dal_csv(CSV_FILE)
        
        # PASSO 2: Carica le tracce Zipkin e inietta l'energia proporzionalmente
        tracce_arricchite = processa_tracce(JSON_FILE, energia_netta)
        
        # PASSO 3: Salva i risultati su file (completo + light)
        salva_risultato(tracce_arricchite, OUTPUT_FILE)