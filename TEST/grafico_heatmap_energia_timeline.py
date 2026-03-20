#!/usr/bin/env python3
"""
Genera un heatmap che mostra l'energia consumata da ogni tipo di span
nel tempo assoluto attraverso tutta la campagna sperimentale.

Asse X: Tempo assoluto in minuti (0 → ~315 min)
Asse Y: Tipi di span
Colore: Intensità energia (Joules)
"""

import json
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Configurazione
BASE_DIRS = [
    Path("c:/Users/berar/Desktop/Tesi_Esperimenti/3/risultati1"),
    Path("c:/Users/berar/Desktop/Tesi_Esperimenti/3/risultati2")
]
OUTPUT_DIR = Path("c:/Users/berar/Desktop/Tesi_Esperimenti/3/grafici_campagna")
OUTPUT_DIR.mkdir(exist_ok=True)

# Configurazione temporale
TEST_DURATION_MIN = 5  # Durata test in minuti
PAUSE_INTRA_BLOCK_MIN = 1  # Pausa tra test dello stesso blocco
PAUSE_INTER_BLOCK_MIN = 5  # Pausa tra blocchi diversi


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


def collect_all_tests_with_timeline(base_dirs):
    """
    Raccoglie tutti i test da tutti i blocchi con timeline assoluta.

    Returns:
        test_data: lista di dict {
            'time_min': float,
            'block_name': str,
            'num_users': int,
            'test_num': int,
            'span_energy': {span_name: energy_joules}
        }
        block_info: lista di dict {
            'num_users': int,
            'start_time': float,
            'end_time': float
        }
    """
    # Raccogli tutti i blocchi
    all_blocks = []
    for base_dir in base_dirs:
        if not base_dir.exists():
            print(f"[WARN] Directory non trovata: {base_dir}")
            continue

        block_dirs = [d for d in base_dir.iterdir()
                     if d.is_dir() and d.name.startswith('blocco_')]
        all_blocks.extend(block_dirs)

    # Ordina blocchi per numero utenti
    all_blocks.sort(key=lambda x: int(x.name.split('_')[-1].replace('utenti', '')))

    print(f"\n[INFO] Trovati {len(all_blocks)} blocchi:")
    for b in all_blocks:
        num_users = int(b.name.split('_')[-1].replace('utenti', ''))
        print(f"  - {b.name}: {num_users} utenti")

    # Raccolta dati con timeline
    test_data = []
    block_info = []
    current_time = 0.0  # Tempo assoluto in minuti

    for block_idx, block_dir in enumerate(all_blocks):
        block_name = block_dir.name
        num_users = int(block_name.split('_')[-1].replace('utenti', ''))

        block_start_time = current_time

        print(f"\n[BLOCK] {block_name} - Start time: {current_time:.1f} min")

        # Ordina test numericamente
        test_dirs = sorted([d for d in block_dir.iterdir() if d.is_dir()],
                          key=lambda x: int(x.name.split('_')[1]))

        for test_dir in test_dirs:
            test_num = int(test_dir.name.split('_')[1])

            # Tempo centrale del test
            test_center_time = current_time + TEST_DURATION_MIN / 2

            # Carica e aggrega energia
            traces = load_traces_from_test(test_dir)
            span_energy = aggregate_energy_by_span(traces)

            test_data.append({
                'time_min': test_center_time,
                'block_name': block_name,
                'num_users': num_users,
                'test_num': test_num,
                'span_energy': span_energy
            })

            print(f"  Test {test_num:02d}: t={test_center_time:.1f} min, {len(span_energy)} span")

            # Avanza tempo
            current_time += TEST_DURATION_MIN
            if test_num < 10:  # Pausa solo se non è l'ultimo test del blocco
                current_time += PAUSE_INTRA_BLOCK_MIN

        block_end_time = current_time

        block_info.append({
            'num_users': num_users,
            'start_time': block_start_time,
            'end_time': block_end_time
        })

        # Pausa inter-blocco (solo se non è l'ultimo blocco)
        if block_idx < len(all_blocks) - 1:
            current_time += PAUSE_INTER_BLOCK_MIN

    print(f"\n[INFO] Timeline totale: 0 -> {current_time:.1f} minuti")
    print(f"[INFO] Raccolti {len(test_data)} test totali")

    return test_data, block_info


def prepare_heatmap_data(test_data, top_n=15):
    """
    Prepara i dati per il heatmap.

    Returns:
        times: array tempi assoluti (asse X)
        span_names: lista nomi span (asse Y)
        energy_matrix: matrice [n_spans × n_tests]
    """
    n_tests = len(test_data)
    times = np.array([t['time_min'] for t in test_data])

    # Trova tutti gli span unici e calcola energia mediana
    all_spans = defaultdict(list)
    for test in test_data:
        for span_name, energy in test['span_energy'].items():
            all_spans[span_name].append(energy)

    # Calcola mediana per ogni span (considerando 0 per assenza)
    span_medians = {}
    for span_name, energies in all_spans.items():
        # Aggiungi 0 per i test dove lo span non compare
        full_energies = energies + [0] * (n_tests - len(energies))
        span_medians[span_name] = np.median(full_energies)

    # Ordina span per mediana decrescente e prendi i top N
    sorted_spans = sorted(span_medians.items(), key=lambda x: x[1], reverse=True)
    top_spans = [name for name, _ in sorted_spans[:top_n]]

    print(f"\n[INFO] Top {top_n} span per energia mediana:")
    for i, (name, median) in enumerate(sorted_spans[:top_n], 1):
        print(f"  {i:2d}. {name:40s} - {median:.3f} J")

    # Crea matrice energia
    energy_matrix = np.zeros((len(top_spans), n_tests))

    for test_idx, test in enumerate(test_data):
        for span_idx, span_name in enumerate(top_spans):
            energy = test['span_energy'].get(span_name, 0)
            energy_matrix[span_idx, test_idx] = energy

    return times, top_spans, energy_matrix


def plot_heatmap_timeline(times, span_names, energy_matrix, block_info, output_file):
    """
    Genera il grafico scatter con pallini proporzionali all'energia.
    """
    n_spans, n_tests = energy_matrix.shape

    # Crea figura grande
    fig, ax = plt.subplots(figsize=(18, 10))

    # Abbrevia nomi span per leggibilità
    span_labels = []
    for name in span_names:
        # Rimuovi "http " e abbrevia
        short_name = name.replace('http ', '')
        short_name = short_name.replace('/owners/', '/o/')
        short_name = short_name.replace('/pets/', '/p/')
        short_name = short_name.replace('/{ownerid}', '/{id}')
        short_name = short_name.replace('/{ownerId}', '/{id}')
        short_name = short_name.replace('/{petid}', '/{pid}')
        short_name = short_name.replace('/{petId}', '/{pid}')
        span_labels.append(short_name)

    # Prepara dati per scatter plot
    # Per ogni punto (test, span) con energia > 0, crea un pallino
    scatter_x = []  # tempi
    scatter_y = []  # indici span
    scatter_sizes = []  # dimensioni pallini
    scatter_colors = []  # colori

    # Scala per dimensione pallini: energia -> pixel^2
    # Usa scala logaritmica per gestire range ampio
    max_energy = np.max(energy_matrix[energy_matrix > 0]) if np.any(energy_matrix > 0) else 1

    for span_idx in range(n_spans):
        for test_idx in range(n_tests):
            energy = energy_matrix[span_idx, test_idx]

            if energy > 0:  # Mostra solo pallini con energia > 0
                scatter_x.append(times[test_idx])
                scatter_y.append(span_idx)

                # Dimensione proporzionale all'energia (scala logaritmica per variabilità)
                # Usiamo log1p per gestire anche valori piccoli
                size = 50 + 300 * (np.log1p(energy) / np.log1p(max_energy))
                scatter_sizes.append(size)

                # Colore in base all'energia (scala YlOrRd)
                color_intensity = energy / max_energy
                scatter_colors.append(color_intensity)

    # Crea scatter plot
    scatter = ax.scatter(scatter_x, scatter_y, s=scatter_sizes, c=scatter_colors,
                         cmap='YlOrRd', alpha=0.7, edgecolors='black', linewidth=0.5)

    # Configura assi
    ax.set_xlabel('Tempo (minuti)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Tipo di Span', fontsize=13, fontweight='bold')
    ax.set_title('Energia consumata per Span nel tempo - Campagna completa (5 blocchi)',
                fontsize=15, fontweight='bold', pad=20)

    # Tick asse X ogni 30 minuti
    max_time = times[-1]
    x_ticks = np.arange(0, max_time + 30, 30)
    ax.set_xticks(x_ticks)
    ax.set_xticklabels([f"{int(t)}" for t in x_ticks])

    # Tick asse Y con nomi span
    ax.set_yticks(range(n_spans))
    ax.set_yticklabels(span_labels, fontsize=10)
    ax.set_ylim(-0.5, n_spans - 0.5)

    # Linee verticali per separare i blocchi
    for i, block in enumerate(block_info):
        # Linea di inizio blocco
        if i > 0:  # Non disegnare all'inizio del primo blocco
            ax.axvline(block['start_time'], color='blue', linewidth=2,
                      linestyle='--', alpha=0.7)

    # Annotazioni con numero utenti sopra il grafico
    for block in block_info:
        center = (block['start_time'] + block['end_time']) / 2
        ax.text(center, -1.5, f"{block['num_users']}u",
               ha='center', va='bottom', fontsize=11,
               fontweight='bold', color='blue',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.7))

    # Colorbar per intensità colore
    cbar = plt.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Energia (Joules)', fontsize=12, fontweight='bold')

    # Grid sottile
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5, axis='x')
    ax.set_axisbelow(True)

    # Layout
    plt.tight_layout()

    # Salva
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n[DONE] Grafico scatter salvato: {output_file}")

    plt.close()


def main():
    """Funzione principale."""
    print("="*80)
    print("[START] Generazione Heatmap Energia Span - Timeline Completa")
    print("="*80)

    # Raccolta dati con timeline
    test_data, block_info = collect_all_tests_with_timeline(BASE_DIRS)

    if not test_data:
        print("[ERROR] Nessun dato raccolto!")
        return

    # Prepara dati per heatmap
    times, span_names, energy_matrix = prepare_heatmap_data(test_data, top_n=15)

    # Genera heatmap
    output_file = OUTPUT_DIR / "heatmap_energia_span_timeline_completa.png"
    plot_heatmap_timeline(times, span_names, energy_matrix, block_info, output_file)

    print("\n" + "="*80)
    print("[DONE] Elaborazione completata!")
    print("="*80)


if __name__ == "__main__":
    main()
