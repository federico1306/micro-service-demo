import matplotlib.pyplot as plt
import json
import numpy as np
import os

def raccogli_dati():
    print("="*60)
    print(" GENERATORE DI GRAFICI COMPLETO PER LA TESI")
    print("="*60)
    
    # ==========================================================
    # PARTE 1: GRAFICI DI TREND (Dati inseriti a mano)
    # ==========================================================
    print("\n--- PARTE 1: TREND DI SCALABILITA' E COSTO CPU ---")
    try:
        num_test = int(input("Quante simulazioni manuali vuoi inserire? (Digita 0 se vuoi solo il grafico di correlazione): "))
    except ValueError:
        print("Errore: Devi inserire un numero intero.")
        return

    if num_test > 0:
        utenti = []
        energia = []
        costo_nano = []

        for i in range(num_test):
            print(f"\n--- Inserimento dati per la Simulazione {i+1} ---")
            try:
                u = int(input(" 1. Numero di Utenti simulati in JMeter (es. 10): "))
                e = float(input(" 2. Energia Netta Totale in Joule (es. 1948.52): "))
                c = float(input(" 3. Costo per Nanosecondo (es. 0.00000155): "))
                
                utenti.append(u)
                energia.append(e)
                costo_nano.append(c)
            except ValueError:
                print("Errore nell'inserimento dei dati. Usa il punto per i decimali (es. 10.5). Riprova.")
                return

        # Ordiniamo i dati in base al numero di utenti
        dati_ordinati = sorted(zip(utenti, energia, costo_nano))
        utenti = [d[0] for d in dati_ordinati]
        energia = [d[1] for d in dati_ordinati]
        costo_nano = [d[2] for d in dati_ordinati]

        genera_immagine_trend(utenti, energia, costo_nano)
    else:
        print(" Hai scelto di saltare i grafici di trend manuali.")

    # ==========================================================
    # PARTE 2: GRAFICO CORRELAZIONE (Automatico dal JSON)
    # ==========================================================
    print("\n--- PARTE 2: CORRELAZIONE LATENZA-ENERGIA (Da File JSON) ---")
    genera_grafico_correlazione()


def genera_immagine_trend(utenti, energia, costo_nano):
    print("\n Generazione dei grafici di trend in corso...")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # --- GRAFICO 1: Energia Assoluta vs Utenti ---
    ax1.plot(utenti, energia, marker='o', color='b', linestyle='-', linewidth=2, markersize=8)
    ax1.set_title('Consumo Energetico Netto vs Carico Utenti', fontsize=14)
    ax1.set_xlabel('Numero di Utenti Concorrenti (JMeter)', fontsize=12)
    ax1.set_ylabel('Energia Netta (Joule)', fontsize=12)
    ax1.grid(True, linestyle='--', alpha=0.7)
    
    for i, txt in enumerate(energia):
        ax1.annotate(f"{txt:.1f} J", (utenti[i], energia[i]), textcoords="offset points", xytext=(0,10), ha='center')

    # --- GRAFICO 2: Costo per Nanosecondo vs Utenti ---
    ax2.plot(utenti, costo_nano, marker='s', color='r', linestyle='-', linewidth=2, markersize=8)
    ax2.set_title('Efficienza di Calcolo: Costo CPU vs Carico', fontsize=14)
    ax2.set_xlabel('Numero di Utenti Concorrenti (JMeter)', fontsize=12)
    ax2.set_ylabel('Costo CPU (Joule / Nanosecondo)', fontsize=12)
    ax2.grid(True, linestyle='--', alpha=0.7)
    ax2.ticklabel_format(style='sci', axis='y', scilimits=(0,0))

    plt.tight_layout()
    nome_file_trend = "grafico_analisi_energetica.png"
    plt.savefig(nome_file_trend, dpi=300) 
    print(f" SUCCESSO! Grafico di trend salvato come: {nome_file_trend}")


def genera_grafico_correlazione():
    FILE_JSON = "dataset_con_energia.json"
    
    if not os.path.exists(FILE_JSON):
        print(f" AVVISO: Non trovo il file {FILE_JSON}. Impossibile generare il grafico di correlazione.")
        return

    print(" 1. Lettura dei dati dalle tracce Zipkin...")
    with open(FILE_JSON, 'r', encoding='utf-8') as f:
        spans = json.load(f)

    tempi_risposta_ms = []
    energia_joule = []

    for span in spans:
        tags = span.get('tags', {})
        if 'energy.joules' in tags and 'duration' in span:
            try:
                durata_ms = float(span['duration']) / 1000.0
                energia = float(tags['energy.joules'])

                # Filtriamo i valori a zero per un grafico accurato
                if energia > 0 and durata_ms > 0:
                    tempi_risposta_ms.append(durata_ms)
                    energia_joule.append(energia)
            except ValueError:
                continue

    numero_campioni = len(energia_joule)
    print(f" 2. Trovati {numero_campioni} campioni validi per l'analisi.")

    if numero_campioni < 2:
        print(" Troppi pochi dati per fare un grafico di correlazione!")
        return

    print(" 3. Calcolo della linea di tendenza e generazione grafico...")
    
    # Creiamo una nuova figura indipendente
    plt.figure(figsize=(10, 6))
    plt.scatter(tempi_risposta_ms, energia_joule, alpha=0.6, color='teal', edgecolors='k', s=50)

    # Matematica: Regressione lineare (numpy)
    z = np.polyfit(tempi_risposta_ms, energia_joule, 1)
    p = np.poly1d(z)
    plt.plot(tempi_risposta_ms, p(tempi_risposta_ms), "r--", linewidth=2)

    # Indice di correlazione di Pearson
    correlazione = np.corrcoef(tempi_risposta_ms, energia_joule)[0, 1]

    plt.title('Correlazione tra Tempo di Risposta ed Energia Consumata per Singola Operazione', fontsize=14)
    plt.xlabel('Tempo di Risposta Totale (Millisecondi)', fontsize=12)
    plt.ylabel('Energia Consumata (Joule)', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.legend([
        f'Singole Richieste (n={numero_campioni})', 
        f'Linea di Tendenza (Indice di Correlazione r = {correlazione:.2f})'
    ], loc='upper left', fontsize=11)

    plt.tight_layout()
    nome_output_corr = "grafico_correlazione_energia_latenza.png"
    plt.savefig(nome_output_corr, dpi=300)
    
    print(f" SUCCESSO! L'Indice di correlazione di Pearson calcolato è: {correlazione:.3f}")
    print(f" Grafico salvato come: {nome_output_corr}")

if __name__ == "__main__":
    raccogli_dati()