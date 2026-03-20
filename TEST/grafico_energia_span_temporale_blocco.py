#!/usr/bin/env python3
"""
Grafico energia span significativi nel tempo per blocco singolo.

Mostra l'energia consumata dagli span durante i test di un blocco (es. 10 utenti),
con timeline continua e visualizzazione doppia:
1. Scatter plot con pallini individuali (dimensione proporzionale all'energia)
2. Aggregazioni temporali per mostrare trend

Asse X: Timeline continua 0-280 secondi (tutti i 10 test sovrapposti)
Asse Y: Span significativi (operazioni con energia rilevante)
"""

import json
from pathlib import Path
from collections import defaultdict, Counter
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Configurazione
BASE_DIR = Path("c:/Users/berar/Desktop/Tesi_Esperimenti/3/risultati1")
OUTPUT_DIR = Path("c:/Users/berar/Desktop/Tesi_Esperimenti/3/grafici_campagna")
OUTPUT_DIR.mkdir(exist_ok=True)

# Configurazione del blocco da analizzare
TARGET_BLOCK = "blocco_1_10utenti"

# Operazioni da escludere (monitoring/health checks)
EXCLUDE_OPERATIONS = {
    'http get /actuator/health',
    'http get /actuator/info',
    'http get /actuator/prometheus',
    'http get',
    'http put',
    'http post'
}


def load_block_tests_data(block_path):
    """
    Carica tutti i 10 test del blocco specificato.
    Usa dataset_con_energia.json (file completo, non LIGHT).

    Returns:
        list: Lista di liste di span [test1_spans, test2_spans, ...]
    """
    print(f"[INFO] Caricamento dati dal blocco: {block_path}")

    spans_by_test = []
    test_dirs = sorted([d for d in block_path.iterdir() if d.is_dir()],
                      key=lambda x: int(x.name.split('_')[1]))

    for test_dir in test_dirs:
        test_num = test_dir.name.split('_')[1]
        json_path = test_dir / "dataset_con_energia.json"

        if not json_path.exists():
            print(f"[WARN] File non trovato: {json_path}")
            spans_by_test.append([])
            continue

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                spans = json.load(f)

            print(f"  Test {test_num}: {len(spans)} span caricati")
            spans_by_test.append(spans)

        except Exception as e:
            print(f"[ERROR] Errore caricamento {json_path}: {e}")
            spans_by_test.append([])

    return spans_by_test


def normalize_timestamps_across_tests(spans_by_test):
    """
    Normalizza timestamp di tutti i test sulla stessa timeline 0-280s.
    Sovrappone i 10 test per analisi comparativa.

    Returns:
        list: Lista di dict con dati normalizzati
    """
    print("[INFO] Normalizzazione timestamp...")

    normalized_data = []

    for test_idx, spans in enumerate(spans_by_test):
        if not spans:
            continue

        # Trova range temporale del test
        timestamps = [span['timestamp'] for span in spans]
        min_timestamp = min(timestamps)
        max_timestamp = max(timestamps)

        duration_seconds = (max_timestamp - min_timestamp) / 1_000_000
        print(f"  Test {test_idx+1}: durata {duration_seconds:.1f} secondi")

        # Normalizza ogni span
        for span in spans:
            relative_time = (span['timestamp'] - min_timestamp) / 1_000_000

            # Estrai energia
            try:
                energy = float(span['tags'].get('energy.joules', 0))
            except (ValueError, TypeError):
                energy = 0

            if energy > 0:  # Solo span con energia significativa
                normalized_data.append({
                    'test_id': test_idx,
                    'time_seconds': relative_time,
                    'operation': span['name'],
                    'energy': energy,
                    'service': span.get('localEndpoint', {}).get('serviceName', 'unknown')
                })

    print(f"  Totale span normalizzati: {len(normalized_data)}")
    return normalized_data


def identify_significant_spans(normalized_data):
    """
    Identifica i tipi di span più significativi per energia.
    Filtra operazioni actuator/monitoring.

    Returns:
        list: Lista dei 7 nomi operazioni più significative
    """
    print("[INFO] Identificazione span significativi...")

    # Aggrega per operazione
    operation_stats = defaultdict(list)
    operation_counts = Counter()

    for item in normalized_data:
        operation = item['operation']
        if operation not in EXCLUDE_OPERATIONS:
            operation_stats[operation].append(item['energy'])
            operation_counts[operation] += 1

    # Calcola statistiche per ogni operazione
    operation_metrics = []
    for operation, energies in operation_stats.items():
        total_energy = sum(energies)
        median_energy = np.median(energies)
        count = operation_counts[operation]

        # Punteggio combinato: mediana * conteggio (favorisce operazioni frequenti e energivore)
        score = median_energy * count

        operation_metrics.append({
            'operation': operation,
            'total_energy': total_energy,
            'median_energy': median_energy,
            'count': count,
            'score': score
        })

    # Ordina per punteggio e prendi top 7
    operation_metrics.sort(key=lambda x: x['score'], reverse=True)
    top_operations = [op['operation'] for op in operation_metrics[:7]]

    print("  Top 7 operazioni significative:")
    for i, op_data in enumerate(operation_metrics[:7], 1):
        print(f"    {i}. {op_data['operation']}")
        print(f"       Count: {op_data['count']}, Median Energy: {op_data['median_energy']:.3f} J")

    return top_operations


def prepare_dual_visualization_data(normalized_data, significant_operations):
    """
    Prepara dati per visualizzazione doppia: scatter + aggregazioni.

    Returns:
        tuple: (scatter_data, aggregation_data)
    """
    print("[INFO] Preparazione dati per visualizzazione...")

    # Filtra solo operazioni significative
    filtered_data = [item for item in normalized_data
                    if item['operation'] in significant_operations]

    # Mappa operazione -> indice Y
    op_to_y = {op: i for i, op in enumerate(significant_operations)}

    # Prepara dati scatter
    scatter_data = {
        'times': [],
        'y_positions': [],
        'energies': [],
        'operations': [],
        'test_ids': []
    }

    for item in filtered_data:
        scatter_data['times'].append(item['time_seconds'])
        scatter_data['y_positions'].append(op_to_y[item['operation']])
        scatter_data['energies'].append(item['energy'])
        scatter_data['operations'].append(item['operation'])
        scatter_data['test_ids'].append(item['test_id'])

    # Prepara aggregazioni temporali (finestre di 15 secondi)
    window_size = 15  # secondi
    max_time = max(scatter_data['times']) if scatter_data['times'] else 280
    num_windows = int(max_time / window_size) + 1

    aggregation_data = {
        'window_centers': [],
        'operations': significant_operations,
        'energy_matrix': np.zeros((len(significant_operations), num_windows))
    }

    for w in range(num_windows):
        window_start = w * window_size
        window_end = (w + 1) * window_size
        window_center = window_start + window_size / 2

        aggregation_data['window_centers'].append(window_center)

        # Aggrega energia per finestra per ogni operazione
        for op_idx, operation in enumerate(significant_operations):
            window_energy = 0
            for item in filtered_data:
                if (operation == item['operation'] and
                    window_start <= item['time_seconds'] < window_end):
                    window_energy += item['energy']

            aggregation_data['energy_matrix'][op_idx, w] = window_energy

    print(f"  Scatter points: {len(scatter_data['times'])}")
    print(f"  Aggregation windows: {num_windows} (size: {window_size}s)")

    return scatter_data, aggregation_data


def plot_temporal_energy_scatter(scatter_data, aggregation_data, significant_operations, output_file):
    """
    Genera il grafico temporale con visualizzazione doppia.
    """
    print(f"[INFO] Generazione grafico: {output_file}")

    # Crea figura con subplot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(18, 12),
                                   height_ratios=[3, 1], sharex=True)
    fig.suptitle('Energia Span nel Tempo - Blocco 10 Utenti (10 test sovrapposti)',
                fontsize=16, fontweight='bold', y=0.98)

    # === SUBPLOT 1: SCATTER PLOT ===

    if scatter_data['energies']:
        energies = np.array(scatter_data['energies'])
        max_energy = np.max(energies)

        # Dimensioni pallini (scala logaritmica)
        sizes = 20 + 200 * (np.log1p(energies) / np.log1p(max_energy))

        # Colori basati su energia (normalizzati)
        colors = energies / max_energy

        # Scatter plot
        scatter = ax1.scatter(scatter_data['times'], scatter_data['y_positions'],
                             s=sizes, c=colors, cmap='YlOrRd', alpha=0.6,
                             edgecolors='black', linewidth=0.3)

        # Colorbar
        cbar = plt.colorbar(scatter, ax=ax1, fraction=0.046, pad=0.04)
        cbar.set_label('Energia (Joules)', fontsize=12, fontweight='bold')

    # Configurazione assi subplot 1
    ax1.set_ylabel('Operazioni', fontsize=13, fontweight='bold')
    ax1.set_title('Scatter Plot - Pallini individuali', fontsize=12, pad=10)

    # Abbrevia nomi operazioni
    short_labels = []
    for op in significant_operations:
        short = op.replace('http ', '').replace('/owners/', '/o/').replace('/pets/', '/p/')
        short = short.replace('/{ownerid}', '/{id}').replace('/{ownerId}', '/{id}')
        short = short.replace('/{petid}', '/{pid}').replace('/{petId}', '/{pid}')
        short_labels.append(short)

    ax1.set_yticks(range(len(significant_operations)))
    ax1.set_yticklabels(short_labels, fontsize=10)
    ax1.set_ylim(-0.5, len(significant_operations) - 0.5)
    ax1.grid(True, alpha=0.3, linestyle='-', linewidth=0.5, axis='x')

    # === SUBPLOT 2: AGGREGAZIONI TEMPORALI ===

    # Line plot per ogni operazione
    colors_line = plt.cm.Set3(np.linspace(0, 1, len(significant_operations)))
    window_centers = aggregation_data['window_centers']

    for op_idx, operation in enumerate(significant_operations):
        energy_trend = aggregation_data['energy_matrix'][op_idx, :]

        # Smoothing semplice con media mobile
        if len(energy_trend) > 3:
            # Media mobile con finestra di 3 punti
            kernel = np.ones(3) / 3
            energy_smooth = np.convolve(energy_trend, kernel, mode='same')
        else:
            energy_smooth = energy_trend

        ax2.plot(window_centers, energy_smooth,
                color=colors_line[op_idx], linewidth=2, alpha=0.8,
                label=short_labels[op_idx])

    # Configurazione assi subplot 2
    ax2.set_xlabel('Tempo (secondi)', fontsize=13, fontweight='bold')
    ax2.set_ylabel('Energia\nAggregata (J)', fontsize=11, fontweight='bold')
    ax2.set_title('Trend Aggregati - Finestre 15 secondi', fontsize=12, pad=10)
    ax2.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)

    # Configurazione asse X comune
    max_time = max(scatter_data['times']) if scatter_data['times'] else 280
    x_ticks = np.arange(0, max_time + 30, 30)
    ax2.set_xticks(x_ticks)
    ax2.set_xlim(0, max_time)

    # Layout
    plt.tight_layout()

    # Salva
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"[DONE] Grafico salvato: {output_file}")

    plt.close()


def main():
    """Funzione principale."""
    print("="*80)
    print("[START] Generazione Grafico Temporale Energia Span - Blocco Singolo")
    print("="*80)

    # Path del blocco target
    block_path = BASE_DIR / TARGET_BLOCK

    if not block_path.exists():
        print(f"[ERROR] Blocco non trovato: {block_path}")
        return

    # Caricamento dati
    spans_by_test = load_block_tests_data(block_path)

    if not any(spans_by_test):
        print("[ERROR] Nessun dato caricato!")
        return

    # Normalizzazione timestamp
    normalized_data = normalize_timestamps_across_tests(spans_by_test)

    if not normalized_data:
        print("[ERROR] Nessun dato normalizzato!")
        return

    # Identificazione span significativi
    significant_operations = identify_significant_spans(normalized_data)

    if not significant_operations:
        print("[ERROR] Nessuna operazione significativa trovata!")
        return

    # Preparazione dati visualizzazione
    scatter_data, aggregation_data = prepare_dual_visualization_data(
        normalized_data, significant_operations)

    # Generazione grafico
    output_file = OUTPUT_DIR / f"energia_span_temporale_{TARGET_BLOCK}.png"
    plot_temporal_energy_scatter(scatter_data, aggregation_data,
                                significant_operations, output_file)

    print("\n" + "="*80)
    print("[DONE] Elaborazione completata!")
    print(f"Grafico salvato in: {output_file}")
    print("="*80)


if __name__ == "__main__":
    main()