#!/usr/bin/env python3
"""
Genera un grafico che mostra l'energia consumata da ogni tipo di span
attraverso le varie ripetizioni degli esperimenti.

Per ogni span (identificato dal campo 'name'), aggrega l'energia totale
consumata in ogni esperimento ripetuto e la visualizza come serie temporale.
"""

import json
import os
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np

# Configurazione
BASE_DIRS = [
    Path("c:/Users/berar/Desktop/Tesi_Esperimenti/3/risultati1"),
    Path("c:/Users/berar/Desktop/Tesi_Esperimenti/3/risultati2")
]
OUTPUT_DIR = Path("c:/Users/berar/Desktop/Tesi_Esperimenti/3/grafici_campagna")
OUTPUT_DIR.mkdir(exist_ok=True)

# Colori per i diversi span
COLORS = plt.cm.tab20.colors


def load_traces_from_test(test_path):
    """Carica le tracce con energia da un singolo test."""
    json_path = test_path / "dataset_con_energia_LIGHT.json"

    if not json_path.exists():
        print(f"[WARN]  File non trovato: {json_path}")
        return []

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            traces = json.load(f)
        return traces
    except Exception as e:
        print(f"[ERROR] Errore nel leggere {json_path}: {e}")
        return []


def aggregate_energy_by_span(traces):
    """
    Aggrega l'energia totale consumata per ogni tipo di span.
    Ritorna un dizionario: {span_name: total_energy_joules}
    """
    span_energy = defaultdict(float)

    for span in traces:
        span_name = span.get('name', 'unknown')
        energy_str = span.get('tags', {}).get('energy.joules', '0')

        try:
            energy_joules = float(energy_str)
            span_energy[span_name] += energy_joules
        except (ValueError, TypeError):
            pass

    return dict(span_energy)


def collect_data_for_block(block_path):
    """
    Raccoglie i dati di energia per tutti i test di un blocco.
    Ritorna un dizionario: {span_name: [energia_test1, energia_test2, ...]}
    Se uno span non appare in un test, il valore è 0.
    """
    # Ordina i test numericamente
    test_dirs = sorted([d for d in block_path.iterdir() if d.is_dir()],
                      key=lambda x: int(x.name.split('_')[1]))

    # Prima passata: trova tutti gli span unici
    all_span_names = set()
    test_data = []  # Lista di (test_num, span_energy_dict)

    for test_dir in test_dirs:
        test_num = test_dir.name.split('_')[1]
        traces = load_traces_from_test(test_dir)
        span_energy = aggregate_energy_by_span(traces)

        all_span_names.update(span_energy.keys())
        test_data.append((test_num, span_energy))

        print(f"  OK Test {test_num}: {len(traces)} span, {len(span_energy)} tipi di span")

    # Seconda passata: crea array completi con 0 per span mancanti
    data_by_span = {span_name: [] for span_name in all_span_names}

    for test_num, span_energy in test_data:
        for span_name in all_span_names:
            energy = span_energy.get(span_name, 0)  # 0 se span non presente
            data_by_span[span_name].append(energy)

    return dict(data_by_span)


def plot_energy_per_span_over_repetitions(data_by_span, block_name, num_users):
    """
    Genera il grafico dell'energia per span attraverso le ripetizioni.
    """
    # Numero di test (ripetizioni)
    num_tests = len(next(iter(data_by_span.values())))
    test_numbers = list(range(1, num_tests + 1))

    # Ordina gli span per energia media decrescente
    span_sorted = sorted(data_by_span.items(),
                        key=lambda x: np.mean(x[1]),
                        reverse=True)

    # Limita a top 15 span per leggibilità
    top_n = min(15, len(span_sorted))
    span_sorted = span_sorted[:top_n]

    # Crea il grafico
    fig, ax = plt.subplots(figsize=(14, 8))

    # Plotta una linea per ogni span
    for idx, (span_name, energy_values) in enumerate(span_sorted):
        color = COLORS[idx % len(COLORS)]

        # Plotta linea con marker
        ax.plot(test_numbers, energy_values,
               marker='o', linewidth=2, markersize=6,
               label=span_name, color=color, alpha=0.8)

    # Configurazione grafico
    ax.set_xlabel('Numero Ripetizione Esperimento', fontsize=12, fontweight='bold')
    ax.set_ylabel('Energia Totale Consumata (Joules)', fontsize=12, fontweight='bold')
    ax.set_title(f'Energia consumata per Span attraverso le ripetizioni\n{block_name} - {num_users} utenti',
                fontsize=14, fontweight='bold', pad=20)

    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_xticks(test_numbers)

    # Legenda fuori dal grafico
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left',
             fontsize=9, framealpha=0.9)

    # Layout compatto
    plt.tight_layout()

    # Save
    output_file = OUTPUT_DIR / f"energia_span_ripetizioni_{block_name}_{num_users}utenti.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"[DONE] Grafico salvato: {output_file}")

    plt.close()


def plot_energy_statistics_boxplot(data_by_span, block_name, num_users):
    """
    Genera un boxplot per mostrare la distribuzione statistica dell'energia per span.
    """
    # Ordina span per energia mediana
    span_sorted = sorted(data_by_span.items(),
                        key=lambda x: np.median(x[1]),
                        reverse=True)

    # Limita a top 12 per leggibilità
    top_n = min(12, len(span_sorted))
    span_sorted = span_sorted[:top_n]

    # Prepara dati per boxplot
    labels = [name.replace('http ', '').replace('/owners/', '/o/').replace('/pets/', '/p/')
             for name, _ in span_sorted]
    data = [values for _, values in span_sorted]

    # Crea grafico
    fig, ax = plt.subplots(figsize=(14, 8))

    bp = ax.boxplot(data, labels=labels, patch_artist=True,
                   notch=True, showmeans=True)

    # Colora i box
    for patch, color in zip(bp['boxes'], COLORS):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)

    # Configurazione
    ax.set_xlabel('Tipo di Span', fontsize=12, fontweight='bold')
    ax.set_ylabel('Energia Totale Consumata (Joules)', fontsize=12, fontweight='bold')
    ax.set_title(f'Distribuzione Energia per Span (10 ripetizioni)\n{block_name} - {num_users} utenti',
                fontsize=14, fontweight='bold', pad=20)

    ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    plt.xticks(rotation=45, ha='right')

    plt.tight_layout()

    # Save
    output_file = OUTPUT_DIR / f"energia_span_boxplot_{block_name}_{num_users}utenti.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"[DONE] Boxplot salvato: {output_file}")

    plt.close()


def main():
    """Funzione principale."""
    print("[START] Generazione grafici energia span per ripetizioni\n")
    print(f"[DIR] Directory analizzate:")
    for base_dir in BASE_DIRS:
        print(f"   - {base_dir}")
    print()

    # Raccogli tutti i blocchi da entrambe le directory
    all_blocks = []
    for base_dir in BASE_DIRS:
        if not base_dir.exists():
            print(f"[WARN]  Directory non trovata: {base_dir}")
            continue

        block_dirs = [d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith('blocco_')]
        all_blocks.extend(block_dirs)

    # Ordina per numero utenti
    all_blocks.sort(key=lambda x: int(x.name.split('_')[-1].replace('utenti', '')))

    print(f"[FOUND] Trovati {len(all_blocks)} blocchi totali\n")

    for block_dir in all_blocks:
        block_name = block_dir.name
        # Estrai numero utenti dal nome (es. "blocco_1_10utenti" -> 10)
        num_users = block_name.split('_')[-1].replace('utenti', '')

        print(f"\n{'='*70}")
        print(f"[BLOCK] Elaborazione {block_name} ({num_users} utenti)")
        print(f"{'='*70}")

        # Raccogli dati
        data_by_span = collect_data_for_block(block_dir)

        if not data_by_span:
            print(f"[WARN]  Nessun dato trovato per {block_name}")
            continue

        print(f"\n[INFO] Trovati {len(data_by_span)} tipi di span diversi")

        # Genera i grafici
        plot_energy_per_span_over_repetitions(data_by_span, block_name, num_users)
        plot_energy_statistics_boxplot(data_by_span, block_name, num_users)

    print(f"\n{'='*70}")
    print("[DONE] Elaborazione completata!")
    print(f"[OUTPUT] Grafici salvati in: {OUTPUT_DIR}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
